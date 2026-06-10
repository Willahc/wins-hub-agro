import os,re,sys,time
import psycopg2,psycopg2.extras,httpx
KEY=os.environ['SERPER_API_KEY']
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.environ['POSTGRES_PASSWORD'])
IG_BAD={"p","reel","reels","explore","tv","accounts","stories","about"}
RE_IG=re.compile(r'instagram\.com/([A-Za-z0-9_.]{3,30})')
RE_TEL=re.compile(r'\(?\d{2}\)?\s?9\d{4}[-\s]?\d{4}')
SOCIAL=('instagram.com','facebook.com','youtube.com','econodata','cnpj','consultasocio')
def serper(q):
    r=httpx.post("https://google.serper.dev/search",headers={"X-API-KEY":KEY,"Content-Type":"application/json"},json={"q":q,"gl":"br","hl":"pt","num":10},timeout=20);r.raise_for_status();return r.json()
conn=psycopg2.connect(**DB);conn.autocommit=True
cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
cur.execute("SELECT cabanha FROM prospeccao.cabanha_extra WHERE instagram IS NULL ORDER BY touros_nelore DESC")
rows=cur.fetchall()
print(f"[harvest {len(rows)} cabanhas extra]",file=sys.stderr,flush=True)
hi=hc=0
for i,r in enumerate(rows,1):
    try:
        j=serper(f'"{r["cabanha"]}" nelore (instagram OR contato OR fazenda OR touros)')
        blob=" ".join(o.get("title","")+" "+o.get("snippet","")+" "+o.get("link","") for o in j.get("organic",[]))
        ig=next((h for h in RE_IG.findall(blob) if h.lower() not in IG_BAD),None)
        cels=[re.sub(r'\D','',c) for c in RE_TEL.findall(blob)]
        cel=cels[0] if cels else None
        site=next((o.get("link") for o in j.get("organic",[]) if o.get("link") and not any(s in o["link"] for s in SOCIAL)),None)
    except Exception: ig=cel=site=None
    hi+=bool(ig);hc+=bool(cel)
    cur.execute("UPDATE prospeccao.cabanha_extra SET instagram=%s,celular=%s,site=%s WHERE cabanha=%s",(ig,cel,site,r["cabanha"]))
    time.sleep(0.35)
    if i%40==0: print(f"  {i}/{len(rows)} IG {hi} cel {hc}",file=sys.stderr,flush=True)
n=len(rows) or 1
print(f"\n[FIM] {len(rows)} | Instagram {hi} ({100*hi//n}%) celular {hc}",file=sys.stderr,flush=True)
