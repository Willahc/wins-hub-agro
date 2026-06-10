#!/usr/bin/env python3
"""
scrape_asbia.py — Extrai dados de https://asbia.org.br/associados (FONTE 3).

A asbia.org.br é uma app Next.js (RSC). Dois conjuntos de dados:

  A) CENTRAIS associadas (o "mapa interativo"): NÃO vêm de uma API.
     Estão HARDCODED como um array JS dentro de um chunk Turbopack
     (.../static/chunks/<hash>.js). O mapa só filtra 4 estados
     (SP, RS, MG, SC). Campos por central:
       id, name, state(UF), lat, lng, address, phone, description
       (description carrega CNPJ e às vezes "| Email: ...").
     Algumas centrais têm "extras" (revendas no mesmo endereço, ex. CRV LAGOA).

  B) ASSOCIADOS (logos clicáveis): renderizados server-side no HTML
     como <a href="site" aria-label="Visitar site de NOME"><img...>.

Uso:
    python3 scrape_asbia.py            # baixa tudo da web e regrava os JSONs
    python3 scrape_asbia.py --offline  # usa HTML/chunk já baixados em data/asbia/

Estratégia para achar o chunk certo (caso o hash mude num redeploy):
  1. baixa /associados
  2. lista todos /_next/static/chunks/*.js
  3. baixa cada um e procura o que contém 'lat:' + 'lng:' + 'CNPJ'
  4. faz parse do array de centrais via regex tolerante
"""
import json
import os
import re
import sys
import urllib.request

BASE = "https://asbia.org.br"
PAGE = f"{BASE}/associados"
OUTDIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "asbia")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


# ---------------------------------------------------------------- ASSOCIADOS
def parse_associados(html: str):
    out = []
    seen = set()
    # <a ... href="SITE" ... aria-label="Visitar site de NOME">
    pat = re.compile(
        r'href="(https?://[^"]+)"[^>]*aria-label="Visitar site de ([^"]+)"'
    )
    for m in pat.finditer(html):
        site, name = m.group(1), m.group(2).strip()
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"nome": name, "site": site})
    out.sort(key=lambda x: x["nome"].lower())
    return out


# ----------------------------------------------------------------- CENTRAIS
def find_centrais_chunk(html: str):
    """Retorna (url_chunk, conteudo) do chunk que contém o array de centrais."""
    dpl = ""
    m = re.search(r'dpl=(dpl_[A-Za-z0-9]+)', html)
    if m:
        dpl = "?dpl=" + m.group(1)
    chunks = sorted(set(re.findall(r'/_next/static/chunks/[A-Za-z0-9_~.\-]+\.js', html)))
    for c in chunks:
        try:
            body = fetch(BASE + c + dpl)
        except Exception:
            continue
        if "lat:" in body and "lng:" in body and "CNPJ" in body:
            return BASE + c + dpl, body
    return None, None


def _split_objects(arr_text: str):
    """Divide o texto do array em objetos de nível superior {...} (lida com nesting de 'extras')."""
    objs, depth, start = [], 0, None
    for i, ch in enumerate(arr_text):
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0 and start is not None:
                objs.append(arr_text[start:i + 1])
                start = None
    return objs


def _field(obj: str, key: str):
    # string: key:"..."
    m = re.search(key + r':"((?:[^"\\]|\\.)*)"', obj)
    if m:
        return m.group(1)
    # número: key:-12.34
    m = re.search(key + r':(-?\d+\.?\d*)', obj)
    if m:
        return float(m.group(1))
    return None


def parse_central_obj(obj: str):
    desc = _field(obj, "description") or ""
    cnpj, email = None, None
    mc = re.search(r'CNPJ:\s*([\d./\- ]+)', desc)
    if mc:
        cnpj = mc.group(1).strip().rstrip("|").strip()
    me = re.search(r'Email:\s*([^\s|"]+)', desc, re.I)
    if me:
        email = me.group(1).strip()
    return {
        "id": _field(obj, "id"),
        "nome": _field(obj, "name"),
        "uf": _field(obj, "state"),
        "lat": _field(obj, "lat"),
        "lng": _field(obj, "lng"),
        "endereco": _field(obj, "address"),
        "telefone": _field(obj, "phone"),
        "cnpj": cnpj,
        "email": email,
        "descricao_raw": desc,
    }


def parse_centrais(chunk: str):
    # O array de centrais é o que contém objetos com lat/lng/CNPJ.
    # Pega do primeiro '[{id:"1"' (ou similar) até o ']' equilibrado.
    m = re.search(r'\[\{id:"', chunk)
    if not m:
        return []
    start = m.start()
    depth, end = 0, None
    for i in range(start, len(chunk)):
        if chunk[i] == "[":
            depth += 1
        elif chunk[i] == "]":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    arr_text = chunk[start:end]
    out = []
    for obj in _split_objects(arr_text):
        if "lat:" not in obj:
            continue
        rec = parse_central_obj(obj)
        # extras (revendas embutidas)
        extras = []
        em = re.search(r'extras:\[(.*)\]\}?$', obj, re.S)
        if "extras:" in obj:
            for sub in _split_objects(obj[obj.index("extras:"):]):
                if "name:" in sub:
                    e = {
                        "nome": _field(sub, "name"),
                        "endereco": _field(sub, "address"),
                        "telefone": _field(sub, "phone"),
                        "descricao_raw": _field(sub, "description"),
                    }
                    if e["nome"] and e["nome"] != rec["nome"]:
                        extras.append(e)
        if extras:
            rec["extras"] = extras
        out.append(rec)
    return out


# ------------------------------------------------------------------- DRIVER
def main():
    offline = "--offline" in sys.argv
    os.makedirs(OUTDIR, exist_ok=True)
    html_path = os.path.join(OUTDIR, "associados.html")

    if offline and os.path.exists(html_path):
        html = open(html_path, encoding="utf-8", errors="replace").read()
    else:
        html = fetch(PAGE)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

    associados = parse_associados(html)

    chunk_path = os.path.join(OUTDIR, "centrais_chunk.js")
    if offline and os.path.exists(chunk_path):
        chunk_url = "(offline)"
        chunk = open(chunk_path, encoding="utf-8", errors="replace").read()
    else:
        chunk_url, chunk = find_centrais_chunk(html)
        if chunk:
            with open(chunk_path, "w", encoding="utf-8") as f:
                f.write(chunk)

    centrais = parse_centrais(chunk) if chunk else []

    with open(os.path.join(OUTDIR, "asbia_associados.json"), "w", encoding="utf-8") as f:
        json.dump(associados, f, ensure_ascii=False, indent=2)
    with open(os.path.join(OUTDIR, "asbia_centrais.json"), "w", encoding="utf-8") as f:
        json.dump(centrais, f, ensure_ascii=False, indent=2)

    print(f"chunk de centrais: {chunk_url}")
    print(f"associados: {len(associados)}")
    print(f"centrais:   {len(centrais)}")
    by_uf = {}
    for c in centrais:
        by_uf[c["uf"]] = by_uf.get(c["uf"], 0) + 1
    print("por UF:", by_uf)


if __name__ == "__main__":
    main()
