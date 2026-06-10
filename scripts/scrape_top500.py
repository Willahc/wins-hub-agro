#!/usr/bin/env python3
"""Piloto de scraping (padrão WiNS Hub Comercial) — extrai telefone / WhatsApp / e-mail
do SITE PRÓPRIO dos prospects do top500. Camada GRÁTIS, mede hit rate real no mercado agro
antes de gastar em Speedio. LGPD: User-Agent identificado, timeout curto, polido.

Roda no container api:  docker exec wins_agro_v1_api_1 python /app/scrape_top500.py
"""
import os, re, sys, html
import psycopg2, psycopg2.extras, httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

DB = dict(host=os.getenv("DB_HOST","db"), port=int(os.getenv("DB_PORT",5432)),
          dbname=os.getenv("POSTGRES_DB","wins_agro"), user=os.getenv("POSTGRES_USER","postgres"),
          password=os.getenv("POSTGRES_PASSWORD",""))
UA = "Mozilla/5.0 (compatible; WiNS-Agro-Bot/1.0; prospeccao)"
PATHS = ["", "/contato", "/fale-conosco", "/contact", "/sobre"]

RE_TEL = re.compile(r'\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}')
RE_WPP = re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d{10,13})', re.I)
RE_EMAIL = re.compile(r'[\w.\-+]+@[\w.\-]+\.\w{2,}')
BAD_EMAIL = ('.png','.jpg','.gif','.svg','.webp','noreply','no-reply','sentry','wixpress','example.','godaddy')

def clean_tel(t):
    d = re.sub(r'\D','',t)
    return d if 10 <= len(d) <= 11 else None

def scrape(row):
    dom = row["dom"]
    tels, wpps, emails = set(), set(), set()
    got = False
    for base in (f"https://{dom}", f"https://www.{dom}"):
        for p in PATHS:
            try:
                r = httpx.get(base+p, headers={"User-Agent":UA}, timeout=8.0, follow_redirects=True)
                if r.status_code != 200 or "text/html" not in r.headers.get("content-type",""):
                    continue
                t = html.unescape(r.text)
                for m in RE_TEL.findall(t):
                    c = clean_tel(m)
                    if c: tels.add(c)
                wpps.update(re.sub(r'\D','',w) for w in RE_WPP.findall(t))
                for e in RE_EMAIL.findall(t):
                    el = e.lower()
                    if not any(b in el for b in BAD_EMAIL): emails.add(el)
                got = True
                if tels and wpps and emails: break
            except Exception:
                continue
        if got and (tels or wpps or emails): break
    score = (30 if tels else 0)+(30 if wpps else 0)+(40 if emails else 0)
    status = "sem_site" if not got else ("vazio" if score==0 else "ok")
    return dict(cnpj_basico=row["cnpj_basico"], dom=dom,
                telefone=next(iter(tels),None), whatsapp=next(iter(wpps),None),
                email=next(iter(emails),None), n_tel=len(tels), n_wpp=len(wpps),
                n_email=len(emails), score=score, status=status)

def main():
    conn = psycopg2.connect(**DB); conn.autocommit=True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.top500_scrape(
        cnpj_basico varchar(8) PRIMARY KEY, dom text, telefone text, whatsapp text,
        email text, n_tel int, n_wpp int, n_email int, score int, status text, scraped_at timestamptz DEFAULT now());""")
    cur.execute("SELECT cnpj_basico, dom FROM prospeccao.top500_pilot WHERE tipo_dominio='proprio' ORDER BY rank")
    rows = cur.fetchall()
    print(f"[scraping {len(rows)} domínios próprios do top500]", file=sys.stderr, flush=True)
    done = 0; agg = {"ok":0,"vazio":0,"sem_site":0}; hit_tel=hit_wpp=hit_email=0
    with ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(scrape, r): r for r in rows}
        for f in as_completed(futs):
            res = f.result(); done += 1; agg[res["status"]] = agg.get(res["status"],0)+1
            hit_tel += res["n_tel"]>0; hit_wpp += res["n_wpp"]>0; hit_email += res["n_email"]>0
            cur.execute("""INSERT INTO prospeccao.top500_scrape
                (cnpj_basico,dom,telefone,whatsapp,email,n_tel,n_wpp,n_email,score,status)
                VALUES (%(cnpj_basico)s,%(dom)s,%(telefone)s,%(whatsapp)s,%(email)s,%(n_tel)s,%(n_wpp)s,%(n_email)s,%(score)s,%(status)s)
                ON CONFLICT (cnpj_basico) DO UPDATE SET telefone=EXCLUDED.telefone,whatsapp=EXCLUDED.whatsapp,
                email=EXCLUDED.email,n_tel=EXCLUDED.n_tel,n_wpp=EXCLUDED.n_wpp,n_email=EXCLUDED.n_email,
                score=EXCLUDED.score,status=EXCLUDED.status,scraped_at=now()""", res)
            if done % 25 == 0:
                print(f"  {done}/{len(rows)} | ok {agg['ok']} vazio {agg['vazio']} sem_site {agg['sem_site']}", file=sys.stderr, flush=True)
    n=len(rows)
    print(f"\n[FIM] {n} sites | site respondeu: {n-agg['sem_site']} | COM ALGUM CONTATO: {agg['ok']}", file=sys.stderr)
    print(f"  hit telefone {hit_tel} ({100*hit_tel//n}%) · WhatsApp {hit_wpp} ({100*hit_wpp//n}%) · email {hit_email} ({100*hit_email//n}%)", file=sys.stderr)

if __name__ == "__main__":
    main()
