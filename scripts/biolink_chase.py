#!/usr/bin/env python3
"""Persegue os bio-links do Instagram (ig_contato.ext): wa.me direto na URL OU agregador
(linktr.ee/beacons/bio.link) que lista o WhatsApp. Extrai WhatsApp/telefone/e-mail. Custo zero.
Grava prospeccao.biolink_contato (keyed por username). Sharded NSHARD/SHARD."""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ.get('PGPW') or os.environ['POSTGRES_PASSWORD'])
RE_WA=re.compile(r'(?:wa\.me/|api\.whatsapp\.com/(?:send/?)?\?phone=|whatsapp\.com/send\?phone=)(\+?\d{10,13})',re.I)
RE_PHONE=re.compile(r'(?:whats|zap|tel|fone|contato)\D{0,12}(\(?\d{2}\)?\s?9?\d{4}[-\s.]?\d{4})',re.I)
RE_EMAIL=re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
BAD_EMAIL=re.compile(r'(example|sentry|\.png|\.jpg|wixpress|godaddy|@2x|sentry|cloudflare)',re.I)
AGG=re.compile(r'(linktr\.ee|linktree|beacons\.|bio\.link|linkbio|campsite\.|lnk\.bio|mla\.bs|linke\.bio|znap\.link|flowpage|allmylinks)',re.I)
def digits(s): return re.sub(r'\D','',s or '')
def norm_mobile(raw):
    d=digits(raw)
    if d.startswith('55') and len(d)>=12: d=d[2:]
    if len(d)==11 and d[2]=='9': return d
    if len(d)==10 and d[2] in '6789': return d[:2]+'9'+d[2:]
    return None
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.biolink_contato(
        username text PRIMARY KEY, ext text, whatsapp text, telefone text, email text, fonte text, achado_em timestamptz DEFAULT now());""")
    cur.execute("""SELECT username, ext FROM prospeccao.ig_contato
                   WHERE ext IS NOT NULL AND ext<>'' AND username NOT IN (SELECT username FROM prospeccao.biolink_contato)""")
    rows=cur.fetchall()
    NSHARD=int(os.environ.get('NSHARD','1')); SHARD=int(os.environ.get('SHARD','0'))
    rows=[r for i,r in enumerate(rows) if i % NSHARD == SHARD]
    print(f"[Biolink chase: {len(rows)} | shard {SHARD}/{NSHARD}]", file=sys.stderr, flush=True)
    nw=ne=0
    with httpx.Client(headers={'User-Agent':'Mozilla/5.0'}, follow_redirects=True) as cl:
        for i,r in enumerate(rows,1):
            ext=r['ext']; wa=tel=email=None; fonte=None
            m=RE_WA.search(ext)              # wa.me direto na própria URL
            if m: wa=norm_mobile(m.group(1)); fonte='url_direta'
            if not wa and AGG.search(ext):   # agregador -> baixa a página e procura wa.me
                try:
                    t=cl.get(ext, timeout=10).text[:300000]
                    mm=RE_WA.search(t)
                    if mm: wa=norm_mobile(mm.group(1))
                    if not wa:
                        for c in RE_PHONE.findall(t):
                            z=norm_mobile(c)
                            if z: wa=z; break
                    for e in RE_EMAIL.findall(t):
                        e=e.lower()
                        if not BAD_EMAIL.search(e): email=e; break
                    fonte='agregador'
                except Exception: fonte='agregador_falhou'
            if wa: nw+=1
            if email: ne+=1
            cur.execute("""INSERT INTO prospeccao.biolink_contato(username,ext,whatsapp,telefone,email,fonte)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(username) DO UPDATE SET whatsapp=EXCLUDED.whatsapp,email=EXCLUDED.email,fonte=EXCLUDED.fonte""",
                (r['username'], ext[:300], wa, tel, email, fonte))
            if i%50==0: print(f"  {i}/{len(rows)} | wa {nw} email {ne}", file=sys.stderr, flush=True)
    print(f"\n[FIM] {len(rows)} | WhatsApp {nw} | email {ne}", file=sys.stderr, flush=True)
if __name__=="__main__": main()
