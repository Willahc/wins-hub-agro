#!/usr/bin/env python3
"""Estende o pipeline vencedor ao resto do ICP genético (confianca='media', ~934): MX + harvest
por NOME DE CABANHA (Serper). Reputação = match oficial Lista Suja por CNPJ (no deliverable, não
aqui — a busca solta era falso positivo). Grava prospeccao.icp_media_screen.
⚠️ média = cabanha casa 2-3 empresas (menos único que alta) → precisão menor; UF+DDD desambiguam.
Roda c/ SERPER_API_KEY no env."""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

KEY=os.getenv("SERPER_API_KEY","").strip()
if not KEY: print("FALTA SERPER_API_KEY",file=sys.stderr); sys.exit(2)
DB=dict(host=os.getenv("DB_HOST","db"),port=int(os.getenv("DB_PORT",5432)),dbname=os.getenv("POSTGRES_DB","wins_agro"),
        user=os.getenv("POSTGRES_USER","postgres"),password=os.getenv("POSTGRES_PASSWORD",""))
FREE={'gmail.com','hotmail.com','outlook.com','yahoo.com.br','yahoo.com','live.com','bol.com.br','terra.com.br','uol.com.br','icloud.com','msn.com','globo.com'}
IG_BAD={"p","reel","reels","explore","tv","accounts","stories","about"}
RE_IG=re.compile(r'instagram\.com/([A-Za-z0-9_.]{3,30})')
RE_WA=re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d{10,13})',re.I)
RE_TEL=re.compile(r'\(?\d{2}\)?\s?9\d{4}[-\s]?\d{4}')
SOCIAL=('instagram.com','facebook.com','linkedin.com','youtube.com','econodata','cnpj','consultasocio','escavador')

def doh_mx(dom):
    try:
        j=httpx.get("https://dns.google/resolve",params={"name":dom,"type":"MX"},timeout=8).json()
        if j.get("Status")==3: return "dominio_inexistente"
        return "mx_ok" if any(a.get("type")==15 for a in j.get("Answer",[])) else "sem_mx"
    except Exception: return "erro_dns"

def serper(q):
    r=httpx.post("https://google.serper.dev/search",headers={"X-API-KEY":KEY,"Content-Type":"application/json"},
      json={"q":q,"gl":"br","hl":"pt","num":10},timeout=20); r.raise_for_status(); return r.json()

def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.icp_media_screen(
        cnpj_basico varchar(8) PRIMARY KEY, razao text, cabanha text, decisor text, uf text, municipio text,
        touros_nelore int, email text, email_status text, telefone text,
        cab_instagram text, cab_whatsapp text, cab_cel text, cab_cel_conf text, cab_site text,
        screened_at timestamptz DEFAULT now());""")
    cur.execute("""SELECT DISTINCT ON (g.cnpj_basico) g.cnpj_basico, g.razao, g.match_fazenda AS cabanha,
               ld.decisor_top AS decisor, g.uf, g.municipio, g.touros_nelore,
               e.correio_eletronico AS email, e.ddd_1||e.telefone_1 AS telefone, e.ddd_1 AS ddd
        FROM prospeccao.prospect_genetica g
        JOIN prospeccao.lead_decisor ld ON ld.cnpj_basico=g.cnpj_basico
        JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico=g.cnpj_basico AND e.cnae_fiscal_principal='0151201' AND e.situacao_cadastral='02'
        WHERE g.confianca='media'
        ORDER BY g.cnpj_basico, (e.correio_eletronico IS NOT NULL) DESC""")
    rows=cur.fetchall()
    cur.execute("SELECT cnpj_basico FROM prospeccao.icp_media_screen")
    done={r["cnpj_basico"] for r in cur.fetchall()}
    rows=[r for r in rows if r["cnpj_basico"] not in done]
    print(f"[ICP media: {len(rows)} a processar]",file=sys.stderr,flush=True)
    # MX em lote
    doms=sorted({r["email"].split("@",1)[1].lower() for r in rows if r["email"] and "@" in r["email"]}-FREE)
    mx={}
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs={ex.submit(doh_mx,d):d for d in doms}
        for f in as_completed(futs): mx[futs[f]]=f.result()
    hi=hcel=hddd=eok=0
    for i,r in enumerate(rows,1):
        em=r["email"]; es="sem_email"
        if em and "@" in em:
            dom=em.split("@",1)[1].lower(); es="free_entregavel" if dom in FREE else mx.get(dom,"erro_dns")
        if es in ("mx_ok","free_entregavel"): eok+=1
        ig=wa=cel=conf=site=None
        try:
            j=serper(f'"{r["cabanha"]}" nelore {r["uf"]} (whatsapp OR contato OR telefone OR instagram)')
            blob=" ".join(o.get("title","")+" "+o.get("snippet","")+" "+o.get("link","") for o in j.get("organic",[]))
            ig=next((h for h in RE_IG.findall(blob) if h.lower() not in IG_BAD),None)
            m=RE_WA.search(blob); wa=re.sub(r'\D','',m.group(1)) if m else None
            cels=[re.sub(r'\D','',c) for c in RE_TEL.findall(blob)]
            cel_ddd=next((c for c in cels if c[:2]==r["ddd"]),None)
            cel=cel_ddd or (cels[0] if cels else None)
            conf="alta(DDD)" if cel_ddd else ("media" if cel else None)
            site=next((o.get("link") for o in j.get("organic",[]) if o.get("link") and not any(s in o["link"] for s in SOCIAL)),None)
        except Exception: pass
        hi+=bool(ig); hcel+=bool(cel); hddd+=bool(conf=="alta(DDD)")
        cur.execute("""INSERT INTO prospeccao.icp_media_screen
          (cnpj_basico,razao,cabanha,decisor,uf,municipio,touros_nelore,email,email_status,telefone,cab_instagram,cab_whatsapp,cab_cel,cab_cel_conf,cab_site)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET
          email_status=EXCLUDED.email_status,cab_instagram=EXCLUDED.cab_instagram,cab_whatsapp=EXCLUDED.cab_whatsapp,
          cab_cel=EXCLUDED.cab_cel,cab_cel_conf=EXCLUDED.cab_cel_conf,cab_site=EXCLUDED.cab_site,screened_at=now()""",
          (r["cnpj_basico"],r["razao"],r["cabanha"],r["decisor"],r["uf"],r["municipio"],r["touros_nelore"],em,es,r["telefone"],ig,wa,cel,conf,site))
        time.sleep(0.35)
        if i%50==0: print(f"  {i}/{len(rows)} | email-ok {eok} · IG {hi} · cel {hcel} (DDD {hddd})",file=sys.stderr,flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | email vivo {eok} · Instagram {hi} ({100*hi//n}%) · celular {hcel} (DDD-conf {hddd})",file=sys.stderr,flush=True)

if __name__=="__main__": main()
