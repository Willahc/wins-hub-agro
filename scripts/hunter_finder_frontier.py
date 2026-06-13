#!/usr/bin/env python3
"""Última fronteira Hunter (jun/13, fechamento do enriquecimento). Lê prospeccao.hunter_frontier_todo
(montada por build_hunter_frontier.sql) e roda o email-finder no domínio próprio limpo.
Grava em prospeccao.hunter_email (status achado/achado_op/vazio); verificar depois com hunter_verify.py.

Default: SÓ fonte in-ICP (cabanha_extra_icp, 15) — o que vale p/ Monte Sião.
Para incluir o opt-in fora do ICP (SP/PR/RS/ES cap>=5M, 260):  -e FONTE=todas

Uso (worker container, ver gotcha #11 da infra):
  docker run -d --name hfront --network wins_agro_v1_default -v /root/wins_agro_v1/scripts:/s \
    -e HK=<hunter_key> -e PGPW=<senha_api_32> -e PGHOST=db hunterpy python /s/hunter_finder_frontier.py
"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.environ['HK']; LIMIT=int(os.environ.get('LIM','2000'))
FONTE=os.environ.get('FONTE','icp')   # 'icp' => só cabanha_extra_icp ; 'todas' => tudo
DB=dict(host=os.environ.get('PGHOST','db'),port=int(os.environ.get('PGPORT','5432')),dbname="wins_agro",user="postgres",password=os.environ['PGPW'])
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
    where = "fonte='cabanha_extra_icp'" if FONTE=='icp' else "TRUE"
    cur.execute(f"""SELECT cnpj_basico, nome, dominio, eh_operador, pri
                    FROM prospeccao.hunter_frontier_todo
                    WHERE {where}
                      AND cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_email)
                    ORDER BY pri, capital_mi DESC NULLS LAST""")
    rows=cur.fetchall()
    NSHARD=int(os.environ.get('NSHARD','1')); SHARD=int(os.environ.get('SHARD','0'))
    rows=[r for i,r in enumerate(rows) if i % NSHARD == SHARD][:LIMIT]
    print(f"[Fronteira Hunter: {len(rows)} fazendas | FONTE={FONTE}]", file=sys.stderr, flush=True)
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
            if i%25==0: print(f"  {i}/{len(rows)} | achados {achou}", file=sys.stderr, flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | e-mail: {achou} ({100*achou//n}%) | operador {op_n}", file=sys.stderr, flush=True)
    print("  -> verificar: hunter_verify.py ; reconstruir entrega: build_entrega_hunter.sql", file=sys.stderr)
if __name__=="__main__": main()
