#!/usr/bin/env python3
"""Gasta o budget Hunter restante (~635) nos MELHORES domínios próprios limpos do RFB ainda não
rodados (nacional): ordena por sinal genético > capital, e-mail-finder no domínio + operador/decisor.
Grava em prospeccao.hunter_email (entra na view de entrega). LIM global = teto de créditos.
Uso: docker run ... --env-file .env --env-file .env.hk -e LIM=630 hunterpy python /s/hunter_rfb.py"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.environ['HK']; LIMIT=int(os.environ.get('LIM','630'))
DB=dict(host=os.environ.get('PGHOST','db'),dbname="wins_agro",user="postgres",password=os.environ.get('PGPW') or os.environ['POSTGRES_PASSWORD'])
SUF={'FILHO','FILHA','JUNIOR','NETO','NETA','SOBRINHO','JR'}
FREE=('gmail.com','hotmail.com','outlook.com','yahoo.com.br','yahoo.com','live.com','bol.com.br','terra.com.br','uol.com.br','icloud.com')
def split_nome(d):
    w=[x for x in re.sub(r'\(.*','',d or '').strip().split() if len(x)>1]
    if not w: return None,None
    first=w[0]; last=w[-1]
    if last.upper() in SUF and len(w)>=2: last=w[-2]
    return first,last
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
      WITH op AS (SELECT DISTINCT ON (cnpj_basico) cnpj_basico, nome FROM prospeccao.contato_candidatos
                  WHERE faixa BETWEEN 3 AND 5 ORDER BY cnpj_basico, score_alcancavel DESC, faixa)
      SELECT ld.cnpj_basico, COALESCE(op.nome, ld.decisor_top) AS nome,
             (op.nome IS NOT NULL) eh_op, lower(split_part(e.correio_eletronico,'@',2)) dom,
             CASE pg.confianca WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baixa' THEN 3 ELSE 9 END pri,
             em.capital_social cap
      FROM prospeccao.lead_decisor ld
      JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico=ld.cnpj_basico
      JOIN cnpj.empresa_rural em ON em.cnpj_basico=ld.cnpj_basico
      LEFT JOIN op ON op.cnpj_basico=ld.cnpj_basico
      LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico=ld.cnpj_basico
      WHERE e.correio_eletronico ~ '@'
        AND lower(split_part(e.correio_eletronico,'@',2)) NOT IN %(free)s
        AND lower(split_part(e.correio_eletronico,'@',2)) !~ '(contab|assessor|advoc|advog|portaldbo|ancp|geneplus|selectsires|semex|serasa|\.gov|\.org\.br|\.mil)'
        AND COALESCE(op.nome, ld.decisor_top) ~ '\S\s+\S'
        AND em.capital_social < 150000000
        AND ld.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_email)
        AND ld.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_operador)
        AND ld.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_resto)
      ORDER BY pri, em.capital_social DESC NULLS LAST
    """, {'free':FREE})
    rows=cur.fetchall()
    NSHARD=int(os.environ.get('NSHARD','1')); SHARD=int(os.environ.get('SHARD','0'))
    rows=[r for i,r in enumerate(rows) if i % NSHARD == SHARD][:LIMIT]
    print(f"[Hunter RFB nacional: {len(rows)} | shard {SHARD}/{NSHARD} | LIM={LIMIT}]", file=sys.stderr, flush=True)
    achou=0; consec_fail=0
    with httpx.Client(timeout=25) as cl:
        for i,r in enumerate(rows,1):
            first,last=split_nome(r['nome'])
            if not first: continue
            em=sc=None; ok=False; credit_out=False
            for t in range(4):
                try:
                    j=cl.get('https://api.hunter.io/v2/email-finder',params={'domain':r['dom'],'first_name':first,'last_name':last,'api_key':KEY}).json()
                    errs=j.get('errors')
                    if errs:
                        msg=str(errs).lower()
                        if 'credit' in msg or 'upgrade' in msg or 'reach' in msg: credit_out=True; break
                        time.sleep(3*(t+1)); continue   # rate-limit/transitório -> retry
                    d=j.get('data',{}); em=d.get('email'); sc=d.get('score'); ok=True; break
                except Exception:
                    time.sleep(2*(t+1))
            if credit_out:
                print(f"  créditos Hunter esgotados em {i} — parando", file=sys.stderr); break
            if not ok:
                consec_fail+=1
                if consec_fail>=10:
                    print(f"  10 falhas seguidas — parando (provável limite)", file=sys.stderr); break
                continue
            consec_fail=0
            if em: achou+=1
            cur.execute("""INSERT INTO prospeccao.hunter_email(cnpj_basico,decisor,dominio,email_decisor,score,status)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET email_decisor=EXCLUDED.email_decisor,
                score=EXCLUDED.score,status=EXCLUDED.status,dominio=EXCLUDED.dominio""",
                (r['cnpj_basico'], r['nome'], r['dom'], em, sc, ('achado_op' if r['eh_op'] else 'achado') if em else 'vazio'))
            time.sleep(0.3)
            if i%50==0: print(f"  {i}/{len(rows)} | achados {achou}", file=sys.stderr, flush=True)
    print(f"\n[FIM] {len(rows)} | e-mail: {achou}", file=sys.stderr, flush=True)
if __name__=="__main__": main()
