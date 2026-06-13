#!/usr/bin/env python3
"""#5 Re-query WhatsApp das fazendas com Instagram mas SEM zap ainda — ângulo NOVO: busca pelo
@handle do IG (+ nome da fazenda) no Serper, pescando wa.me que a busca-da-marca não achou.
Grava resto_referencia.whatsapp_bio + whats_retry. Sharded NSHARD/SHARD."""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx
KEY=os.getenv("SERPER_API_KEY","").strip()
DB=dict(host="db",dbname="wins_agro",user="postgres",password=os.getenv('PGPW') or os.getenv("POSTGRES_PASSWORD",""))
RE_WA=re.compile(r'(?:wa\.me/|api\.whatsapp\.com/(?:send/?)?\?phone=|whatsapp\.com/send\?phone=)(\+?\d{10,13})',re.I)
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
    for p in j.get("places",[]) or []: blobs.append(p.get("title","")+" "+str(p.get("phoneNumber","")))
    full=" ".join(blobs)
    for m in RE_WA.finditer(full):
        z=norm_mobile(m.group(1))
        if z: return z
    for m in RE_ZAP.finditer(full):
        z=norm_mobile(m.group(1))
        if z: return z
    return None
def nucleo(r):
    r=re.sub(r'\b(LTDA|S/?A|EIRELI|ME|EPP|AGROPECUARIA|AGRO\s?PECUARIA|AGROPASTORIL|AGRICOLA|FAZENDA|EMPREENDIMENTOS?|PARTICIPACOES|E|DE|DA|DO)\b','',(r or '').upper()).strip()
    return re.sub(r'\s+',' ',r)
def main():
    if not KEY: print("FALTA SERPER",file=sys.stderr); sys.exit(2)
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("ALTER TABLE prospeccao.resto_referencia ADD COLUMN IF NOT EXISTS whats_retry timestamptz")
    cur.execute("""SELECT rr.cnpj_basico, rr.instagram, t.razao, rr.uf, t.municipio
                   FROM prospeccao.resto_referencia rr JOIN prospeccao.hunter_resto_todo t USING(cnpj_basico)
                   WHERE rr.instagram IS NOT NULL AND rr.whatsapp IS NULL AND rr.whatsapp_bio IS NULL AND rr.whats_retry IS NULL""")
    rows=cur.fetchall()
    NSHARD=int(os.getenv("NSHARD","1")); SHARD=int(os.getenv("SHARD","0"))
    rows=[r for i,r in enumerate(rows) if i % NSHARD == SHARD]
    print(f"[Retry WhatsApp via @handle: {len(rows)} | shard {SHARD}/{NSHARD}]",file=sys.stderr,flush=True)
    achou=0
    with httpx.Client():
        for i,r in enumerate(rows,1):
            q=f'"{r["instagram"]}" {nucleo(r["razao"])} {r["uf"]} (whatsapp OR contato OR telefone)'.strip()
            try: j=serper(q)
            except Exception:
                print(f"  {i} serper falhou",file=sys.stderr); continue
            zap=find_zap(j); um=bool(zap) and DDD2UF.get(zap[:2])==r['uf']
            if zap: achou+=1
            cur.execute("UPDATE prospeccao.resto_referencia SET whatsapp_bio=%s, whats_ufmatch=COALESCE(whats_ufmatch,%s), whats_retry=now() WHERE cnpj_basico=%s",
                        (zap, um if zap else None, r['cnpj_basico']))
            time.sleep(0.3)
            if i%30==0: print(f"  {i}/{len(rows)} | achou {achou}",file=sys.stderr,flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | WhatsApp novo {achou} ({100*achou//n}%)",file=sys.stderr,flush=True)
if __name__=="__main__": main()
