#!/usr/bin/env python3
"""Carrega touros do Sumário ANCP 2024 (Nelore/Guzerá/Brahman/Tabapuã/Sindi) em mercado.reprodutor.
Fonte nacional grátis que faltava (ANCP=0 antes). Parseia SÓ as tabelas 'SUMÁRIO GERAL DE TOUROS DA
RAÇA X (TOP 15% MGTe)' do PDF (-layout), onde MGTe é a última coluna. Dedup por (registro,raca_id).
MGTe vai pra mercado.avaliacao (caracteristica 'MGTe (ANCP)'). Texto em /tmp/ancp.txt (pdftotext -layout).
Uso: docker exec -i wins_agro_v1_api_1 python - < scripts/load_ancp.py"""
import re, os, psycopg2, psycopg2.extras
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.getenv("POSTGRES_PASSWORD",""))
URL="https://www.ancp.org.br/wp/wp-content/uploads/2024/08/Sumario-ANCP-2024.pdf"
RACA={'NELORE':1,'GUZERA':4,'GUZERÁ':4,'BRAHMAN':2,'TABAPUA':7,'TABAPUÃ':7,'SINDI':6}
# RG  mês/ano  NOME  G  PAI_RG  <números...MGTe(VAL AC TOP)>
ROW=re.compile(r'^\s*([A-Z]{2,6}\s+[A-Z]?\d{1,6})\s+(\d{2}/\d{2})\s+(.+?)\s+G\s+([A-Z]{2,6}\s+[A-Z]?\d{1,6})\s+([\d].*\d.*)$')
HDR=re.compile(r'DE TOUROS\b.*?DA RA[ÇC]A\s+([A-ZÃÁÉ]+)')   # tabelas de touros (geral E líderes)
def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    for seq,tbl in [('mercado.reprodutor_id_seq','mercado.reprodutor'),
                    ('mercado.avaliacao_id_seq','mercado.avaliacao')]:
        cur.execute(f"SELECT setval('{seq}', GREATEST((SELECT max(id) FROM {tbl}),1))")
    cur.execute("SELECT id FROM catalogo.caracteristica WHERE nome='MGTe (ANCP)'")
    r=cur.fetchone()
    if r: carac=r['id']
    else:
        cur.execute("SELECT setval('catalogo.caracteristica_id_seq', GREATEST((SELECT max(id) FROM catalogo.caracteristica), 1))")
        cur.execute("INSERT INTO catalogo.caracteristica(sigla,nome,unidade) VALUES('MGTe','MGTe (ANCP)','pts') RETURNING id")
        carac=cur.fetchone()['id']
    rows=[]; in_tab=False; is_gen=False; raca=None
    for ln in open('/tmp/ancp.txt', encoding='utf-8', errors='ignore'):
        h=HDR.search(ln)
        if h:
            nm=h.group(1).upper().replace('Á','A').replace('Ã','A').replace('É','E')
            raca=RACA.get(nm) or RACA.get(h.group(1).upper())
            in_tab=raca is not None; is_gen=('GERAL DE TOUROS' in ln); continue
        # sai da seção de touros ao bater em outra grande seção (matriz/jovens/intro)
        if re.search(r'MATRIZ|FÊMEAS|FEMEAS|MACHOS JOVENS|ÍNDICE DE SELE', ln, re.I):
            in_tab=False
        if not (in_tab and raca): continue
        m=ROW.match(ln.rstrip())
        if not m: continue
        rg=re.sub(r'\s+',' ',m.group(1)).strip()
        nome=re.sub(r'\s+',' ',m.group(3)).strip(); pai=re.sub(r'\s+',' ',m.group(4)).strip()
        toks=m.group(5).split()
        if len(toks)<3: continue
        mgte=perc=None
        if is_gen:   # MGTe só é a última coluna na tabela GERAL
            try:
                v=float(toks[-3].replace(',','.'))
                if -50<v<200: mgte=v
                p=toks[-1].replace('%','').replace(',','.'); perc=float(p)
            except ValueError: pass
        rows.append((rg,nome,raca,pai,mgte,perc))
    # dedup no arquivo por (rg,raca): mantém a entrada COM mgte se houver
    best={}
    for x in rows:
        k=(x[0],x[2])
        if k not in best or (x[4] is not None and best[k][4] is None): best[k]=x
    uniq=list(best.values())
    novo=0; mgte_ins=0
    for rg,nome,raca,pai,mgte,perc in uniq:
        cur.execute("""INSERT INTO mercado.reprodutor
            (registro,nome,especie_codigo,raca_id,sexo,pai_registro,fonte_programa,fonte_referencia,fonte_url,fonte_evidencia)
            VALUES(%s,%s,'BOV',%s,'M',%s,'ancp','Sumário ANCP 2024-2',%s,%s)
            ON CONFLICT (registro,raca_id) DO NOTHING RETURNING id""",
            (rg,nome[:200],raca,pai,URL,(f'MGTe={mgte}' if mgte is not None else 'ANCP líder')))
        g=cur.fetchone()
        if g:
            novo+=1
            if mgte is not None:
                cur.execute("INSERT INTO mercado.avaliacao(reprodutor_id,caracteristica_id,valor,percentil) VALUES(%s,%s,%s,%s)",
                            (g['id'],carac,mgte,perc)); mgte_ins+=1
    # relatório por raça
    cur.execute("""SELECT ra.nome, count(*) FROM mercado.reprodutor r JOIN catalogo.raca ra ON ra.id=r.raca_id
                   WHERE r.fonte_programa='ancp' GROUP BY ra.nome ORDER BY 2 DESC""")
    print(f"[ANCP] linhas parseadas={len(rows)} unicas={len(uniq)} | NOVOS reprodutores={novo} | MGTe inseridos={mgte_ins}")
    for x in cur.fetchall(): print(f"  {x['nome']}: {x['count']}")
if __name__=="__main__": main()
