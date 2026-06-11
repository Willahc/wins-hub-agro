#!/usr/bin/env python3
"""PoC: acha WhatsApp das cabanhas SEM zap, buscando no Google (Serper) pelo NOME DO DECISOR
e pela FAZENDA — o número costuma aparecer no IG (bio/linktree), site ou ficha. Extrai wa.me,
número rotulado 'whatsapp/zap/contato' e celular do site; valida que é MÓVEL (prospeccao.cel_whats).
Lê do v_fila_prospeccao (sem whatsapp confirmado nem inferido). Mede taxa de acerto.
Uso: docker exec -e SERPER_API_KEY=.. wins_agro_v1_api_1 python /app/enrich_cabanha_zap.py [N]"""
import os, re, sys, time, json
import psycopg2, psycopg2.extras, httpx

KEY = os.getenv("SERPER_API_KEY", "").strip()
LIM = int(sys.argv[1]) if len(sys.argv) > 1 else 40
DB = dict(host="db", dbname="wins_agro", user="postgres", password=os.getenv("POSTGRES_PASSWORD", ""))

RE_WA  = re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp\.com/send\?phone=)(\+?\d{10,13})', re.I)
# só rótulo EXPLÍCITO de whatsapp/zap (contato/tel/fone geram falso positivo de fixo/co-aparição)
RE_ZAP = re.compile(r'(?:whats\s?app|whatsapp|zap)\D{0,14}(\(?\d{2}\)?\s?9\d{4}[-\s.]?\d{4})', re.I)
RE_IG  = re.compile(r'instagram\.com/([A-Za-z0-9_.]{2,30})', re.I)
IG_BAD = {"p","explore","reel","reels","tv","accounts","about","privacy","legal","stories","directory","s"}

def digits(s): return re.sub(r'\D','',s or '')

# DDD -> UF (p/ checar se o WhatsApp encontrado é do MESMO estado da cabanha = alta confiança)
DDD2UF = {}
for _ufs, _dd in [('SP',range(11,20)),('RJ',[21,22,24]),('ES',[27,28]),('MG',[31,32,33,34,35,37,38]),
    ('PR',[41,42,43,44,45,46]),('SC',[47,48,49]),('RS',[51,53,54,55]),('DF',[61]),('GO',[62,64]),
    ('TO',[63]),('MT',[65,66]),('MS',[67]),('AC',[68]),('RO',[69]),('BA',[71,73,74,75,77]),('SE',[79]),
    ('PE',[81,87]),('AL',[82]),('PB',[83]),('RN',[84]),('CE',[85,88]),('PI',[86,89]),('PA',[91,93,94]),
    ('AM',[92,97]),('RR',[95]),('AP',[96]),('MA',[98,99])]:
    for _d in _dd: DDD2UF[str(_d)] = _ufs

# DDDs válidos no Brasil (mata fragmento de CNPJ tipo DDD 00/01/10/20/40/78...)
DDD_OK = {'11','12','13','14','15','16','17','18','19','21','22','24','27','28','31','32','33','34',
          '35','37','38','41','42','43','44','45','46','47','48','49','51','53','54','55','61','62',
          '63','64','65','66','67','68','69','71','73','74','75','77','79','81','82','83','84','85',
          '86','87','88','89','91','92','93','94','95','96','97','98','99'}

def norm_mobile(raw):
    """retorna celular 11-díg VÁLIDO (DDD real) ou None."""
    d = digits(raw)
    if d.startswith('55') and len(d) >= 12: d = d[2:]
    if len(d)==11 and d[2]=='9' and d[:2] in DDD_OK: return d
    if len(d)==10 and d[2] in '6789' and d[:2] in DDD_OK: return d[:2]+'9'+d[2:]
    return None

def serper(q, tries=3):
    # retry com backoff: falha transitória da API não pode virar "lead sem contato" permanente
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
    """procura WhatsApp por prioridade: wa.me > rótulo whatsapp/zap > móvel solto. + handle IG."""
    blobs = []
    for o in j.get("organic", []):
        blobs.append(o.get("title","")+" | "+o.get("snippet","")+" | "+o.get("link",""))
    kg = j.get("knowledgeGraph", {})
    blobs.append(str(kg.get("attributes",{}))+" "+kg.get("phoneNumber",""))
    for p in j.get("places",[]) or []:
        blobs.append(p.get("title","")+" "+str(p.get("phoneNumber","")))
    full = " ".join(blobs)
    ig = next((h.lower() for h in RE_IG.findall(full) if h.lower() not in IG_BAD and not h.isdigit()), None)
    # 1) wa.me explícito
    for m in RE_WA.finditer(full):
        z = norm_mobile(m.group(1))
        if z: return z, "wa.me", ig
    # 2) número rotulado EXPLICITAMENTE como whatsapp/zap
    for m in RE_ZAP.finditer(full):
        z = norm_mobile(m.group(1))
        if z: return z, "rotulo", ig
    return None, None, ig

def main():
    if not KEY: print("FALTA SERPER_API_KEY", file=sys.stderr); sys.exit(2)
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.cabanha_zap(
        cnpj text PRIMARY KEY, decisor text, fazenda text, uf text,
        whatsapp text, fonte text, instagram text, via_busca text, buscado_em timestamptz DEFAULT now());
        ALTER TABLE prospeccao.cabanha_zap ADD COLUMN IF NOT EXISTS uf_match boolean;""")
    cur.execute("""
        SELECT cnpj, decisor, COALESCE(cabanha,fazenda) AS fazenda, uf, municipio, instagram
        FROM prospeccao.v_fila_prospeccao
        WHERE ativo AND whatsapp IS NULL AND prospeccao.cel_whats(telefone) IS NULL
          AND decisor IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM prospeccao.cabanha_zap z WHERE z.cnpj=v_fila_prospeccao.cnpj)
        ORDER BY (instagram IS NOT NULL) DESC, cnpj
        LIMIT %s""", (LIM,))
    rows=cur.fetchall()
    print(f"[cabanha_zap PoC: {len(rows)} alvos]", file=sys.stderr, flush=True)
    achou=ok_uf=0
    for i,r in enumerate(rows,1):
        dec=re.sub(r'\s+',' ',(r['decisor'] or '')).strip()
        faz=re.sub(r'\b(FAZENDA|AGROPECUARIA|LTDA|S/?A|AGRO|PECUARIA)\b','',r['fazenda'] or '',flags=re.I).strip()
        zap=fonte=ig=via=None
        # tenta por (decisor + fazenda), depois só fazenda+IG, depois só decisor
        queries=[(f'"{dec}" {faz} {r["uf"]} whatsapp OR contato OR instagram','decisor+fazenda'),
                 (f'{faz} {r["municipio"] or ""} {r["uf"]} pecuária whatsapp OR contato instagram','fazenda'),
                 (f'"{dec}" {r["uf"]} instagram whatsapp','decisor')]
        falhas=0
        for q,tag in queries:
            try: z,f,h = find_zap(serper(q))
            except Exception as e:
                falhas+=1; print(f"  {i} ERRO {str(e)[:40]}",file=sys.stderr); time.sleep(2); continue
            if h and not ig: ig=h
            if z: zap,fonte,via=z,f,tag; break
            time.sleep(0.3)
        # TODAS as buscas falharam (API fora, não "não achou"): NÃO grava — sem linha/
        # sem buscado_em novo, o próximo run re-tenta este lead em vez de enterrá-lo.
        if falhas == len(queries) and not zap:
            continue
        ufm = (DDD2UF.get(zap[:2]) == r['uf']) if zap else None
        if zap: achou+=1
        if ufm: ok_uf+=1
        # COALESCE: re-run que não achou nada não apaga contato já conquistado antes
        cur.execute("""INSERT INTO prospeccao.cabanha_zap(cnpj,decisor,fazenda,uf,whatsapp,fonte,instagram,via_busca,uf_match)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(cnpj) DO UPDATE SET
            whatsapp=COALESCE(EXCLUDED.whatsapp, cabanha_zap.whatsapp),
            fonte=COALESCE(EXCLUDED.fonte, cabanha_zap.fonte),
            instagram=COALESCE(EXCLUDED.instagram, cabanha_zap.instagram),
            via_busca=COALESCE(EXCLUDED.via_busca, cabanha_zap.via_busca),
            uf_match=COALESCE(EXCLUDED.uf_match, cabanha_zap.uf_match),
            buscado_em=now()""",
            (r['cnpj'],dec,r['fazenda'],r['uf'],zap,fonte,ig,via,ufm))
        if i%10==0: print(f"  {i}/{len(rows)} | whatsapp {achou} (DDD-UF ok {ok_uf})",file=sys.stderr,flush=True)
    print(f"\n[FIM] {len(rows)} buscados · WhatsApp {achou} · DDD bate UF {ok_uf} (alta confiança)",file=sys.stderr,flush=True)

if __name__=="__main__": main()
