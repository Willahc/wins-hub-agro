#!/usr/bin/env python3
"""Expansão Hunter: fazendas de corte nacionais (estados pecuária) com DOMÍNIO PRÓPRIO LIMPO no
e-mail RFB (correio_eletronico) que o Hunter ainda não rodou. Alimenta com o OPERADOR JOVEM
(contato_candidatos, faixa 31-50) quando existe, senão o decisor_top. Prioriza ICP genética.
Grava em prospeccao.hunter_email (col `decisor`=nome usado, `status`=achado/vazio). Verificar depois.
Uso: docker exec -e HK=.. -e LIM=1600 python /app/hunter_finder_nacional.py"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.environ['HK']; LIMIT=int(os.environ.get('LIM','1600'))
DB=dict(host=os.environ.get('PGHOST','db'),port=int(os.environ.get('PGPORT','5432')),dbname="wins_agro",user="postgres",password=os.environ['PGPW'])
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
      WITH op AS (
        SELECT DISTINCT ON (cnpj_basico) cnpj_basico, nome
        FROM prospeccao.contato_candidatos WHERE faixa BETWEEN 3 AND 5
        ORDER BY cnpj_basico, score_alcancavel DESC, faixa
      ), dom AS (
        SELECT ld.cnpj_basico, ld.decisor_top,
               lower(split_part(e.correio_eletronico,'@',2)) AS d
        FROM prospeccao.lead_decisor ld
        JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico=ld.cnpj_basico
        WHERE ld.uf IN ('MT','MS','GO','PA','TO','MG','BA','RO')
          AND e.correio_eletronico IS NOT NULL AND e.correio_eletronico<>''
      )
      SELECT DISTINCT ON (dom.cnpj_basico)
             dom.cnpj_basico,
             COALESCE(op.nome, dom.decisor_top) AS nome,
             (op.nome IS NOT NULL) AS eh_operador,
             dom.d AS dominio,
             CASE pg.confianca WHEN 'alta' THEN 1 WHEN 'media' THEN 2 WHEN 'baixa' THEN 3 ELSE 9 END AS pri
      FROM dom
      LEFT JOIN op USING(cnpj_basico)
      LEFT JOIN prospeccao.prospect_genetica pg ON pg.cnpj_basico=dom.cnpj_basico
      WHERE dom.d<>'' AND dom.d NOT IN %(free)s
        AND dom.d !~ '(contab|assessor|advoc|advog|portaldbo|ancp|geneplus|selectsires|semex|serasa|\\.gov|\\.org\\.br|\\.mil)'
        AND dom.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_email)
        AND dom.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_operador)
        AND COALESCE(op.nome, dom.decisor_top) IS NOT NULL
      ORDER BY dom.cnpj_basico, pri
    """, {'free':FREE})
    rows=cur.fetchall()
    rows.sort(key=lambda r: r['pri'])   # ICP genética primeiro
    NSHARD=int(os.environ.get('NSHARD','1')); SHARD=int(os.environ.get('SHARD','0'))
    rows=[r for i,r in enumerate(rows) if i % NSHARD == SHARD][:LIMIT]   # fatia disjunta p/ paralelizar
    print(f"[Expansão Hunter: {len(rows)} fazendas (domínio próprio nacional, ICP-priorizado)]", file=sys.stderr, flush=True)
    achou=op_n=0
    with httpx.Client(timeout=25) as cl:
        for i,r in enumerate(rows,1):
            first,last=split_nome(r['nome'])
            if not first: continue
            em=sc=None; ok=False
            for t in range(3):
                try:
                    j=cl.get('https://api.hunter.io/v2/email-finder',params={'domain':r['dominio'],'first_name':first,'last_name':last,'api_key':KEY}).json()
                    em=j.get('data',{}).get('email'); sc=j.get('data',{}).get('score'); ok=True; break
                except Exception:
                    time.sleep(2*(t+1))
            if not ok:
                print(f"  {i} API falhou 3x — pulado", file=sys.stderr); continue
            if em: achou+=1
            if em and r['eh_operador']: op_n+=1
            cur.execute("""INSERT INTO prospeccao.hunter_email(cnpj_basico,decisor,dominio,email_decisor,score,status)
                VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET
                email_decisor=EXCLUDED.email_decisor,score=EXCLUDED.score,status=EXCLUDED.status,dominio=EXCLUDED.dominio""",
                (r['cnpj_basico'], r['nome'], r['dominio'], em, sc, ('achado_op' if r['eh_operador'] else 'achado') if em else 'vazio'))
            time.sleep(0.4)
            if i%50==0: print(f"  {i}/{len(rows)} | achados {achou} (operador {op_n})", file=sys.stderr, flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | e-mail: {achou} ({100*achou//n}%) | via operador {op_n}", file=sys.stderr, flush=True)
if __name__=="__main__": main()
