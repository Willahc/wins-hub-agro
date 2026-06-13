#!/usr/bin/env python3
"""Frente B: acha WhatsApp/Instagram do OPERADOR JOVEM da fazenda (não o patriarca registrado).
Lê o TOP candidato de prospeccao.contato_candidatos (filho/administrador jovem, score_alcancavel)
e busca no Serper por NOME + FAZENDA + MUNICIPIO -> wa.me / rótulo whatsapp / IG. Valida MÓVEL e
marca uf_match (DDD == UF da fazenda = alta confiança). Grava prospeccao.candidato_zap.
Hipótese: jovem tem Zap/IG público -> fura o teto ~5-17% do decisor registrado.
Uso: docker exec -e SERPER_API_KEY=.. wins_agro_v1_api_1 python /app/enrich_candidato_zap.py [N] [icp]"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx

KEY = os.getenv("SERPER_API_KEY", "").strip()
LIM = int(sys.argv[1]) if len(sys.argv) > 1 else 200
ICP_ONLY = len(sys.argv) > 2 and sys.argv[2].lower() == "icp"
DB = dict(host="db", dbname="wins_agro", user="postgres", password=os.getenv("POSTGRES_PASSWORD", ""))

RE_WA  = re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp\.com/send\?phone=)(\+?\d{10,13})', re.I)
RE_ZAP = re.compile(r'(?:whats\s?app|whatsapp|zap)\D{0,14}(\(?\d{2}\)?\s?9\d{4}[-\s.]?\d{4})', re.I)
RE_IG  = re.compile(r'instagram\.com/([A-Za-z0-9_.]{2,30})', re.I)
IG_BAD = {"p","explore","reel","reels","tv","accounts","about","privacy","legal","stories","directory","s"}

def digits(s): return re.sub(r'\D','',s or '')

DDD2UF = {}
for _ufs, _dd in [('SP',range(11,20)),('RJ',[21,22,24]),('ES',[27,28]),('MG',[31,32,33,34,35,37,38]),
    ('PR',[41,42,43,44,45,46]),('SC',[47,48,49]),('RS',[51,53,54,55]),('DF',[61]),('GO',[62,64]),
    ('TO',[63]),('MT',[65,66]),('MS',[67]),('AC',[68]),('RO',[69]),('BA',[71,73,74,75,77]),('SE',[79]),
    ('PE',[81,87]),('AL',[82]),('PB',[83]),('RN',[84]),('CE',[85,88]),('PI',[86,89]),('PA',[91,93,94]),
    ('AM',[92,97]),('RR',[95]),('AP',[96]),('MA',[98,99])]:
    for _d in _dd: DDD2UF[str(_d)] = _ufs
DDD_OK = set(DDD2UF.keys())

def norm_mobile(raw):
    d = digits(raw)
    if d.startswith('55') and len(d) >= 12: d = d[2:]
    if len(d)==11 and d[2]=='9' and d[:2] in DDD_OK: return d
    if len(d)==10 and d[2] in '6789' and d[:2] in DDD_OK: return d[:2]+'9'+d[2:]
    return None

def serper(q, tries=3):
    for t in range(tries):
        try:
            r = httpx.post("https://google.serper.dev/search",
                           headers={"X-API-KEY":KEY,"Content-Type":"application/json"},
                           json={"q":q,"gl":"br","hl":"pt","num":10}, timeout=20)
            r.raise_for_status(); return r.json()
        except Exception:
            if t == tries-1: raise
            time.sleep(2*(t+1))

def find_zap(j):
    blobs = []
    for o in j.get("organic", []):
        blobs.append(o.get("title","")+" | "+o.get("snippet","")+" | "+o.get("link",""))
    kg = j.get("knowledgeGraph", {})
    blobs.append(str(kg.get("attributes",{}))+" "+kg.get("phoneNumber",""))
    for p in j.get("places",[]) or []:
        blobs.append(p.get("title","")+" "+str(p.get("phoneNumber","")))
    full = " ".join(blobs)
    ig = next((h.lower() for h in RE_IG.findall(full) if h.lower() not in IG_BAD and not h.isdigit()), None)
    for m in RE_WA.finditer(full):
        z = norm_mobile(m.group(1))
        if z: return z, "wa.me", ig
    for m in RE_ZAP.finditer(full):
        z = norm_mobile(m.group(1))
        if z: return z, "rotulo", ig
    return None, None, ig

def nucleo(razao):
    """tira sufixos corporativos pra usar a fazenda como contexto de busca."""
    r = re.sub(r'\b(LTDA|S/?A|EIRELI|ME|EPP|AGROPECUARIA|AGRO\s?PECUARIA|AGROPASTORIL|FAZENDA|EMPREENDIMENTOS?|E|DE|DA|DO)\b','',
               (razao or '').upper()).strip()
    return re.sub(r'\s+',' ',r)

def main():
    if not KEY: print("FALTA SERPER_API_KEY", file=sys.stderr); sys.exit(2)
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.candidato_zap(
        cnpj_basico text PRIMARY KEY, nome text, fazenda text, uf text, municipio text,
        faixa int, score_alcancavel int,
        whatsapp text, fonte text, instagram text, uf_match boolean, buscado_em timestamptz DEFAULT now());""")
    icp_filter = ""
    if ICP_ONLY:
        icp_filter = """AND cc.cnpj_basico IN (
            SELECT cnpj_basico FROM prospeccao.icp527_screen
            UNION SELECT cnpj_basico FROM prospeccao.icp_media_screen
            UNION SELECT left(regexp_replace(cnpj14,'\\D','','g'),8) FROM prospeccao.cabanha_extra WHERE cnpj14 IS NOT NULL)"""
    cur.execute(f"""
        WITH rk AS (
          SELECT cc.*, row_number() OVER (PARTITION BY cc.cnpj_basico
                   ORDER BY cc.score_alcancavel DESC, cc.faixa) rn
          FROM prospeccao.contato_candidatos cc
          WHERE cc.score_alcancavel >= 3 {icp_filter})
        SELECT r.cnpj_basico, r.nome, r.razao AS fazenda, r.uf, r.municipio, r.faixa, r.score_alcancavel
        FROM rk r
        WHERE r.rn=1
          AND r.cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.candidato_zap)
        ORDER BY r.score_alcancavel DESC, r.faixa
        LIMIT %s""", (LIM,))
    rows = cur.fetchall()
    print(f"[Frente B: harvest de {len(rows)} operadores jovens (ICP={ICP_ONLY})]", file=sys.stderr, flush=True)
    achou=ufm=igs=0
    with httpx.Client():
        for i,r in enumerate(rows,1):
            nome=r['nome']; muni=r['municipio'] or ''; uf=r['uf']
            ctx=nucleo(r['fazenda'])
            q=f'"{nome}" {ctx} {muni} {uf}'.strip()
            try:
                j=serper(q)
            except Exception:
                print(f"  {i} Serper falhou 3x — pulado", file=sys.stderr); continue
            zap,fonte,ig=find_zap(j)
            um = bool(zap) and DDD2UF.get(zap[:2])==uf
            if zap: achou+=1
            if um: ufm+=1
            if ig: igs+=1
            cur.execute("""INSERT INTO prospeccao.candidato_zap
                (cnpj_basico,nome,fazenda,uf,municipio,faixa,score_alcancavel,whatsapp,fonte,instagram,uf_match)
                VALUES(%(cnpj_basico)s,%(nome)s,%(fazenda)s,%(uf)s,%(municipio)s,%(faixa)s,%(score_alcancavel)s,%(z)s,%(f)s,%(ig)s,%(um)s)
                ON CONFLICT(cnpj_basico) DO UPDATE SET whatsapp=EXCLUDED.whatsapp,fonte=EXCLUDED.fonte,
                  instagram=EXCLUDED.instagram,uf_match=EXCLUDED.uf_match,buscado_em=now()""",
                {**r,'z':zap,'f':fonte,'ig':ig,'um':um})
            time.sleep(0.3)
            if i%25==0: print(f"  {i}/{len(rows)} | zap {achou} (uf-match {ufm}) | IG {igs}", file=sys.stderr, flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | WhatsApp {achou} ({100*achou//n}%) | uf-match {ufm} ({100*ufm//n}%) | Instagram {igs} ({100*igs//n}%)", file=sys.stderr, flush=True)
if __name__=="__main__": main()
