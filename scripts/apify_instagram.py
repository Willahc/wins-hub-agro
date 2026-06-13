#!/usr/bin/env python3
"""Apify Instagram Profile Scraper: lê a BIO + contato de Business dos handles de cabanha que temos,
pra extrair WhatsApp/telefone/e-mail do decisor (o IG bloqueia nosso IP direto; a Apify usa proxies).
Grava prospeccao.ig_contato. Roda com APIFY_TOKEN no env.

Atores possíveis: 'apify~instagram-profile-scraper' (perfis). Schema de saída pode variar por versão →
teste 2-3 handles primeiro (--test) pra confirmar os nomes dos campos antes do batch."""
import os, re, sys, json, time
import psycopg2, psycopg2.extras, httpx
TOKEN=os.environ['APIFY_TOKEN']
ACTOR=os.environ.get('ACTOR','apify~instagram-profile-scraper')
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ.get('PGPW') or os.environ['POSTGRES_PASSWORD'])
RE_WA=re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d{10,13})',re.I)
RE_TEL=re.compile(r'\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}')

def run_apify(handles):
    url=f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"
    r=httpx.post(url, params={"token":TOKEN}, json={"usernames":handles}, timeout=300)
    r.raise_for_status(); return r.json()

def extrai(item):
    # campos variam por versão do ator — pega defensivo
    bio=item.get('biography') or item.get('bio') or ''
    ext=item.get('externalUrl') or item.get('external_url') or ''
    bphone=(item.get('businessPhoneNumber') or item.get('public_phone_number') or
            item.get('contactPhoneNumber') or item.get('businessContactMethod') or '')
    bemail=(item.get('businessEmail') or item.get('public_email') or item.get('email') or '')
    blob=f"{bio} {ext} {bphone} {json.dumps(item.get('businessAddress',''))}"
    wa=None; m=RE_WA.search(blob)
    if m: wa=re.sub(r'\D','',m.group(1))
    if not wa:
        for c in (re.sub(r'\D','',x) for x in RE_TEL.findall(bio)):
            if len(c)==11 and c[2]=='9': wa=c; break
    return dict(username=item.get('username'), bio=bio[:500], ext=ext,
                business_phone=str(bphone) or None, business_email=str(bemail) or None,
                whatsapp=wa, followers=item.get('followersCount'))

def main():
    test = '--test' in sys.argv
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.ig_contato(
        username text PRIMARY KEY, bio text, ext text, business_phone text, business_email text,
        whatsapp text, followers int, raw jsonb, capturado_em timestamptz DEFAULT now());""")
    cur.execute("""WITH h AS (
        SELECT instagram ig FROM prospeccao.resto_referencia WHERE instagram IS NOT NULL AND instagram<>''
        UNION SELECT cab_instagram FROM prospeccao.icp527_screen WHERE cab_instagram IS NOT NULL
        UNION SELECT cab_instagram FROM prospeccao.icp_media_screen WHERE cab_instagram IS NOT NULL
        UNION SELECT instagram FROM prospeccao.cabanha_extra WHERE instagram IS NOT NULL)
        SELECT DISTINCT lower(btrim(ig)) ig FROM h
        WHERE lower(btrim(ig)) NOT IN (SELECT username FROM prospeccao.ig_contato)
          AND ig !~ '^(p|explore|reel|reels|tv|accounts|stories)$'""")
    handles=[r['ig'] for r in cur.fetchall()]
    NSHARD=int(os.environ.get('NSHARD','1')); SHARD=int(os.environ.get('SHARD','0'))
    handles=[h for i,h in enumerate(handles) if i % NSHARD == SHARD]   # fatia disjunta
    LIM=int(os.environ.get('LIM','0'))
    if LIM: handles=handles[:LIM]
    if test: handles=handles[:3]
    print(f"[Apify IG: {len(handles)} handles{' (TESTE)' if test else ''}]", file=sys.stderr, flush=True)
    BATCH=50; wa=ph=em=0
    for i in range(0,len(handles),BATCH):
        chunk=handles[i:i+BATCH]
        try: items=run_apify(chunk)
        except Exception as e: print(f"  batch {i} ERRO {str(e)[:60]}", file=sys.stderr); continue
        if test: print("RAW keys de 1 item:", list(items[0].keys()) if items else "vazio", file=sys.stderr)
        for it in items:
            d=extrai(it)
            if not d['username']: continue
            wa+=bool(d['whatsapp']); ph+=bool(d['business_phone']); em+=bool(d['business_email'])
            cur.execute("""INSERT INTO prospeccao.ig_contato(username,bio,ext,business_phone,business_email,whatsapp,followers)
                VALUES(%(username)s,%(bio)s,%(ext)s,%(business_phone)s,%(business_email)s,%(whatsapp)s,%(followers)s)
                ON CONFLICT(username) DO UPDATE SET bio=EXCLUDED.bio,business_phone=EXCLUDED.business_phone,
                business_email=EXCLUDED.business_email,whatsapp=EXCLUDED.whatsapp""", d)
        print(f"  {min(i+BATCH,len(handles))}/{len(handles)} | wa {wa} · biz_phone {ph} · biz_email {em}", file=sys.stderr, flush=True)
        time.sleep(1)
    print(f"\n[FIM] WhatsApp {wa} · telefone-business {ph} · email-business {em}", file=sys.stderr, flush=True)
if __name__=="__main__": main()
