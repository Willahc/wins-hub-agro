#!/usr/bin/env python3
"""Frente 2 (antes de caçar contato novo): VALIDAR os contatos que já temos.
E-mail -> checa registro MX REAL do domínio via DNS-over-HTTPS (grátis, sem dep nova).
Telefone -> valida DDD brasileiro + formato (fixo 10 / celular 11). Liveness real de
linha exige HLR pago; aqui marcamos formato/DDD (descarta o lixo óbvio de graça).

Roda no container api: docker exec wins_agro_v1_api_1 python /app/validar_contatos_top500.py
"""
import os, re, sys
import psycopg2, psycopg2.extras, httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

DB = dict(host=os.getenv("DB_HOST","db"), port=int(os.getenv("DB_PORT",5432)),
          dbname=os.getenv("POSTGRES_DB","wins_agro"), user=os.getenv("POSTGRES_USER","postgres"),
          password=os.getenv("POSTGRES_PASSWORD",""))

FREE = {'gmail.com','hotmail.com','outlook.com','yahoo.com.br','yahoo.com','live.com',
        'bol.com.br','terra.com.br','uol.com.br','icloud.com','msn.com','globo.com','me.com'}
DDD_OK = {11,12,13,14,15,16,17,18,19,21,22,24,27,28,31,32,33,34,35,37,38,41,42,43,44,45,46,
          47,48,49,51,53,54,55,61,62,63,64,65,66,67,68,69,71,73,74,75,77,79,81,82,83,84,85,
          86,87,88,89,91,92,93,94,95,96,97,98,99}

def check_mx(domain):
    """True se o domínio tem registro MX (recebe e-mail). Via DoH Google (grátis)."""
    try:
        r = httpx.get("https://dns.google/resolve", params={"name":domain,"type":"MX"}, timeout=8.0)
        j = r.json()
        if j.get("Status") == 3:   # NXDOMAIN
            return "dominio_inexistente"
        if any(a.get("type")==15 for a in j.get("Answer",[])):
            return "mx_ok"
        # sem MX -> tenta A (alguns aceitam mail no A, raro)
        r2 = httpx.get("https://dns.google/resolve", params={"name":domain,"type":"A"}, timeout=8.0)
        return "sem_mx" if r2.json().get("Answer") else "dominio_inexistente"
    except Exception:
        return "erro_dns"

def classify_email(email, mx_cache):
    if not email or "@" not in email:
        return "sem_email", None
    dom = email.split("@",1)[1].lower().strip()
    if not re.match(r'^[\w.\-+]+@[\w.\-]+\.\w{2,}$', email):
        return "sintaxe_ruim", dom
    if dom in FREE:
        return "free_entregavel", dom
    if dom not in mx_cache:
        mx_cache[dom] = check_mx(dom)
    return mx_cache[dom], dom

def classify_phone(tel):
    d = re.sub(r'\D','', tel or '')
    if len(d) not in (10,11): return "formato_ruim"
    if int(d[:2]) not in DDD_OK: return "ddd_invalido"
    return "celular_fmt" if len(d)==11 else "fixo_fmt"

def main():
    conn = psycopg2.connect(**DB); conn.autocommit=True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.top500_validacao(
        cnpj_basico varchar(8) PRIMARY KEY, email text, email_dom text, email_status text,
        telefone text, tel_status text, validado_em timestamptz DEFAULT now());""")
    cur.execute("SELECT cnpj_basico, email, telefone FROM prospeccao.top500_pilot ORDER BY rank")
    rows = cur.fetchall()
    # 1) pré-resolve MX de todos os domínios únicos (paralelo), depois classifica
    doms = sorted({(r["email"].split("@",1)[1].lower().strip()) for r in rows
                   if r["email"] and "@" in r["email"]} - FREE)
    print(f"[validando {len(rows)} prospects | {len(doms)} domínios únicos p/ checar MX]", file=sys.stderr, flush=True)
    mx_cache = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(check_mx, d): d for d in doms}
        for f in as_completed(futs):
            mx_cache[futs[f]] = f.result()
    # 2) classifica e grava
    agg_e, agg_t = {}, {}
    for r in rows:
        es, dom = classify_email(r["email"], mx_cache)
        ts = classify_phone(r["telefone"])
        agg_e[es]=agg_e.get(es,0)+1; agg_t[ts]=agg_t.get(ts,0)+1
        cur.execute("""INSERT INTO prospeccao.top500_validacao
            (cnpj_basico,email,email_dom,email_status,telefone,tel_status)
            VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (cnpj_basico) DO UPDATE SET
            email_status=EXCLUDED.email_status, tel_status=EXCLUDED.tel_status, validado_em=now()""",
            (r["cnpj_basico"], r["email"], dom, es, r["telefone"], ts))
    print("\n=== E-MAIL (existente) ===", file=sys.stderr)
    for k,v in sorted(agg_e.items(), key=lambda x:-x[1]): print(f"  {k:22} {v}", file=sys.stderr)
    print("=== TELEFONE (existente) ===", file=sys.stderr)
    for k,v in sorted(agg_t.items(), key=lambda x:-x[1]): print(f"  {k:22} {v}", file=sys.stderr)
    usavel_email = agg_e.get("mx_ok",0)+agg_e.get("free_entregavel",0)
    usavel_tel = agg_t.get("celular_fmt",0)+agg_t.get("fixo_fmt",0)
    print(f"\n[RESUMO] e-mail entregável (MX/free): {usavel_email}/500 | telefone formato-ok: {usavel_tel}/500", file=sys.stderr)

if __name__ == "__main__":
    main()
