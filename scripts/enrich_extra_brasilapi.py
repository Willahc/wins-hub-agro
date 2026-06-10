import os,re,sys,time
import psycopg2,psycopg2.extras,httpx
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['POSTGRES_PASSWORD'])
QUALS=("Administrador","Sócio-Administrador","Sócio","Presidente","Diretor","Titular","Proprietário")
HOLD=(" S/A"," S.A","PARTICIPAC","HOLDING","EMPREEND"," FUNDO")
def pessoa(n): u=(n or "").upper(); return not any(h in u for h in HOLD)
def qsa(client,c):
    for a in range(4):
        try:
            r=client.get(f"https://brasilapi.com.br/api/cnpj/v1/{c}",timeout=20)
            if r.status_code==429: time.sleep(4+a*4); continue
            if r.status_code!=200: return None
            return r.json()
        except Exception: time.sleep(2)
    return None
conn=psycopg2.connect(**DB);conn.autocommit=True
cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
for col in ("razao_social","decisor","situacao"):
    cur.execute(f"ALTER TABLE prospeccao.cabanha_extra ADD COLUMN IF NOT EXISTS {col} text;")
cur.execute("""SELECT ce.cabanha, ce.cnpj14 FROM prospeccao.cabanha_extra ce
  LEFT JOIN prospeccao.lead_decisor ld ON ld.cnpj_basico=left(ce.cnpj14,8)
  WHERE ce.cnpj14 IS NOT NULL AND ld.cnpj_basico IS NULL AND ce.razao_social IS NULL""")
rows=cur.fetchall()
print(f"[BrasilAPI em {len(rows)} cabanhas fora da base corte]",file=sys.stderr,flush=True)
hit=0
with httpx.Client(headers={"User-Agent":"wins-agro/extra"}) as cl:
    for i,r in enumerate(rows,1):
        d=qsa(cl,r["cnpj14"]); time.sleep(0.7)
        if not d:
            cur.execute("UPDATE prospeccao.cabanha_extra SET situacao='erro' WHERE cabanha=%s",(r["cabanha"],)); continue
        decis=[]
        for s in (d.get("qsa") or []):
            nm=(s.get("nome_socio") or "").strip(); ql=(s.get("qualificacao_socio") or "").strip()
            if nm and pessoa(nm) and any(q in ql for q in QUALS): decis.append(f"{nm} ({ql})")
        top=next((x for x in decis if "dminist" in x or "Presid" in x or "Diret" in x), decis[0] if decis else None)
        if top: hit+=1
        cur.execute("UPDATE prospeccao.cabanha_extra SET razao_social=%s,decisor=%s,situacao=%s WHERE cabanha=%s",
            (d.get("razao_social"), top, d.get("descricao_situacao_cadastral"), r["cabanha"]))
        if i%30==0: print(f"  {i}/{len(rows)} decisor {hit}",file=sys.stderr,flush=True)
print(f"\n[FIM] {len(rows)} | com decisor {hit}",file=sys.stderr,flush=True)
