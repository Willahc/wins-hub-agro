#!/usr/bin/env python3
"""Trabalho completo no ICP genético (527 alta): VALIDAÇÃO + TRIAGEM REPUTACIONAL + SOCIAL.
- E-mail: MX real (DoH, grátis).
- Reputacional: Serper busca razão + termos de risco (trabalho escravo / lista suja / embargo
  IBAMA / desmatamento / fraude). Só flag se o resultado cita a fazenda E o termo (corta homônimo).
- Social: Serper acha Instagram + WhatsApp; celular só vale se DDD bate com o da fazenda (filtro de
  qualidade aprendido no piloto).
Entrega tabela prospeccao.icp527_screen. Roda c/ SERPER_API_KEY no env.
"""
import os, re, sys, time, unicodedata
import psycopg2, psycopg2.extras, httpx
from concurrent.futures import ThreadPoolExecutor, as_completed

KEY = os.getenv("SERPER_API_KEY","").strip()
if not KEY: print("FALTA SERPER_API_KEY", file=sys.stderr); sys.exit(2)
DB = dict(host=os.getenv("DB_HOST","db"), port=int(os.getenv("DB_PORT",5432)),
          dbname=os.getenv("POSTGRES_DB","wins_agro"), user=os.getenv("POSTGRES_USER","postgres"),
          password=os.getenv("POSTGRES_PASSWORD",""))
FREE = {'gmail.com','hotmail.com','outlook.com','yahoo.com.br','yahoo.com','live.com','bol.com.br',
        'terra.com.br','uol.com.br','icloud.com','msn.com','globo.com','me.com'}
IG_BAD = {"p","explore","reel","reels","tv","accounts","about","stories","directory"}
RE_IG  = re.compile(r'instagram\.com/([A-Za-z0-9_.]{2,30})', re.I)
RE_WA  = re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d{10,13})', re.I)
RE_TEL = re.compile(r'\(?\d{2}\)?\s?9\d{4}[-\s]?\d{4}')
RISK = re.compile(r'(trabalho escravo|an[aá]logo[ -]?[àa]?[ -]?escravid[ãa]o|lista suja|escravid[ãa]o|'
                  r'trabalho infantil|embargo|ibama|desmatamento|crime ambiental|deten[çc][ãa]o|'
                  r'condenad[oa]|fraude|lavagem de dinheiro|trabalho deg)', re.I)

def strip_ac(s): return unicodedata.normalize("NFKD",s or "").encode("ascii","ignore").decode()
def digits(s): return re.sub(r'\D','',s or '')
def core_tokens(razao):
    s = strip_ac(razao).upper()
    s = re.sub(r'[^A-Z0-9 ]',' ',s)
    stop={"FAZENDA","AGROPECUARIA","AGRO","PECUARIA","LTDA","SA","S","A","EIRELI","ME","EPP",
          "PARTICIPACOES","RURAL","E","DA","DE","DO","DAS","DOS","CIA","COMERCIO"}
    return {t for t in s.split() if t not in stop and len(t)>3}

def doh_mx(dom):
    try:
        r=httpx.get("https://dns.google/resolve",params={"name":dom,"type":"MX"},timeout=8)
        j=r.json()
        if j.get("Status")==3: return "dominio_inexistente"
        return "mx_ok" if any(a.get("type")==15 for a in j.get("Answer",[])) else "sem_mx"
    except Exception: return "erro_dns"

def serper(q):
    r=httpx.post("https://google.serper.dev/search",headers={"X-API-KEY":KEY,"Content-Type":"application/json"},
                 json={"q":q,"gl":"br","hl":"pt","num":10},timeout=20)
    r.raise_for_status(); return r.json()

def reputacional(razao, municipio):
    toks=core_tokens(razao)
    q=f'"{razao}" {municipio} (trabalho escravo OR "lista suja" OR embargo IBAMA OR desmatamento OR fraude OR condenado)'
    try: j=serper(q)
    except Exception: return None, None
    for o in j.get("organic",[]):
        blob=f"{o.get('title','')} {o.get('snippet','')}"
        up=strip_ac(blob).upper()
        if RISK.search(blob) and any(t in up for t in toks):   # cita a fazenda E o termo
            m=RISK.search(blob)
            return m.group(1).lower(), o.get("link","")
    return None, None

def social(razao, municipio, uf, farm_ddd):
    q=f'"{razao}" {municipio} {uf} (instagram OR whatsapp OR contato)'
    try: j=serper(q)
    except Exception: return None,None,None
    blob=" ".join(o.get("title","")+" "+o.get("snippet","")+" "+o.get("link","") for o in j.get("organic",[]))
    ig=next((h.lower() for h in RE_IG.findall(blob) if h.lower() not in IG_BAD and not h.isdigit()),None)
    wa=None
    m=RE_WA.search(blob)
    if m: wa=digits(m.group(1))
    cel=None
    for c in (digits(x) for x in RE_TEL.findall(blob)):
        if len(c)==11 and c[:2]==farm_ddd:   # SÓ celular com DDD da fazenda (filtro de qualidade)
            cel=c; break
    return ig, wa, cel

def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.icp527_screen(
        cnpj_basico varchar(8) PRIMARY KEY, razao text, decisor text, uf text, municipio text,
        touros_nelore int, email text, email_status text, telefone text,
        instagram text, whatsapp text, celular text,
        risco text, risco_fonte text, screened_at timestamptz DEFAULT now());""")
    cur.execute("""
        SELECT g.cnpj_basico, g.razao, ld.decisor_top AS decisor, g.uf, g.municipio, g.touros_nelore,
               e.correio_eletronico AS email, e.ddd_1||e.telefone_1 AS telefone, e.ddd_1 AS ddd
        FROM prospeccao.prospect_genetica g
        JOIN prospeccao.lead_decisor ld ON ld.cnpj_basico=g.cnpj_basico
        JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico=g.cnpj_basico
             AND e.cnae_fiscal_principal='0151201' AND e.situacao_cadastral='02'
        WHERE g.confianca='alta'
        GROUP BY g.cnpj_basico, g.razao, ld.decisor_top, g.uf, g.municipio, g.touros_nelore,
                 e.correio_eletronico, e.ddd_1, e.telefone_1
        ORDER BY g.touros_nelore DESC""")
    rows=cur.fetchall()
    # dedupe por cnpj_basico (o GROUP BY pode trazer +1 estab por empresa)
    seen=set(); uniq=[]
    for r in rows:
        if r["cnpj_basico"] in seen: continue
        seen.add(r["cnpj_basico"]); uniq.append(r)
    rows=uniq
    print(f"[screen ICP genético: {len(rows)} fazendas alta-confiança]", file=sys.stderr, flush=True)

    # MX em lote (domínios únicos)
    doms=sorted({(r["email"].split("@",1)[1].lower()) for r in rows if r["email"] and "@" in r["email"]}-FREE)
    mx={}
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs={ex.submit(doh_mx,d):d for d in doms}
        for f in as_completed(futs): mx[futs[f]]=f.result()

    risco_n=ig_n=wa_n=cel_n=email_ok=0
    for i,r in enumerate(rows,1):
        # email
        em=r["email"]; es="sem_email"
        if em and "@" in em:
            dom=em.split("@",1)[1].lower()
            es="free_entregavel" if dom in FREE else mx.get(dom,"erro_dns")
        if es in ("mx_ok","free_entregavel"): email_ok+=1
        # reputacional + social (2 buscas serper)
        risco,fonte=reputacional(r["razao"], r["municipio"]); time.sleep(0.3)
        ig,wa,cel=social(r["razao"], r["municipio"], r["uf"], r["ddd"]); time.sleep(0.3)
        if risco: risco_n+=1
        ig_n+=bool(ig); wa_n+=bool(wa); cel_n+=bool(cel)
        cur.execute("""INSERT INTO prospeccao.icp527_screen
          (cnpj_basico,razao,decisor,uf,municipio,touros_nelore,email,email_status,telefone,instagram,whatsapp,celular,risco,risco_fonte)
          VALUES (%(cnpj_basico)s,%(razao)s,%(decisor)s,%(uf)s,%(municipio)s,%(touros_nelore)s,%(email)s,%(es)s,%(telefone)s,%(ig)s,%(wa)s,%(cel)s,%(risco)s,%(fonte)s)
          ON CONFLICT (cnpj_basico) DO UPDATE SET email_status=EXCLUDED.email_status,instagram=EXCLUDED.instagram,
            whatsapp=EXCLUDED.whatsapp,celular=EXCLUDED.celular,risco=EXCLUDED.risco,risco_fonte=EXCLUDED.risco_fonte,screened_at=now()""",
          dict(r, es=es, ig=ig, wa=wa, cel=cel, risco=risco, fonte=fonte))
        if i%25==0: print(f"  {i}/{len(rows)} | email-ok {email_ok} · IG {ig_n} · WhatsApp {wa_n} · cel {cel_n} · RISCO {risco_n}", file=sys.stderr, flush=True)
    n=len(rows)
    print(f"\n[FIM] {n} | email vivo {email_ok} ({100*email_ok//n}%) · IG {ig_n} · WhatsApp {wa_n} · celular-DDDok {cel_n} · RISCO reputacional {risco_n}", file=sys.stderr, flush=True)

if __name__=="__main__":
    main()
