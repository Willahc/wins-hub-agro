import os,re,sys,time,unicodedata
import psycopg2,psycopg2.extras,httpx
KEY=os.environ['SERPER_API_KEY']
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['POSTGRES_PASSWORD'])
RE_CNPJ=re.compile(r'(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})')
def strip_ac(s): return unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode().upper()
def toks(cab):
    return {t for t in re.sub(r'[^A-Z0-9 ]',' ',strip_ac(cab)).split() if len(t)>3 and t not in ('FAZENDA','AGROPECUARIA','NELORE','RANCHO')}
def serper(q):
    r=httpx.post("https://google.serper.dev/search",headers={"X-API-KEY":KEY,"Content-Type":"application/json"},json={"q":q,"gl":"br","hl":"pt","num":10},timeout=20);r.raise_for_status();return r.json()
conn=psycopg2.connect(**DB);conn.autocommit=True
cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
for c in ("cnpj14","cnpj_fonte"):
    cur.execute(f"ALTER TABLE prospeccao.cabanha_extra ADD COLUMN IF NOT EXISTS {c} text;")
cur.execute("SELECT cabanha FROM prospeccao.cabanha_extra WHERE cnpj14 IS NULL ORDER BY touros_nelore DESC")
rows=cur.fetchall()
print(f"[buscando CNPJ de {len(rows)} cabanhas]",file=sys.stderr,flush=True)
hit=0
for i,r in enumerate(rows,1):
    cab=r["cabanha"]; tk=toks(cab); cnpj=fonte=None
    try:
        j=serper(f'"{cab}" (nelore OR agropecuaria OR fazenda) (cnpj OR econodata OR "razão social")')
        for o in j.get("organic",[]):
            txt=o.get("title","")+" "+o.get("snippet","")
            up=strip_ac(txt)
            m=RE_CNPJ.search(txt)
            if m and (not tk or any(t in up for t in tk)):   # CNPJ + cita a cabanha
                cnpj=re.sub(r'\D','',m.group(1)); fonte=o.get("link",""); break
    except Exception: pass
    if cnpj: hit+=1
    cur.execute("UPDATE prospeccao.cabanha_extra SET cnpj14=%s,cnpj_fonte=%s WHERE cabanha=%s",(cnpj,fonte,cab))
    time.sleep(0.35)
    if i%40==0: print(f"  {i}/{len(rows)} CNPJ-hit {hit}",file=sys.stderr,flush=True)
print(f"\n[FIM] {len(rows)} | CNPJ encontrado {hit}",file=sys.stderr,flush=True)
