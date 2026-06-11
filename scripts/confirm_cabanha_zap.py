#!/usr/bin/env python3
"""Re-ancoragem por NOME: confirma que o WhatsApp recuperado é REALMENTE da cabanha —
re-busca e checa se o número aparece numa página/snippet que TAMBÉM cita o decisor ou a
fazenda (casa pelos últimos 8 dígitos, robusto a 9º dígito/DDI). Marca cabanha_zap.nome_confirmado."""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx

KEY=os.getenv("SERPER_API_KEY","").strip()
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.getenv("POSTGRES_PASSWORD",""))
STOP={'FAZENDA','AGROPECUARIA','AGROPECUÁRIA','LTDA','AGRO','PECUARIA','PECUÁRIA','RANCHO','SITIO','SÍTIO',
      'JUNIOR','FILHO','NETO','DOS','DAS','DE','DA','DO','SANTA','SANTO','SAO','SÃO','NOVA','NOVO','VALE'}

def digits(s): return re.sub(r'\D','',s or '')
def toks(nm): return {t for t in re.split(r'\W+',(nm or '').upper()) if len(t)>=4 and t not in STOP}

def serper(q, tries=3):
    for t in range(tries):
        try:
            r=httpx.post("https://google.serper.dev/search",headers={"X-API-KEY":KEY,"Content-Type":"application/json"},
                         json={"q":q,"gl":"br","hl":"pt","num":10},timeout=20); r.raise_for_status(); return r.json()
        except Exception:
            if t==tries-1: raise
            time.sleep(2*(t+1))

def confirma(j, last8, ntok):
    """True se algum resultado tem o número (últimos 8 díg) E ≥1 token do nome."""
    for o in j.get("organic",[]):
        txt=o.get("title","")+" "+o.get("snippet","")+" "+o.get("link","")
        if last8 in digits(txt) and any(t in txt.upper() for t in ntok):
            return True, (o.get("link","") or "")[:60]
    return False, None

def main():
    if not KEY: print("FALTA SERPER_API_KEY",file=sys.stderr); sys.exit(2)
    c=psycopg2.connect(**DB); c.autocommit=True; cur=c.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("ALTER TABLE prospeccao.cabanha_zap ADD COLUMN IF NOT EXISTS nome_confirmado boolean")
    cur.execute("ALTER TABLE prospeccao.cabanha_zap ADD COLUMN IF NOT EXISTS fonte_confirma text")
    cur.execute("SELECT cnpj,decisor,fazenda,uf,whatsapp FROM prospeccao.cabanha_zap WHERE whatsapp IS NOT NULL ORDER BY uf_match DESC NULLS LAST")
    rows=cur.fetchall(); print(f"[confirma: {len(rows)} números]",file=sys.stderr,flush=True)
    ok=0
    for i,r in enumerate(rows,1):
        last8=r['whatsapp'][-8:]; ntok=toks(r['decisor'])|toks(r['fazenda'])
        conf=False; src=None; falhas=0; nq=0
        if ntok:
            dec=re.sub(r'\s+',' ',r['decisor'] or '').strip()
            queries=(f'"{dec}" {r["fazenda"]} {r["uf"]}', f'{r["fazenda"]} {r["uf"]} whatsapp contato')
            nq=len(queries)
            for q in queries:
                try: conf,src=confirma(serper(q),last8,ntok)
                except Exception as e: falhas+=1; print(f"  {i} ERRO {str(e)[:35]}",file=sys.stderr); time.sleep(2); continue
                if conf: break
                time.sleep(0.3)
        # API fora em TODAS as tentativas != "não confirmado": não regrava False
        # em cima de confirmação anterior; re-run tenta de novo.
        if nq and falhas==nq:
            continue
        ok+=int(conf)
        cur.execute("UPDATE prospeccao.cabanha_zap SET nome_confirmado=%s, fonte_confirma=%s WHERE cnpj=%s",
                    (conf,src,r['cnpj']))
        if i%30==0: print(f"  {i}/{len(rows)} | nome_confirmado {ok}",file=sys.stderr,flush=True)
    print(f"\n[FIM] {len(rows)} · nome_confirmado {ok}",file=sys.stderr,flush=True)

if __name__=="__main__": main()
