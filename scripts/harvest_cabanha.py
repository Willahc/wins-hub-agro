#!/usr/bin/env python3
"""CRACK do gap de contato: busca o ICP genético (527) pelo NOME DA CABANHA (do catálogo, não a
razão social) → acha Instagram + WhatsApp/celular. Teste deu 80% (vs 0% pela razão), porque a
cabanha existe online pelo nome de marca/prefixo. Celular com DDD da fazenda = alta confiança.
Roda c/ SERPER_API_KEY no env."""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx

KEY=os.getenv("SERPER_API_KEY","").strip()
if not KEY: print("FALTA SERPER_API_KEY",file=sys.stderr); sys.exit(2)
DB=dict(host=os.getenv("DB_HOST","db"),port=int(os.getenv("DB_PORT",5432)),dbname=os.getenv("POSTGRES_DB","wins_agro"),
        user=os.getenv("POSTGRES_USER","postgres"),password=os.getenv("POSTGRES_PASSWORD",""))
IG_BAD={"p","reel","reels","explore","tv","accounts","stories","about"}
RE_IG=re.compile(r'instagram\.com/([A-Za-z0-9_.]{3,30})')
RE_WA=re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d{10,13})',re.I)
RE_TEL=re.compile(r'\(?\d{2}\)?\s?9\d{4}[-\s]?\d{4}')
SOCIAL=('instagram.com','facebook.com','linkedin.com','youtube.com','econodata','cnpj','consultasocio','escavador')

def serper(q):
    r=httpx.post("https://google.serper.dev/search",headers={"X-API-KEY":KEY,"Content-Type":"application/json"},
      json={"q":q,"gl":"br","hl":"pt","num":10},timeout=20); r.raise_for_status(); return r.json()

def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    for col in ("cab_instagram","cab_whatsapp","cab_cel","cab_cel_conf","cab_site"):
        t="text"
        cur.execute(f"ALTER TABLE prospeccao.icp527_screen ADD COLUMN IF NOT EXISTS {col} {t};")
    cur.execute("""SELECT s.cnpj_basico, g.match_fazenda AS cabanha, s.uf, left(s.telefone,2) AS ddd, s.touros_nelore
        FROM prospeccao.icp527_screen s JOIN prospeccao.prospect_genetica g ON g.cnpj_basico=s.cnpj_basico
        ORDER BY s.touros_nelore DESC""")
    rows=cur.fetchall()
    print(f"[harvest cabanha em {len(rows)} fazendas de elite]",file=sys.stderr,flush=True)
    hi=hwa=hcel=hddd=0
    for i,r in enumerate(rows,1):
        try:
            j=serper(f'"{r["cabanha"]}" nelore {r["uf"]} (whatsapp OR contato OR telefone OR instagram)')
        except Exception as e:
            print(f"  {i} ERRO {str(e)[:40]}",file=sys.stderr); time.sleep(2); continue
        blob=" ".join(o.get("title","")+" "+o.get("snippet","")+" "+o.get("link","") for o in j.get("organic",[]))
        ig=next((h for h in RE_IG.findall(blob) if h.lower() not in IG_BAD),None)
        m=RE_WA.search(blob); wa=re.sub(r'\D','',m.group(1)) if m else None
        cels=[re.sub(r'\D','',c) for c in RE_TEL.findall(blob)]
        cel_ddd=next((c for c in cels if c[:2]==r["ddd"]),None)        # alta conf (DDD da fazenda)
        cel=cel_ddd or (cels[0] if cels else None)
        conf="alta(DDD)" if cel_ddd else ("media" if cel else None)
        site=next((o.get("link") for o in j.get("organic",[]) if o.get("link") and not any(s in o["link"] for s in SOCIAL)),None)
        hi+=bool(ig); hwa+=bool(wa); hcel+=bool(cel); hddd+=bool(cel_ddd)
        cur.execute("""UPDATE prospeccao.icp527_screen SET cab_instagram=%s,cab_whatsapp=%s,cab_cel=%s,cab_cel_conf=%s,cab_site=%s
            WHERE cnpj_basico=%s""",(ig,wa,cel,conf,site,r["cnpj_basico"]))
        time.sleep(0.35)
        if i%25==0: print(f"  {i}/{len(rows)} | IG {hi} · WhatsApp {hwa} · cel {hcel} (DDD-ok {hddd})",file=sys.stderr,flush=True)
    n=len(rows)
    print(f"\n[FIM] {n} | Instagram {hi} ({100*hi//n}%) · WhatsApp {hwa} · celular {hcel} ({100*hcel//n}%, DDD-confirmado {hddd}/{100*hddd//n}%)",file=sys.stderr,flush=True)

if __name__=="__main__": main()
