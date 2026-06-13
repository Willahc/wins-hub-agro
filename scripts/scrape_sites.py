#!/usr/bin/env python3
"""Raspa os SITES de fazenda que já temos (resto_referencia.dominio_cand) procurando contato direto:
e-mail, WhatsApp (wa.me / número rotulado), telefone. Bypassa o Hunter (custo zero). Tenta home +
páginas de contato comuns. Grava prospeccao.site_contato.
Uso: docker run ... --env-file .env -e NSHARD=6 -e SHARD=n hunterpy python /s/scrape_sites.py"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ.get('PGPW') or os.environ['POSTGRES_PASSWORD'])
RE_EMAIL=re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
RE_WA=re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp\.com/send\?phone=)(\+?\d{10,13})',re.I)
RE_TEL=re.compile(r'(?:tel|fone|whats|zap|contato)\D{0,12}(\(?\d{2}\)?\s?9?\d{4}[-\s.]?\d{4})',re.I)
BAD_EMAIL=re.compile(r'(example|sentry|\.png|\.jpg|\.gif|wixpress|godaddy|@2x|domain\.com|email\.com|seu-?email|nome@)',re.I)
PATHS=['','/contato','/contato.html','/contato.php','/fale-conosco','/quem-somos','/sobre','/contact']
def digits(s): return re.sub(r'\D','',s or '')
def norm_mobile(raw):
    d=digits(raw)
    if d.startswith('55') and len(d)>=12: d=d[2:]
    if len(d)==11 and d[2]=='9': return d
    if len(d)==10 and d[2] in '6789': return d[:2]+'9'+d[2:]
    return None
def scrape(cl, dom):
    emails=set(); wa=set(); tels=set()
    for p in PATHS:
        for scheme in (('https://','http://') if p=='' else ('https://',)):
            try:
                r=cl.get(scheme+dom+p, timeout=8, follow_redirects=True)
                if r.status_code>=400: continue
                t=r.text[:200000]
                for e in RE_EMAIL.findall(t):
                    e=e.lower()
                    if not BAD_EMAIL.search(e) and not e.endswith(('.png','.jpg','.webp')): emails.add(e)
                for m in RE_WA.findall(t):
                    z=norm_mobile(m);
                    if z: wa.add(z)
                for m in RE_TEL.findall(t):
                    z=norm_mobile(m)
                    if z: tels.add(z)
                break  # achou a página nesse scheme
            except Exception:
                continue
        if emails or wa: break  # já achou contato, não precisa varrer todas as páginas
    return emails, wa, tels
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.site_contato(
        cnpj_basico varchar(8) PRIMARY KEY, dominio text, emails text, whatsapp text, telefones text, raspado_em timestamptz DEFAULT now());""")
    cur.execute("""SELECT DISTINCT ON (dominio_cand) cnpj_basico, dominio_cand dom
                   FROM prospeccao.resto_referencia
                   WHERE dominio_cand IS NOT NULL
                     AND cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.site_contato)
                   ORDER BY dominio_cand, cnpj_basico""")
    rows=cur.fetchall()
    NSHARD=int(os.environ.get('NSHARD','1')); SHARD=int(os.environ.get('SHARD','0'))
    rows=[r for i,r in enumerate(rows) if i % NSHARD == SHARD]
    print(f"[Scrape sites: {len(rows)} | shard {SHARD}/{NSHARD}]", file=sys.stderr, flush=True)
    ne=nw=0
    with httpx.Client(headers={'User-Agent':'Mozilla/5.0'}) as cl:
        for i,r in enumerate(rows,1):
            try: emails,wa,tels=scrape(cl, r['dom'])
            except Exception: emails,wa,tels=set(),set(),set()
            # só e-mail do PROPRIO dominio (descarta gmail/terceiro que aparece no rodapé)
            own=[e for e in emails if e.split('@')[1]==r['dom']] or list(emails)[:3]
            if own: ne+=1
            if wa: nw+=1
            cur.execute("""INSERT INTO prospeccao.site_contato(cnpj_basico,dominio,emails,whatsapp,telefones)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET emails=EXCLUDED.emails,whatsapp=EXCLUDED.whatsapp,telefones=EXCLUDED.telefones""",
                (r['cnpj_basico'], r['dom'], ','.join(sorted(set(own))[:5]) or None, ','.join(sorted(wa)[:3]) or None, ','.join(sorted(tels)[:3]) or None))
            if i%50==0: print(f"  {i}/{len(rows)} | email {ne} wa {nw}", file=sys.stderr, flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | com e-mail {ne} ({100*ne//n}%) | com WhatsApp {nw}", file=sys.stderr, flush=True)
if __name__=="__main__": main()
