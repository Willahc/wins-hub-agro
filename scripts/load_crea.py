#!/usr/bin/env python3
"""
load_crea.py — Harvest AGRÔNOMOS / ZOOTECNISTAS from the CREA-GO public
professional lookup, which exposes a captcha-free JSON API:

    POST https://api.crea-go.org.br/busca/dadosConsultaPublica
    body: {"tipo":"profissionais","registro":"<N>/D-GO"}  (or {"nome":"..."})

It returns {result, msg, dados:{idx:{registro,nome,cpf_cnpj,situacao_registro,
prof_titulo,prof_pos_graduacao}}}.

Strategy: iterate the LEGACY sequential registro keyspace (1..MAX) which covers
the older professionals registered as "N/D-GO", keep only records whose title
mentions Agrônomo or Zootecnista, and upsert into prospeccao.tecnico_crea.

Run inside the api container so it reaches the host's IPv4 path:
    docker cp scripts/load_crea.py wins_agro_v1_api_1:/tmp/load_crea.py
    docker exec -i wins_agro_v1_api_1 python /tmp/load_crea.py --max 30000

Note: the API is name/registro driven (no "list all"); modern 10-digit RNP
registros are NOT contiguous and are skipped. CREA-GO carries no municipio or
contact in the public payload — names + título + situação only.
"""
import sys, re, json, time, argparse, threading, urllib.request, urllib.error, ssl
from concurrent.futures import ThreadPoolExecutor, as_completed

API = "https://api.crea-go.org.br/busca/dadosConsultaPublica"
UF = "GO"
FONTE = "https://api.crea-go.org.br/busca/profissionaiseempresas"
TITLE_RE = re.compile(r"gr[ôo]nom|ootecn", re.I)
CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def classify(titulo: str) -> str:
    t = (titulo or "").lower()
    has_agro = bool(re.search(r"gr[ôo]nom", t))
    has_zoo = bool(re.search(r"ootecn", t))
    if has_agro and has_zoo:
        return "agronomo+zootecnista"
    if has_agro:
        return "agronomo"
    if has_zoo:
        return "zootecnista"
    return "outro"


def query_registro(reg: str):
    body = json.dumps({"tipo": "profissionais", "registro": reg}).encode()
    req = urllib.request.Request(
        API, data=body,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=40, context=CTX) as r:
        d = json.loads(r.read().decode())
    if not d.get("result"):
        return []
    dados = d.get("dados") or {}
    recs = list(dados.values()) if isinstance(dados, dict) else list(dados)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=26000, help="max legacy registro to scan")
    ap.add_argument("--start", type=int, default=1)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--out", default="/tmp/crea_go.jsonl")
    args = ap.parse_args()

    def fetch(n):
        reg = f"{n}/D-GO"
        for attempt in range(3):
            try:
                return n, query_registro(reg)
            except (urllib.error.URLError, TimeoutError, ssl.SSLError, OSError):
                time.sleep(1.0)
        return n, []

    lock = threading.Lock()
    kept = 0
    done = 0
    seen = set()
    nums = range(args.start, args.max + 1)
    with open(args.out, "w") as fh, ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(fetch, n) for n in nums]
        for fut in as_completed(futs):
            n, recs = fut.result()
            for rec in recs:
                titulo_raw = rec.get("prof_titulo") or ""
                if not TITLE_RE.search(titulo_raw):
                    continue
                nome = (rec.get("nome") or "").strip()
                registro = (rec.get("registro") or f"{n}/D-GO").strip()
                key = (registro, nome)
                with lock:
                    if key in seen:
                        continue
                    seen.add(key)
                    out = {
                        "cnpj_or_cpf": rec.get("cpf_cnpj"),
                        "nome": nome,
                        "registro_crea": registro,
                        "titulo": classify(titulo_raw),
                        "titulo_raw": titulo_raw,
                        "uf": UF,
                        "municipio": None,
                        "situacao": rec.get("situacao_registro"),
                        "fonte_url": FONTE,
                    }
                    fh.write(json.dumps(out, ensure_ascii=False) + "\n")
                    kept += 1
            with lock:
                done += 1
                if done % 2000 == 0:
                    sys.stderr.write(f"...processed {done}/{len(futs)} kept={kept}\n")
                    fh.flush()
    sys.stderr.write(f"DONE scanned {args.start}..{args.max} kept={kept}\n")
    print(args.out)


if __name__ == "__main__":
    main()
