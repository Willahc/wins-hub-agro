#!/usr/bin/env python3
"""WhatsApp das fazendas do 'resto' que têm Instagram (presença pública = mais provável ter zap
comercial achável). NÃO extrai do IG (o IG esconde phone) — busca a MARCA da fazenda no Serper e
pesca wa.me / número rotulado 'whatsapp/zap', valida MÓVEL e marca uf_match (DDD bate UF = alta
confiança). Mesma régua do enrich_cabanha_zap (~33% achado / ~16% alta-conf). Grava colunas
whatsapp/whats_fonte/whats_ufmatch em prospeccao.resto_referencia.
Uso (worker): docker run ... --env-file .env -e MAXPRI=3 -e LIM=100 hunterpy python /s/enrich_resto_whats.py"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.getenv("SERPER_API_KEY","").strip()
LIM=int(os.getenv("LIM","100")); MAXPRI=int(os.getenv("MAXPRI","3"))
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
def nucleo(r):
    r=re.sub(r'\b(LTDA|S/?A|EIRELI|ME|EPP|AGROPECUARIA|AGRO\s?PECUARIA|AGROPASTORIL|AGRICOLA|FAZENDA|EMPREENDIMENTOS?|PARTICIPACOES|E|DE|DA|DO)\b','',(r or '').upper()).strip()
    return re.sub(r'\s+',' ',r)
def main():
    if not KEY: print("FALTA SERPER_API_KEY",file=sys.stderr); sys.exit(2)
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    for c in ("whatsapp text","whats_fonte text","whats_ufmatch boolean","whats_buscado timestamptz"):
        cur.execute(f"ALTER TABLE prospeccao.resto_referencia ADD COLUMN IF NOT EXISTS {c}")
    cur.execute("""SELECT rr.cnpj_basico, t.razao, rr.uf, t.municipio, t.pri
                   FROM prospeccao.resto_referencia rr JOIN prospeccao.hunter_resto_todo t USING(cnpj_basico)
                   WHERE rr.instagram IS NOT NULL AND rr.whats_buscado IS NULL AND t.pri<=%s
                   ORDER BY t.pri, t.capital_mi DESC NULLS LAST LIMIT %s""",(MAXPRI,LIM))
    rows=cur.fetchall()
    NSHARD=int(os.getenv("NSHARD","1")); SHARD=int(os.getenv("SHARD","0"))
    rows=[r for k,r in enumerate(rows) if k%NSHARD==SHARD]
    print(f"[WhatsApp resto-IG: {len(rows)} fazendas | MAXPRI={MAXPRI} | shard {SHARD}/{NSHARD}]",file=sys.stderr,flush=True)
    achou=ufm=0
    with httpx.Client():
        for i,r in enumerate(rows,1):
            muni=r['municipio'] or ''; uf=r['uf']; ctx=nucleo(r['razao'])
            q=f'{ctx} {muni} {uf} (whatsapp OR contato OR fazenda)'.strip()
            try: j=serper(q)
            except Exception:
                print(f"  {i} Serper falhou — pulado",file=sys.stderr); continue
            zap,fonte=find_zap(j); um=bool(zap) and DDD2UF.get(zap[:2])==uf
            if zap: achou+=1
            if um: ufm+=1
            cur.execute("""UPDATE prospeccao.resto_referencia
                SET whatsapp=%s, whats_fonte=%s, whats_ufmatch=%s, whats_buscado=now() WHERE cnpj_basico=%s""",
                (zap,fonte,um,r['cnpj_basico']))
            time.sleep(0.3)
            if i%20==0: print(f"  {i}/{len(rows)} | zap {achou} (uf-match {ufm})",file=sys.stderr,flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | WhatsApp {achou} ({100*achou//n}%) | alta-conf uf-match {ufm} ({100*ufm//n}%)",file=sys.stderr,flush=True)
if __name__=="__main__": main()
