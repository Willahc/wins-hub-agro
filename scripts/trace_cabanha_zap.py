#!/usr/bin/env python3
"""Rastreia a PROVENIÊNCIA dos WhatsApp não confirmados: re-busca, acha o resultado que contém
o número (casa últimos 8 díg) e grava a URL + o trecho de origem em cabanha_zap.source_url/source_txt.
Mostra de ONDE de fato cada número veio (site da fazenda? diretório? prefeitura? co-aparição?)."""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx

KEY=os.getenv("SERPER_API_KEY","").strip()
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.getenv("POSTGRES_PASSWORD",""))
def digits(s): return re.sub(r'\D','',s or '')

def serper(q):
    r=httpx.post("https://google.serper.dev/search",headers={"X-API-KEY":KEY,"Content-Type":"application/json"},
                 json={"q":q,"gl":"br","hl":"pt","num":10},timeout=20); r.raise_for_status(); return r.json()

def localiza(j, last8):
    for o in j.get("organic",[]):
        txt=o.get("title","")+" | "+o.get("snippet","")
        if last8 in digits(txt+" "+o.get("link","")):
            return o.get("link",""), txt[:180]
    return None, None

def dominio(u):
    m=re.search(r'https?://([^/]+)', u or ''); return (m.group(1) if m else (u or '')).replace('www.','')

def main():
    if not KEY: print("FALTA SERPER_API_KEY",file=sys.stderr); sys.exit(2)
    c=psycopg2.connect(**DB); c.autocommit=True; cur=c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("ALTER TABLE prospeccao.cabanha_zap ADD COLUMN IF NOT EXISTS source_url text")
    cur.execute("ALTER TABLE prospeccao.cabanha_zap ADD COLUMN IF NOT EXISTS source_txt text")
    cur.execute("""SELECT cnpj,decisor,fazenda,uf,whatsapp,via_busca FROM prospeccao.cabanha_zap
        WHERE whatsapp IS NOT NULL AND NOT (uf_match OR fonte IN ('wa.me','extlink'))
          AND COALESCE(nome_confirmado,false)=false ORDER BY uf""")
    rows=cur.fetchall(); print(f"[trace: {len(rows)} números]",file=sys.stderr,flush=True)
    achou=0
    for i,r in enumerate(rows,1):
        last8=r['whatsapp'][-8:]; dec=re.sub(r'\s+',' ',r['decisor'] or '').strip()
        url=txt=None
        # repete as MESMAS buscas da recuperação, na ordem
        for q in (f'"{dec}" {r["fazenda"]} {r["uf"]} whatsapp OR contato OR instagram',
                  f'{r["fazenda"]} {r["uf"]} pecuária whatsapp OR contato instagram',
                  f'"{dec}" {r["uf"]} instagram whatsapp'):
            try: url,txt=localiza(serper(q),last8)
            except Exception: time.sleep(2); continue
            if url: break
            time.sleep(0.3)
        if url: achou+=1
        cur.execute("UPDATE prospeccao.cabanha_zap SET source_url=%s, source_txt=%s WHERE cnpj=%s",(url,txt,r['cnpj']))
        if i%30==0: print(f"  {i}/{len(rows)} | rastreado {achou}",file=sys.stderr,flush=True)
    print(f"\n[FIM] {len(rows)} · origem localizada {achou}",file=sys.stderr,flush=True)
    # resumo por domínio
    cur.execute("""SELECT regexp_replace(split_part(regexp_replace(source_url,'https?://',''),'/',1),'^www\\.','') dom, count(*)
        FROM prospeccao.cabanha_zap WHERE source_url IS NOT NULL AND whatsapp IS NOT NULL
          AND NOT (uf_match OR fonte IN ('wa.me','extlink')) AND COALESCE(nome_confirmado,false)=false
        GROUP BY 1 ORDER BY 2 DESC LIMIT 20""")
    print("\n=== DE ONDE VIERAM (domínio) ===",file=sys.stderr)
    for x in cur.fetchall(): print(f"  {x['count']:3}  {x['dom']}",file=sys.stderr)

if __name__=="__main__": main()
