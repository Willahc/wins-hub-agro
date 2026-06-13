#!/usr/bin/env python3
"""#3 GRÁTIS: WhatsApp/telefone PUBLICADO dos técnicos-EMPRESA (assessoria, clínica, central de IA,
agropecuária) que ainda não têm zap confirmado. NÃO usa o número reconstruído da Receita — busca a
MARCA da empresa no Serper e pesca: wa.me / número rotulado 'whatsapp' (celular real) + o telefone do
Google Meu Negócio (contato atual da empresa, fixo ou móvel). Só EMPRESA (nome de pessoa física não é
raspável). Grava prospeccao.tecnico_zap. Resumível (NOT EXISTS na tecnico_zap) e sharded (NSHARD/SHARD).
Uso: docker exec -e LIM=900 -e MAXPRI=3 wins_agro_v1_api_1 python - < scripts/enrich_tecnico_whats.py"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.getenv("SERPER_API_KEY","").strip()
LIM=int(os.getenv("LIM","900"))
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.getenv("POSTGRES_PASSWORD",""))
RE_WA =re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp\.com/send\?phone=)(\+?\d{10,13})',re.I)
RE_ZAP=re.compile(r'(?:whats\s?app|whatsapp|zap)\D{0,14}(\(?\d{2}\)?\s?9\d{4}[-\s.]?\d{4})',re.I)
def digits(s): return re.sub(r'\D','',s or '')
DDD2UF={}
for _ufs,_dd in [('SP',range(11,20)),('RJ',[21,22,24]),('ES',[27,28]),('MG',[31,32,33,34,35,37,38]),
    ('PR',[41,42,43,44,45,46]),('SC',[47,48,49]),('RS',[51,53,54,55]),('DF',[61]),('GO',[62,64]),
    ('TO',[63]),('MT',[65,66]),('MS',[67]),('AC',[68]),('RO',[69]),('BA',[71,73,74,75,77]),('SE',[79]),
    ('PE',[81,87]),('AL',[82]),('PB',[83]),('RN',[84]),('CE',[85,88]),('PI',[86,89]),('PA',[91,93,94]),
    ('AM',[92,97]),('RR',[95]),('AP',[96]),('MA',[98,99])]:
    for _d in _dd: DDD2UF[str(_d)]=_ufs
DDD_OK=set(DDD2UF.keys())
def norm_mobile(raw):
    d=digits(raw)
    if d.startswith('55') and len(d)>=12: d=d[2:]
    if len(d)==11 and d[2]=='9' and d[:2] in DDD_OK: return d
    if len(d)==10 and d[2] in '6789' and d[:2] in DDD_OK: return d[:2]+'9'+d[2:]
    return None
def serper(q,tries=3):
    for t in range(tries):
        try:
            r=httpx.post("https://google.serper.dev/search",headers={"X-API-KEY":KEY,"Content-Type":"application/json"},
                json={"q":q,"gl":"br","hl":"pt","num":10},timeout=20); r.raise_for_status(); return r.json()
        except Exception:
            if t==tries-1: raise
            time.sleep(2*(t+1))
def find_zap(j):
    blobs=[]
    for o in j.get("organic",[]): blobs.append(o.get("title","")+" | "+o.get("snippet","")+" | "+o.get("link",""))
    kg=j.get("knowledgeGraph",{}); blobs.append(str(kg.get("attributes",{}))+" "+kg.get("phoneNumber",""))
    for p in j.get("places",[]) or []: blobs.append(p.get("title","")+" "+str(p.get("phoneNumber","")))
    full=" ".join(blobs)
    for m in RE_WA.finditer(full):
        z=norm_mobile(m.group(1))
        if z: return z,"wa.me"
    for m in RE_ZAP.finditer(full):
        z=norm_mobile(m.group(1))
        if z: return z,"rotulo"
    return None,None
def google_phone(j):
    """telefone do Google Meu Negócio / knowledge graph — contato ATUAL da empresa (fixo ou móvel)."""
    kg=j.get("knowledgeGraph",{}) or {}
    if kg.get("phoneNumber"): return kg["phoneNumber"]
    for p in (j.get("places",[]) or []):
        if p.get("phoneNumber"): return p["phoneNumber"]
    return None
def clean(name):
    n=re.sub(r'\b(LTDA|S/?A|EIRELI|ME|EPP|MEI)\b','',(name or '').upper())
    return re.sub(r'\s+',' ',n).strip()
TARGET="""
SELECT cnpj14, nome, uf, municipio,
  (crmv_confiavel::int + tem_fazenda_propria::int + (tier IN ('A-inseminador','B-corte-alto'))::int) AS sinal
FROM prospeccao.v_tecnico_fazenda_ui t
WHERE nome !~ '^[0-9]' AND nome <> '(sem nome fantasia)'
  AND whatsapp IS NULL AND celular IS NULL
  AND nome ~* '(ASSESSORIA|AGROPECU|VETERIN|CLINICA|CLÍNICA|REPRODU|GENETICA|GENÉTICA|NUTRI|AGRO|PECU|RURAL|CENTRAL|LTDA|EIRELI|COMERCIO|COMÉRCIO|INSEMIN|EMBRI)'
  AND ((categoria IS NOT NULL AND tier IN ('A-inseminador','B-corte-alto','C-corte-medio','D-corte-baixo'))
       OR categoria IN ('apoio_pecuaria','inseminacao','repro_secundario'))
  AND NOT EXISTS (SELECT 1 FROM prospeccao.tecnico_zap z WHERE z.cnpj14=t.cnpj14)
ORDER BY sinal DESC, tier, cnpj14 LIMIT %s"""
def main():
    if not KEY: print("FALTA SERPER_API_KEY",file=sys.stderr); sys.exit(2)
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.tecnico_zap (
        cnpj14 text PRIMARY KEY, whatsapp text, whats_fonte text, whats_ufmatch boolean,
        tel_google text, buscado timestamptz DEFAULT now())""")
    cur.execute(TARGET,(LIM,))
    rows=cur.fetchall()
    NSHARD=int(os.getenv("NSHARD","1")); SHARD=int(os.getenv("SHARD","0"))
    rows=[r for k,r in enumerate(rows) if k%NSHARD==SHARD]
    print(f"[tec-zap: {len(rows)} empresas | shard {SHARD}/{NSHARD}]",file=sys.stderr,flush=True)
    achou=ufm=gph=0
    for i,r in enumerate(rows,1):
        muni=r['municipio'] or ''; uf=r['uf']; ctx=clean(r['nome'])
        q=f'{ctx} {muni} {uf} (whatsapp OR contato OR telefone)'.strip()
        try: j=serper(q)
        except Exception:
            print(f"  {i} Serper falhou — pulado (resumível)",file=sys.stderr); continue
        zap,fonte=find_zap(j); um=bool(zap) and DDD2UF.get(zap[:2])==uf
        tg=google_phone(j)
        if zap: achou+=1
        if um: ufm+=1
        if tg: gph+=1
        cur.execute("""INSERT INTO prospeccao.tecnico_zap(cnpj14,whatsapp,whats_fonte,whats_ufmatch,tel_google,buscado)
            VALUES(%s,%s,%s,%s,%s,now()) ON CONFLICT (cnpj14) DO UPDATE
            SET whatsapp=EXCLUDED.whatsapp, whats_fonte=EXCLUDED.whats_fonte,
                whats_ufmatch=EXCLUDED.whats_ufmatch, tel_google=EXCLUDED.tel_google, buscado=now()""",
            (r['cnpj14'],zap,fonte,um,tg))
        time.sleep(0.3)
        if i%25==0: print(f"  {i}/{len(rows)} | zap {achou} (uf-match {ufm}) | tel-google {gph}",file=sys.stderr,flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | WhatsApp {achou} ({100*achou//n}%) | alta-conf {ufm} | tel-Google {gph} ({100*gph//n}%)",file=sys.stderr,flush=True)
if __name__=="__main__": main()
