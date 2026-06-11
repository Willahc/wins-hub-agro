#!/usr/bin/env python3
"""Hunter Email Finder no ICP: domínio próprio + nome do decisor -> e-mail real do decisor + score.
Foca no buraco dos 23% (e-mail que NÃO é do decisor). Grava prospeccao.hunter_email."""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.environ['HK']; LIMIT=int(os.environ.get('LIM','99999'))
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['PGPW'])
SUF={'FILHO','FILHA','JUNIOR','NETO','NETA','SOBRINHO','JR'}
def split_nome(d):
    w=[x for x in re.sub(r'\(.*','',d or '').strip().split() if len(x)>1]
    if not w: return None,None
    first=w[0]; last=w[-1]
    if last.upper() in SUF and len(w)>=2: last=w[-2]
    return first,last
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.hunter_email(
        cnpj_basico varchar(8) PRIMARY KEY, decisor text, dominio text, email_decisor text, score int, status text, achado_em timestamptz DEFAULT now());""")
    cur.execute("""SELECT cnpj_basico, decisor, dom FROM (
      SELECT cnpj_basico, decisor, lower(split_part(email,'@',2)) AS dom FROM prospeccao.icp527_screen
      UNION ALL SELECT cnpj_basico, decisor, lower(split_part(email,'@',2)) FROM prospeccao.icp_media_screen) x
      WHERE decisor IS NOT NULL AND dom<>''
        AND dom NOT IN ('gmail.com','hotmail.com','outlook.com','yahoo.com.br','yahoo.com','live.com','bol.com.br','terra.com.br','uol.com.br','icloud.com')
        AND dom !~ '(contab|assessor|advoc|advog)'
        AND cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_email)
      ORDER BY cnpj_basico LIMIT %s""", (LIMIT,))
    rows=cur.fetchall()
    print(f"[Hunter finder em {len(rows)} leads (domínio próprio + decisor)]", file=sys.stderr, flush=True)
    achou=0
    with httpx.Client(timeout=25) as cl:
        for i,r in enumerate(rows,1):
            first,last=split_nome(r['decisor'])
            if not first: continue
            em=sc=None; ok_api=False
            for t in range(3):   # retry: falha de API != "vazio" (que é permanente)
                try:
                    j=cl.get('https://api.hunter.io/v2/email-finder',params={'domain':r['dom'],'first_name':first,'last_name':last,'api_key':KEY}).json()
                    em=j.get('data',{}).get('email'); sc=j.get('data',{}).get('score'); ok_api=True; break
                except Exception:
                    time.sleep(2*(t+1))
            if not ok_api:
                print(f"  {i} API falhou 3x — pulado (re-run tenta de novo)", file=sys.stderr); continue
            st='achado' if em else 'vazio'
            if em: achou+=1
            cur.execute("INSERT INTO prospeccao.hunter_email(cnpj_basico,decisor,dominio,email_decisor,score,status) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET email_decisor=EXCLUDED.email_decisor,score=EXCLUDED.score,status=EXCLUDED.status",
                        (r['cnpj_basico'], r['decisor'], r['dom'], em, sc, st))
            time.sleep(0.4)
            if i%20==0: print(f"  {i}/{len(rows)} | achados {achou}", file=sys.stderr, flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | e-mail do decisor achado: {achou} ({100*achou//n}%)", file=sys.stderr, flush=True)
if __name__=="__main__": main()
