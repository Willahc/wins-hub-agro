import os, json, psycopg2
DB={"host":os.getenv("DB_HOST","db"),"port":int(os.getenv("DB_PORT",5432)),"dbname":os.getenv("POSTGRES_DB","wins_agro"),"user":os.getenv("POSTGRES_USER","postgres"),"password":os.getenv("POSTGRES_PASSWORD","")}
conn=psycopg2.connect(**DB); cur=conn.cursor()
cur.execute("SELECT id FROM catalogo.caracteristica WHERE sigla='IDX_CARC_PROMEBO'"); CARC=cur.fetchone()[0]
ALVO=[CARC,20]; nr=na=0
for b in json.load(open("/app/angus_bulls.json")):
    cur.execute("""INSERT INTO mercado.reprodutor (registro,nome,especie_codigo,raca_id,fonte_referencia,fonte_programa,coletado_em)
      VALUES (%s,%s,'BOV',9,%s,'promebo',now())
      ON CONFLICT (registro,raca_id) DO UPDATE SET nome=EXCLUDED.nome,fonte_referencia=EXCLUDED.fonte_referencia,fonte_programa=EXCLUDED.fonte_programa
      RETURNING id""",(b["registro"],b["nome"],"Sumário Angus ANC/PROMEBO 2018/19 (PDF)"))
    rid=cur.fetchone()[0]; nr+=1
    cur.execute("DELETE FROM mercado.avaliacao WHERE reprodutor_id=%s AND caracteristica_id=ANY(%s)",(rid,ALVO))
    for cid in ALVO:
        cur.execute("INSERT INTO mercado.avaliacao (reprodutor_id,caracteristica_id,valor,coletado_em) VALUES (%s,%s,%s,now())",(rid,cid,b["carcaca"])); na+=1
conn.commit(); print(f"Angus: {nr} reprodutores, {na} avaliações"); conn.close()
