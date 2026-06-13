#!/usr/bin/env python3
"""Hunter email-verifier nos e-mails JÁ achados (decisor + operador): confirma deliverability
e separa os chutes de padrão (status 'outra_empresa') dos mailboxes REAIS. Grava verif_status.
Throttle 1.4s (Starter rate-limita forte). Uso: docker exec -e HK=.. python /app/hunter_verify.py"""
import os, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.environ['HK']
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ.get('PGPW') or os.environ['POSTGRES_PASSWORD'])
def verify(cl, email):
    for t in range(3):
        try:
            j=cl.get('https://api.hunter.io/v2/email-verifier',params={'email':email,'api_key':KEY}).json()
            d=j.get('data',{})
            return d.get('status'), d.get('result'), d.get('score')
        except Exception:
            time.sleep(2*(t+1))
    return None,None,None
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("ALTER TABLE prospeccao.hunter_operador ADD COLUMN IF NOT EXISTS verif_status text")
    cur.execute("ALTER TABLE prospeccao.hunter_resto ADD COLUMN IF NOT EXISTS verif_status text")
    cur.execute("ALTER TABLE prospeccao.site_contato ADD COLUMN IF NOT EXISTS verif_status text")
    # une as fontes (inclui e-mail raspado do site = 1º da lista)
    cur.execute("""
      SELECT 'hunter_email' AS tbl, cnpj_basico, email_decisor AS email FROM prospeccao.hunter_email
        WHERE email_decisor IS NOT NULL AND email_decisor<>'' AND verif_status IS NULL
      UNION ALL
      SELECT 'hunter_operador', cnpj_basico, email_operador FROM prospeccao.hunter_operador
        WHERE email_operador IS NOT NULL AND email_operador<>'' AND verif_status IS NULL
      UNION ALL
      SELECT 'hunter_resto', cnpj_basico, email_operador FROM prospeccao.hunter_resto
        WHERE email_operador IS NOT NULL AND email_operador<>'' AND verif_status IS NULL
      UNION ALL
      SELECT 'site_contato', cnpj_basico, split_part(emails,',',1) FROM prospeccao.site_contato
        WHERE emails IS NOT NULL AND emails<>'' AND verif_status IS NULL""")
    rows=cur.fetchall()
    NSHARD=int(os.environ.get('NSHARD','1')); SHARD=int(os.environ.get('SHARD','0'))
    rows=[r for i,r in enumerate(rows) if i % NSHARD == SHARD]   # fatia disjunta p/ paralelizar
    print(f"[verificando {len(rows)} e-mails | shard {SHARD}/{NSHARD}]", file=sys.stderr, flush=True)
    tally={}
    with httpx.Client(timeout=25) as cl:
        for i,r in enumerate(rows,1):
            st,res,sc=verify(cl, r['email'])
            tag=st or 'erro'; tally[tag]=tally.get(tag,0)+1
            col='email_decisor' if r['tbl']=='hunter_email' else 'email_operador'
            cur.execute(f"UPDATE prospeccao.{r['tbl']} SET verif_status=%s WHERE cnpj_basico=%s",(st,r['cnpj_basico']))
            time.sleep(1.4)
            if i%20==0: print(f"  {i}/{len(rows)} | {tally}", file=sys.stderr, flush=True)
    print(f"\n[FIM] {len(rows)} verificados | {tally}", file=sys.stderr, flush=True)
if __name__=="__main__": main()
