#!/usr/bin/env python3
"""'O RESTO' dos operadores jovens sem domínio próprio (jun/13). Usa Hunter email-finder com
`company` (razão social) em vez de `domain` — o Hunter resolve o domínio da empresa sozinho.
Lê prospeccao.hunter_resto_todo (build_hunter_resto.sql), prioriza por sinal genético/capital.
Grava em prospeccao.hunter_resto (tabela separada; NÃO mistura com o canal de domínio próprio,
pois aqui o domínio é INFERIDO pelo Hunter, qualidade diferente). Verificar depois.

⚠️ Hit-rate DESCONHECIDO e provavelmente baixo: fazenda que usa gmail normalmente NÃO tem domínio
corporativo p/ o Hunter achar (mesma parede estrutural do WhatsApp). RODAR PRIMEIRO UM TESTE
(LIM=100, melhor sinal) e medir antes de gastar o budget (~1.255 buscas, reseta 11/jul).

Uso (worker container, ver gotcha #11):
  PGPW=$(docker exec wins_agro_v1_api_1 printenv POSTGRES_PASSWORD)
  docker run -d --name hresto --network wins_agro_v1_default -v /root/wins_agro_v1/scripts:/s \
    -e HK=<chave> -e PGPW="$PGPW" -e PGHOST=db -e LIM=100 hunterpy python /s/hunter_finder_resto.py
"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.environ['HK']; LIMIT=int(os.environ.get('LIM','100'))
MAXPRI=int(os.environ.get('MAXPRI','3'))   # 1=alta 2=media 3=baixa 4=descartar 5=sem sinal
DB=dict(host=os.environ.get('PGHOST','db'),port=int(os.environ.get('PGPORT','5432')),dbname="wins_agro",user="postgres",password=os.environ.get('PGPW') or os.environ['POSTGRES_PASSWORD'])
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
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.hunter_resto(
        cnpj_basico varchar(8) PRIMARY KEY, operador text, company_hint text,
        dominio_resolvido text, email_operador text, score int, sinal text,
        status text, verif_status text, achado_em timestamptz DEFAULT now());""")
    # default: SÓ fazendas com DOMÍNIO REAL colhido no Serper (resto_referencia.dominio_cand) -> usa `domain`.
    # COMPANY=1: cai pra company-resolution (razão) nas que não têm domínio colhido (qualidade baixa).
    USE_COMPANY=os.environ.get('COMPANY','0')=='1'
    join_dom = "LEFT JOIN" if USE_COMPANY else "JOIN"
    cur.execute(f"""SELECT t.cnpj_basico, t.operador, t.company_hint, t.sinal, t.pri, rr.dominio_cand
                   FROM prospeccao.hunter_resto_todo t
                   {join_dom} prospeccao.resto_referencia rr
                     ON rr.cnpj_basico=t.cnpj_basico AND rr.dominio_cand IS NOT NULL
                   WHERE t.pri <= %(mp)s
                     AND t.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_resto)
                   ORDER BY (rr.dominio_cand IS NOT NULL) DESC, t.pri, t.capital_mi DESC NULLS LAST""", {'mp':MAXPRI})
    rows=cur.fetchall()
    NSHARD=int(os.environ.get('NSHARD','1')); SHARD=int(os.environ.get('SHARD','0'))
    rows=[r for i,r in enumerate(rows) if i % NSHARD == SHARD][:LIMIT]
    print(f"[Resto Hunter: {len(rows)} | domínio-colhido prioritário | COMPANY-fallback={USE_COMPANY} | LIM={LIMIT}]", file=sys.stderr, flush=True)
    achou=0
    with httpx.Client(timeout=25) as cl:
        for i,r in enumerate(rows,1):
            first,last=split_nome(r['operador'])
            if not first: continue
            em=sc=dom=None; ok=False
            params={'first_name':first,'last_name':last,'api_key':KEY}
            if r.get('dominio_cand'): params['domain']=r['dominio_cand']   # domínio real colhido = melhor
            else:                     params['company']=r['company_hint']  # fallback resolução
            for t in range(3):
                try:
                    j=cl.get('https://api.hunter.io/v2/email-finder',params=params).json()
                    d=j.get('data',{}); em=d.get('email'); sc=d.get('score'); dom=d.get('domain'); ok=True; break
                except Exception:
                    time.sleep(2*(t+1))
            if not ok:
                print(f"  {i} API falhou 3x — pulado", file=sys.stderr); continue
            if em: achou+=1
            cur.execute("""INSERT INTO prospeccao.hunter_resto(cnpj_basico,operador,company_hint,dominio_resolvido,email_operador,score,sinal,status)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET
                email_operador=EXCLUDED.email_operador,score=EXCLUDED.score,dominio_resolvido=EXCLUDED.dominio_resolvido,status=EXCLUDED.status""",
                (r['cnpj_basico'], r['operador'], r['company_hint'], dom, em, sc, r['sinal'],
                 'achado' if em else ('sem_dominio' if not dom else 'vazio')))
            time.sleep(0.4)
            if i%25==0: print(f"  {i}/{len(rows)} | achados {achou} ({100*achou//i}%)", file=sys.stderr, flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | e-mail: {achou} ({100*achou//n}%)", file=sys.stderr, flush=True)
    print("  Se hit-rate util (>5%): escalar (subir LIM/MAXPRI). Senao: parede estrutural confirmada, parar.", file=sys.stderr)
if __name__=="__main__": main()
