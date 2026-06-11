#!/usr/bin/env python3
"""Source 5 (canal técnicos): enriquece técnicos (vet/zootecnista/inseminador) via SERPER.
Para cada estabelecimento de veterinária/inseminação (cnpj.estabelecimento_vet), faz 1 busca
Google e extrai Instagram, WhatsApp, celular, telefone (knowledgeGraph/places) e site, ALÉM de
detectar o SINAL DE CORTE/REPRO (IATF, TE, FIV, Nelore, sêmen, embrião...) que separa o
veterinário de GADO do de PET — a segmentação que o CRMV/Receita não dá.

Lê SERPER_API_KEY do env. Prioriza inseminação (0162801) > veterinária, ativos, com telefone,
e municípios de maior rebanho de corte (cnpj.cnpj_por_municipio.bovino_corte).
Resumível: pula CNPJ já buscado (a menos de --redo). Persiste em prospeccao.tecnico_social.

Uso:  docker exec -e SERPER_API_KEY=xxxx wins_agro_v1_api_1 python /app/enrich_tecnico_social.py \
          [--ufs MT,GO,MS,TO] [--nacional] [--limit N] [--redo]
"""
import os, re, sys, time, argparse
import psycopg2, psycopg2.extras, httpx

ap = argparse.ArgumentParser()
ap.add_argument("--ufs", default="MT,GO,MS,TO,MG")
ap.add_argument("--nacional", action="store_true")
ap.add_argument("--limit", type=int, default=100000)
ap.add_argument("--redo", action="store_true")
ap.add_argument("--tiers", default="", help="ex: A,B,C — filtra prospeccao.v_tecnico_lead (vazio=sem filtro)")
A = ap.parse_args()
UFS = None if A.nacional else A.ufs.split(",")
# mapeia letra do tier -> prefixo do tier na view (A-inseminador, B-corte-alto, ...)
TIERS = [t.strip().upper()+"-%" for t in A.tiers.split(",") if t.strip()] or None

KEY = os.getenv("SERPER_API_KEY", "").strip()
if not KEY:
    print("FALTA SERPER_API_KEY", file=sys.stderr); sys.exit(2)
DB = dict(host=os.getenv("DB_HOST", "db"), port=int(os.getenv("DB_PORT", 5432)),
          dbname=os.getenv("POSTGRES_DB", "wins_agro"), user=os.getenv("POSTGRES_USER", "postgres"),
          password=os.getenv("POSTGRES_PASSWORD", ""))

IG_BAD = {"p","explore","reel","reels","tv","accounts","about","privacy","legal","developer","directory","stories"}
RE_IG  = re.compile(r'instagram\.com/([A-Za-z0-9_.]{2,30})', re.I)
RE_WA  = re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp\.com/send\?phone=)(\+?\d{10,13})', re.I)
RE_ZAP = re.compile(r'(?:whats\s?app|whatsapp|zap)[^0-9]{0,16}(\(?\d{2}\)?\s?9\d{4}[-\s]?\d{4})', re.I)
RE_TEL = re.compile(r'\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}')
SOCIAL_DIR = ('instagram.com','facebook.com','linkedin.com','youtube.com','twitter.com','tiktok.com',
              'econodata','consultasocio','cnpj','escavador','solutudo','apontador','telelistas','guiamais')
# sinal de pecuária de CORTE / reprodução (vs clínica de pet)
RE_CORTE = re.compile(r'\b(iatf|fiv|te\b|transfer[eê]ncia de embri|embri[ãa]o|s[êe]men|insemina|repro\w*|'
                      r'nelore|brahman|angus|bovino|gado|pecu[áa]ria|corte|cria[çc][ãa]o|rebanho|matriz|'
                      r'touro|prenhez|andrologia|reprodu[çc][ãa]o animal)\b', re.I)
RE_PET = re.compile(r'\b(pet|c[ãa]es?|gatos?|c[ãa]o e gato|animais de estima|clinica veterin[áa]ria|'
                    r'banho e tosa|vacina[çc][ãa]o de c)\b', re.I)
# CRMV: "CRMV-MG nº 2307/Z", "CRMV PR11707", "CRMV/SP 12345" — captura UF (2 letras), número e categoria (/Z=zootecnista)
RE_CRMV = re.compile(r'CRMV[\s/]*-?\s*([A-Z]{2})?\s*(?:n[ºo°\.\s:]*)?\s*(\d{3,6})\s*(/\s*[ZVzv])?', re.I)
# profissão: zootecnista vs médico-veterinário (sinal textual)
RE_ZOOTEC = re.compile(r'\bzootecnist|\bzootecni[ao]\b|\bzootec\b', re.I)
RE_VET    = re.compile(r'm[ée]dic[oa]?\s*-?\s*veterin[áa]ri', re.I)
UFS_BR = {'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'}

def digits(s): return re.sub(r'\D','',s or '')

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

def _name_tokens(nm):
    return {t for t in re.split(r'\W+', (nm or "").upper()) if len(t)>=4 and not t.isdigit() and t not in
            {'JUNIOR','FILHO','NETO','SOBR','DOS','DAS','Dal','VETERINARIA','CONSULTORIA','PECUARIA','REPRODUCAO','ANIMAL','AGROPEC'}}

def _crmv_in(text):
    out=[]
    for m in RE_CRMV.finditer(text or ""):
        uf=(m.group(1) or "").upper(); num=m.group(2)
        cat="Z" if (m.group(3) and "z" in m.group(3).lower()) else ("V" if m.group(3) else "")
        if uf and uf not in UFS_BR: uf=""
        if 3<=len(num)<=6: out.append((uf,num,cat))
    return out

def extract_crmv(results, name, uf_hint):
    """Só aceita CRMV de um resultado que TAMBÉM contenha o nome do profissional (anti-homônimo).
    Entre os ancorados no nome, prefere UF coincidente. results = lista de (titulo+snippet+link)."""
    toks=_name_tokens(name)
    if not toks: return (None,None,None)
    anchored=[]
    for txt in results:
        up=txt.upper()
        hits=sum(1 for t in toks if t in up)
        if hits>=2 or (len(toks)<=2 and hits>=1):     # nome presente no MESMO resultado
            anchored.extend(_crmv_in(txt))
    if not anchored: return (None,None,None)
    for uf,num,cat in anchored:
        if uf and uf==(uf_hint or "").upper(): return (num,uf,cat)
    uf,num,cat=anchored[0]; return (num,uf or None,cat or None)

def extract(j, uf_hint=None, name=None):
    results=[o.get("title","")+" "+o.get("snippet","")+" "+o.get("link","") for o in j.get("organic",[])]
    blob = " ".join([j.get("knowledgeGraph",{}).get("title",""),
                     str(j.get("knowledgeGraph",{}).get("attributes",{})),
                     j.get("knowledgeGraph",{}).get("phoneNumber","")])
    for r in results: blob += " "+r
    for p in j.get("places",[]) or []:
        blob += " "+p.get("title","")+" "+str(p.get("phoneNumber",""))
    ig=None
    for h in RE_IG.findall(blob):
        if h.lower() not in IG_BAD and not h.isdigit(): ig=h.lower(); break
    wa=None
    m=RE_WA.search(blob)
    if m: wa=digits(m.group(1))
    if not wa:
        m=RE_ZAP.search(blob)
        if m and 10<=len(digits(m.group(1)))<=11: wa=digits(m.group(1))
    cel=None
    for c in (digits(x) for x in RE_TEL.findall(blob)):
        if len(c)==11 and c[2]=='9': cel=c; break
    kg_tel=digits(j.get("knowledgeGraph",{}).get("phoneNumber","")) or \
           (digits(j.get("places",[{}])[0].get("phoneNumber","")) if j.get("places") else "")
    site=None
    for o in j.get("organic",[]):
        l=o.get("link","")
        if l and not any(s in l for s in SOCIAL_DIR): site=l; break
    corte = bool(RE_CORTE.search(blob)); pet = bool(RE_PET.search(blob))
    sinal = "corte" if (corte and not pet) else "corte+pet" if (corte and pet) else "pet" if pet else "indef"
    crmv,crmv_uf,crmv_cat = extract_crmv(results, name, uf_hint)
    zt=bool(RE_ZOOTEC.search(blob)); vt=bool(RE_VET.search(blob))
    if crmv_cat=='Z' or (zt and not vt):   prof='zootecnista'
    elif crmv_cat=='V' or (vt and not zt): prof='veterinario'
    elif zt and vt:                        prof='ambos'
    else:                                  prof=''
    return ig, wa, cel, (kg_tel or None), site, sinal, crmv, crmv_uf, crmv_cat, prof

# CNAE 0162801 = inseminação (maior intenção), 7500100 = veterinária, 0162899 = apoio pecuária
SQL = """
SELECT e.cnpj_basico,
       COALESCE(vn.nome_pf, NULLIF(e.nome_fantasia,''), e.cnpj_basico) AS nome,
       e.municipio_nome AS municipio, e.uf, e.cnae_fiscal_principal AS cnae,
       e.ddd_1||e.telefone_1 AS tel_receita
FROM cnpj.estabelecimento_vet e
LEFT JOIN prospeccao.vet_nome vn ON vn.cnpj_basico=e.cnpj_basico
WHERE e.situacao_cadastral='02'
  AND (%(ufs)s IS NULL OR e.uf = ANY(%(ufs)s))
  AND (%(tiers)s IS NULL OR EXISTS (SELECT 1 FROM prospeccao.v_tecnico_lead vl
        WHERE vl.cnpj_basico=e.cnpj_basico AND vl.tier LIKE ANY(%(tiers)s)))
  AND (%(redo)s OR NOT EXISTS (SELECT 1 FROM prospeccao.tecnico_social s WHERE s.cnpj_basico=e.cnpj_basico))
ORDER BY (e.cnae_fiscal_principal='0162801') DESC, e.nome_fantasia
LIMIT %(lim)s;
"""

def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.tecnico_social(
        cnpj_basico varchar(8) PRIMARY KEY, nome text, municipio text, uf text, cnae text,
        instagram text, whatsapp text, celular text, tel_kg text, tel_receita text,
        site text, sinal text, status text, buscado_em timestamptz DEFAULT now());
        ALTER TABLE prospeccao.tecnico_social ADD COLUMN IF NOT EXISTS crmv text;
        ALTER TABLE prospeccao.tecnico_social ADD COLUMN IF NOT EXISTS crmv_uf text;
        ALTER TABLE prospeccao.tecnico_social ADD COLUMN IF NOT EXISTS crmv_cat text;
        ALTER TABLE prospeccao.tecnico_social ADD COLUMN IF NOT EXISTS profissao text;""")
    cur.execute(SQL, dict(ufs=UFS, tiers=TIERS, redo=A.redo, lim=A.limit))
    rows=cur.fetchall()
    print(f"[Serper técnicos: {len(rows)} alvos | ufs={UFS or 'NACIONAL'}]", file=sys.stderr, flush=True)
    hw=hc=ht=hcorte=hcrmv=hzoo=0
    for i,row in enumerate(rows,1):
        nm=re.sub(r'\b(LTDA|S/?A|EIRELI|ME|EPP)\b','',row["nome"],flags=re.I).strip()
        q=f'{nm} {row["municipio"] or ""} {row["uf"]} CRMV veterinário OR zootecnista OR inseminação OR IATF'
        try:
            ig,wa,cel,kg,site,sinal,crmv,crmv_uf,crmv_cat,prof=extract(serper(q), row["uf"], nm)
        except Exception as e:
            print(f"  {i} ERRO {str(e)[:50]}", file=sys.stderr, flush=True); time.sleep(2); continue
        st="whatsapp" if (wa or kg) else "celular" if cel else "instagram" if ig else "site" if site else "nada"
        hw+=bool(wa); hc+=bool(cel); ht+=bool(kg); hcorte+=(sinal in ("corte","corte+pet")); hcrmv+=bool(crmv); hzoo+=(prof=='zootecnista')
        cur.execute("""INSERT INTO prospeccao.tecnico_social
            (cnpj_basico,nome,municipio,uf,cnae,instagram,whatsapp,celular,tel_kg,tel_receita,site,sinal,status,crmv,crmv_uf,crmv_cat,profissao)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT(cnpj_basico) DO UPDATE SET instagram=EXCLUDED.instagram,whatsapp=EXCLUDED.whatsapp,
            celular=EXCLUDED.celular,tel_kg=EXCLUDED.tel_kg,site=EXCLUDED.site,sinal=EXCLUDED.sinal,
            status=EXCLUDED.status,crmv=EXCLUDED.crmv,crmv_uf=EXCLUDED.crmv_uf,crmv_cat=EXCLUDED.crmv_cat,profissao=EXCLUDED.profissao,buscado_em=now()""",
            (row["cnpj_basico"],nm,row["municipio"],row["uf"],row["cnae"],ig,wa,cel,kg,row["tel_receita"],site,sinal,st,crmv,crmv_uf,crmv_cat,prof))
        time.sleep(0.4)
        if i%25==0: print(f"  {i}/{len(rows)} | WhatsApp {hw} · cel {hc} · corte {hcorte} · CRMV {hcrmv} · zootec {hzoo}", file=sys.stderr, flush=True)
    n=max(len(rows),1)
    print(f"\n[FIM] {len(rows)} | WhatsApp {hw} · cel {hc} · CORTE {hcorte} ({100*hcorte//n}%) · CRMV {hcrmv} ({100*hcrmv//n}%) · ZOOTEC {hzoo}", file=sys.stderr, flush=True)

if __name__=="__main__":
    main()
