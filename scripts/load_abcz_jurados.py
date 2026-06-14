#!/usr/bin/env python3
"""
load_abcz_jurados.py — Harvest the ABCZ "Colégio de Jurados" public roster.

ABCZ (Assoc. Brasileira dos Criadores de Zebu) publishes its credentialed
zebu judges (jurados) as plain HTML. These are elite, contactable
veterinarians AND zootecnistas who influence genetics decisions nationally.
We keep the ZOOTECNISTAS (and agrônomos, if any) for prospeccao.tecnico_crea —
the new professional class — but the loader can optionally keep all.

Page structure (one block per judge):
    <h3>NOME</h3>
    <p>PROFISSAO</p>
    <div class="uk-text-small ...">UF/centrais codes</div>
    <p>(DD)9.9999-9999</p>
    <p>EMAIL; EMAIL2</p>
    <p>Data de efetivação: dd/mm/aaaa</p>

Run inside the api container:
    docker cp scripts/load_abcz_jurados.py wins_agro_v1_api_1:/tmp/
    docker exec -i wins_agro_v1_api_1 python /tmp/load_abcz_jurados.py
Produces /tmp/abcz_jurados.jsonl (one record per judge).
"""
import re, json, sys, ssl, urllib.request

URLS = [
    "https://www.abcz.org.br/produtos-e-servicos/area-tecnica/colegio-de-jurados/listagem-dos-jurados/1/jurados-atualizados-corte",
    "https://www.abcz.org.br/produtos-e-servicos/area-tecnica/colegio-de-jurados/listagem-dos-jurados/5/jurados-atualizados-leite",
]
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\(?\d{2}\)?[\s\-]?\d?[\.\s\-]?\d{4,5}[\-\s]?\d{4}")


def classify(prof: str) -> str:
    p = (prof or "").lower()
    if "zootec" in p:
        return "zootecnista"
    if "agr" in p and "nom" in p:
        return "agronomo"
    if "veterin" in p:
        return "veterinario"
    return (prof or "").strip().lower() or "outro"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60, context=CTX) as r:
        return r.read().decode("utf-8", "replace")


def parse(html, url):
    out = []
    # split into per-judge blocks at each <h3>
    blocks = re.split(r"(?=<h3>)", html)
    for blk in blocks:
        m = re.search(r"<h3>(.*?)</h3>", blk, re.S)
        if not m:
            continue
        nome = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip()
        if not nome or len(nome) < 4:
            continue
        ps = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", p)).strip()
              for p in re.findall(r"<p>(.*?)</p>", blk, re.S)]
        prof = ps[0] if ps else ""
        text = " ".join(ps)
        emails = sorted(set(EMAIL_RE.findall(text)))
        phones = sorted(set(re.sub(r"\s+", "", x) for x in PHONE_RE.findall(text)))
        # centrais/UF codes live in the uk-text-small div
        cm = re.search(r'uk-text-small[^>]*>(.*?)</div>', blk, re.S)
        centrais = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", cm.group(1))).strip() if cm else ""
        out.append({
            "nome": nome,
            "profissao_raw": prof,
            "titulo": classify(prof),
            "email": ";".join(emails) or None,
            "telefone": ";".join(phones) or None,
            "centrais": centrais or None,
            "fonte_url": url,
        })
    return out


def main():
    records = {}
    for url in URLS:
        try:
            html = fetch(url)
        except Exception as e:
            sys.stderr.write(f"fetch fail {url}: {e}\n")
            continue
        for rec in parse(html, url):
            # dedupe by name; first source wins but merge contacts
            key = rec["nome"].upper()
            if key in records:
                continue
            records[key] = rec
    with open("/tmp/abcz_jurados.jsonl", "w") as fh:
        for rec in records.values():
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    by_t = {}
    for r in records.values():
        by_t[r["titulo"]] = by_t.get(r["titulo"], 0) + 1
    sys.stderr.write(f"parsed {len(records)} unique jurados; by titulo: {by_t}\n")
    print("/tmp/abcz_jurados.jsonl")


if __name__ == "__main__":
    main()
