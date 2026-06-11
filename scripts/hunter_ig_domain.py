#!/usr/bin/env python3
"""Cruzamento #2: roda Hunter Email Finder usando o DOMÍNIO REAL da fazenda (do externalUrl do
Instagram) + o nome do decisor do lead casado. Acha e-mail de decisor em domínios que não tínhamos."""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.environ['HK']; DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['PGPW'])
SUF={'FILHO','FILHA','JUNIOR','NETO','NETA','SOBRINHO','JR'}
BAD=('linktr','beacons','instagram','facebook','youtu','tiktok','drive.google','docs.google','t.me','wa.me','centralleiloes','programaleiloes','ivelus')
def host(u):
    m=re.match(r'^https?://(www\.)?([^/]+)',(u or '').lower()); return m.group(2) if m else ''
def split_nome(d):
    w=[x for x in re.sub(r'\(.*','',d or '').strip().split() if len(x)>1]
    if not w: return None,None
    f=w[0]; l=w[-1]
    if l.upper() in SUF and len(w)>=2: l=w[-2]
    return f,l
c=psycopg2.connect(**DB); c.autocommit=True; cur=c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("CREATE TABLE IF NOT EXISTS prospeccao.hunter_ig(username text PRIMARY KEY, dominio text, decisor text, email_decisor text, score int)")
# casa handle -> decisor do lead (ICP ou stud)
cur.execute("""
  SELECT g.username, g.ext, COALESCE(s.decisor, m.decisor, ce.decisor, ld.decisor_top) AS decisor
  FROM prospeccao.ig_contato g
  LEFT JOIN prospeccao.icp527_screen s ON s.cab_instagram=g.username
  LEFT JOIN prospeccao.icp_media_screen m ON m.cab_instagram=g.username
  LEFT JOIN prospeccao.cabanha_extra ce ON ce.instagram=g.username
  LEFT JOIN prospeccao.lead_decisor ld ON ld.cnpj_basico=left(ce.cnpj14,8)
  WHERE g.ext ~* '\\.(com|com\\.br|agr\\.br|net|org|co)'
    AND g.username NOT IN (SELECT username FROM prospeccao.hunter_ig)""")
rows=[r for r in cur.fetchall() if r['decisor'] and host(r['ext']) and not any(b in host(r['ext']) for b in BAD)]
print(f"[Hunter em {len(rows)} domínios reais do Instagram + decisor]", file=sys.stderr, flush=True)
achou=0
with httpx.Client(timeout=25) as cl:
    for i,r in enumerate(rows,1):
        dom=host(r['ext']); first,last=split_nome(r['decisor'])
        if not first: continue
        em=sc=None; ok_api=False
        for t in range(3):   # retry: falha de API != "vazio" (que é permanente)
            try:
                j=cl.get('https://api.hunter.io/v2/email-finder',params={'domain':dom,'first_name':first,'last_name':last,'api_key':KEY}).json()
                em=j.get('data',{}).get('email'); sc=j.get('data',{}).get('score'); ok_api=True; break
            except Exception:
                time.sleep(2*(t+1))
        if not ok_api:
            print(f"  {i} API falhou 3x — pulado (re-run tenta de novo)", file=sys.stderr); continue
        if em: achou+=1
        cur.execute("INSERT INTO prospeccao.hunter_ig(username,dominio,decisor,email_decisor,score) VALUES(%s,%s,%s,%s,%s) ON CONFLICT(username) DO UPDATE SET email_decisor=EXCLUDED.email_decisor,score=EXCLUDED.score",
                    (r['username'],dom,r['decisor'],em,sc))
        time.sleep(0.4)
n=len(rows) or 1
print(f"[FIM] {len(rows)} | e-mail de decisor (domínio do IG): {achou} ({100*achou//n}%)", file=sys.stderr, flush=True)
