#!/usr/bin/env python3
"""Hunter no OPERADOR JOVEM (não o decisor registrado): domínio PRÓPRIO da fazenda + nome do
operador (faixa 31-50, top de prospeccao.contato_candidatos) -> e-mail pessoal dele no domínio.
Domínio vem do PRÓPRIO e-mail da fazenda (icp527/icp_media) = limpo por construção (não é o `site`
contaminado dos studs). Grava em tabela SEPARADA prospeccao.hunter_operador (não sobrescreve o decisor).
Uso: docker exec -e HK=.. wins_agro_v1_api_1 python /app/hunter_finder_operador.py [N]"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.environ['HK']; LIMIT=int(os.environ.get('LIM','99999'))
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['PGPW'])
SUF={'FILHO','FILHA','JUNIOR','NETO','NETA','SOBRINHO','JR'}
FREE={'gmail.com','hotmail.com','outlook.com','yahoo.com.br','yahoo.com','live.com','bol.com.br','terra.com.br','uol.com.br','icloud.com'}
def split_nome(d):
    w=[x for x in re.sub(r'\(.*','',d or '').strip().split() if len(x)>1]
    if not w: return None,None
    first=w[0]; last=w[-1]
    if last.upper() in SUF and len(w)>=2: last=w[-2]
    return first,last
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.hunter_operador(
        cnpj_basico varchar(8) PRIMARY KEY, operador text, faixa int, dominio text,
        email_operador text, score int, status text, achado_em timestamptz DEFAULT now());""")
    cur.execute("""
      WITH dom AS (
        SELECT cnpj_basico, lower(split_part(email,'@',2)) dom FROM prospeccao.icp527_screen
        UNION ALL SELECT cnpj_basico, lower(split_part(email,'@',2)) FROM prospeccao.icp_media_screen
      ), domc AS (
        SELECT DISTINCT ON (cnpj_basico) cnpj_basico, dom FROM dom
        WHERE dom<>'' AND dom NOT IN %(free)s AND dom !~ '(contab|assessor|advoc|advog)'
      ), op AS (
        SELECT DISTINCT ON (cnpj_basico) cnpj_basico, nome, faixa
        FROM prospeccao.contato_candidatos
        WHERE faixa BETWEEN 3 AND 5
        ORDER BY cnpj_basico, score_alcancavel DESC, faixa
      )
      SELECT d.cnpj_basico, o.nome AS operador, o.faixa, d.dom
      FROM domc d JOIN op o USING(cnpj_basico)
      WHERE d.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.hunter_operador)
      ORDER BY d.cnpj_basico LIMIT %(lim)s""", {'free':tuple(FREE),'lim':LIMIT})
    rows=cur.fetchall()
    print(f"[Hunter no operador jovem: {len(rows)} fazendas (domínio próprio + operador 31-50)]", file=sys.stderr, flush=True)
    achou=0
    with httpx.Client(timeout=25) as cl:
        for i,r in enumerate(rows,1):
            first,last=split_nome(r['operador'])
            if not first: continue
            em=sc=None; ok_api=False
            for t in range(3):
                try:
                    j=cl.get('https://api.hunter.io/v2/email-finder',params={'domain':r['dom'],'first_name':first,'last_name':last,'api_key':KEY}).json()
                    em=j.get('data',{}).get('email'); sc=j.get('data',{}).get('score'); ok_api=True; break
                except Exception:
                    time.sleep(2*(t+1))
            if not ok_api:
                print(f"  {i} API falhou 3x — pulado", file=sys.stderr); continue
            if em: achou+=1
            cur.execute("""INSERT INTO prospeccao.hunter_operador(cnpj_basico,operador,faixa,dominio,email_operador,score,status)
                VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET
                email_operador=EXCLUDED.email_operador,score=EXCLUDED.score,status=EXCLUDED.status""",
                (r['cnpj_basico'], r['operador'], r['faixa'], r['dom'], em, sc, 'achado' if em else 'vazio'))
            time.sleep(0.4)
            if i%20==0: print(f"  {i}/{len(rows)} | achados {achou}", file=sys.stderr, flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | e-mail do operador: {achou} ({100*achou//n}%)", file=sys.stderr, flush=True)
if __name__=="__main__": main()
