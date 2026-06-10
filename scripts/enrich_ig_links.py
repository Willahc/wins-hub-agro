#!/usr/bin/env python3
"""Cruzamento: usa o externalUrl do Instagram (domínio REAL da fazenda + agregadores) e a bio
pra extrair E-MAIL e WhatsApp que faltavam. Grátis. Atualiza prospeccao.ig_contato."""
import os, re, httpx
import psycopg2, psycopg2.extras
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['PGPW'])
RE_WA=re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp\.com/send\?phone=)(\+?\d{10,13})',re.I)
RE_EMAIL=re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
BADMAIL=('.png','.jpg','.gif','.svg','noreply','no-reply','sentry','wixpress','example','godaddy','.webp')
ua={"User-Agent":"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36"}
def clean_email(t):
    e=t.lower()
    return e if not any(b in e for b in BADMAIL) else None
c=psycopg2.connect(**DB); c.autocommit=True; cur=c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("ALTER TABLE prospeccao.ig_contato ADD COLUMN IF NOT EXISTS email text")
# 1) e-mail direto da bio
cur.execute("SELECT username,bio FROM prospeccao.ig_contato WHERE email IS NULL AND bio ~ '@'")
b=0
for r in cur.fetchall():
    for m in RE_EMAIL.findall(r['bio']):
        e=clean_email(m)
        if e: cur.execute("UPDATE prospeccao.ig_contato SET email=%s WHERE username=%s",(e,r['username'])); b+=1; break
# 2) raspa externalUrl (domínio real + agregador) p/ email + whatsapp
cur.execute(r"SELECT username,ext,whatsapp,email FROM prospeccao.ig_contato WHERE ext ~* '\.(com|com\.br|agr\.br|net|org|co)' AND ext !~* '(instagram|facebook|youtu|tiktok|drive\.google|docs\.google|t\.me)'")
rows=cur.fetchall(); se=sw=0
def host(u):
    m=re.match(r'^https?://(www\.)?([^/]+)',u.lower()); return m.group(2) if m else ''
for r in rows:
    h=host(r['ext']); cand=[r['ext']]
    if '.' in h and 'linktr' not in h and 'beacons' not in h:
        cand += [f"https://{h}/contato", f"https://{h}/fale-conosco", f"https://{h}/contact"]
    em=r['email']; wa=r['whatsapp']
    for url in cand:
        if em and wa: break
        try:
            resp=httpx.get(url,headers=ua,timeout=8,follow_redirects=True)
            if resp.status_code!=200: continue
            t=resp.text
            if not wa:
                m=RE_WA.search(t)
                if m: wa=re.sub(r'\D','',m.group(1)); sw+=1
            if not em:
                for x in RE_EMAIL.findall(t):
                    e=clean_email(x)
                    if e and not e.endswith(('.com.png',)): em=e; se+=1; break
        except Exception: continue
    if em!=r['email'] or wa!=r['whatsapp']:
        cur.execute("UPDATE prospeccao.ig_contato SET email=COALESCE(%s,email), whatsapp=COALESCE(%s,whatsapp) WHERE username=%s",(em,wa,r['username']))
print(f"e-mail da bio: {b} | e-mail do site: {se} | whatsapp novo do site: {sw}")
cur.execute("SELECT count(email) e, count(whatsapp) w FROM prospeccao.ig_contato")
t=cur.fetchone(); print(f"TOTAL ig_contato: email {t['e']} · whatsapp {t['w']}")
