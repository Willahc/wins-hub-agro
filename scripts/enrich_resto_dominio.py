#!/usr/bin/env python3
"""Passo ANTES do Hunter (jun/13, ideia do William): p/ o operador jovem SEM domínio próprio,
buscar a PESSOA no Google/LinkedIn/Instagram (Serper) e trazer uma REFERÊNCIA:
  - domínio corporativo candidato (site da empresa/fazenda dele) -> alimenta o Hunter depois
  - perfil LinkedIn / handle Instagram -> referência manual
  - e-mail direto no snippet -> pula o Hunter
Lê prospeccao.hunter_resto_todo (prioriza sinal genético). Grava prospeccao.resto_referencia.
Uso (dentro do api, que já tem SERPER_API_KEY+POSTGRES_PASSWORD no env):
  docker cp scripts/enrich_resto_dominio.py wins_agro_v1_api_1:/tmp/ && \
  docker exec wins_agro_v1_api_1 python /tmp/enrich_resto_dominio.py [LIM] [MAXPRI]"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx

KEY = os.getenv("SERPER_API_KEY","").strip()
LIM = int(sys.argv[1]) if len(sys.argv)>1 else 60
MAXPRI = int(sys.argv[2]) if len(sys.argv)>2 else 2   # 1=alta 2=+media 3=+baixa
MODO = sys.argv[3] if len(sys.argv)>3 else "pessoa"   # pessoa = "nome" empresa ; marca = brand-centric
DB = dict(host="db", dbname="wins_agro", user="postgres", password=os.getenv("POSTGRES_PASSWORD",""))

# domínios que NÃO são site corporativo do dono (social, agregador, diretório, notícia, gov, busca)
BAD_DOM = re.compile(r'(instagram|facebook|fb\.com|linkedin|twitter|x\.com|youtube|youtu\.be|tiktok|'
    r'linktr|wa\.me|whatsapp|t\.me|telegram|google|globo|uol\.com|terra\.com|ig\.com|r7\.com|'
    r'wikipedia|jusbrasil|escavador|cnpj|cnpja|econodata|consultasocio|portaldbo|beefpoint|'
    r'gov\.br|jus\.br|org\.br|edu\.br|mil\.br|gmail|hotmail|outlook|yahoo|live\.com|bol\.com|'
    r'mercadolivre|olx|enjoei|tray|vtex|wordpress|blogspot|wixsite|abril\.com|estadao|folha)', re.I)
RE_EMAIL = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b')
RE_IG = re.compile(r'instagram\.com/([A-Za-z0-9_.]{2,30})', re.I)
RE_LI = re.compile(r'(linkedin\.com/in/[A-Za-z0-9\-_%]+)', re.I)
IG_BAD = {"p","explore","reel","reels","tv","accounts","about","privacy","legal","stories","directory","s"}
STOP = set("LTDA SA EIRELI ME EPP AGROPECUARIA AGRO PECUARIA AGROPASTORIL AGRICOLA FAZENDA FAZENDAS "
           "EMPREENDIMENTOS PARTICIPACOES E DE DA DO DOS DAS SAO SANTA SANTO".split())

def reg_domain(link):
    m = re.match(r'https?://([^/]+)', link or '')
    if not m: return None
    host = m.group(1).lower().lstrip('www.')
    parts = host.split('.')
    if len(parts) < 2: return None
    # pega o registrável (cobre .com.br / .com)
    if len(parts) >= 3 and parts[-2] in ('com','net','org','agr','ind','eng','adv') and parts[-1]=='br':
        return '.'.join(parts[-3:])
    return '.'.join(parts[-2:])

def toks(s):
    return {t for t in re.sub(r'[^A-Za-z ]',' ',(s or '').upper()).split() if len(t)>=4 and t not in STOP}

def serper(q, tries=3):
    for t in range(tries):
        try:
            r = httpx.post("https://google.serper.dev/search",
                headers={"X-API-KEY":KEY,"Content-Type":"application/json"},
                json={"q":q,"gl":"br","hl":"pt","num":10}, timeout=20)
            r.raise_for_status(); return r.json()
        except Exception:
            if t==tries-1: raise
            time.sleep(2*(t+1))

def harvest(j, name_tok, farm_tok):
    cand = {}   # dominio -> melhor confianca
    li=ig=email=None
    organic = j.get("organic",[]) or []
    for o in organic:
        link=o.get("link",""); blob=(o.get("title","")+" "+o.get("snippet","")+" "+link)
        if not li:
            m=RE_LI.search(blob);  li = m.group(1) if m else None
        if not ig:
            h=next((x.lower() for x in RE_IG.findall(blob) if x.lower() not in IG_BAD and not x.isdigit()),None); ig=h
        if not email:
            for e in RE_EMAIL.findall(blob):
                d=e.split('@')[1].lower()
                if not BAD_DOM.search(d): email=e.lower(); break
        d = reg_domain(link)
        if not d or BAD_DOM.search(d): continue
        label = d.split('.')[0]                      # rótulo principal (sem TLD)
        dtok = toks(label)
        # SÓ conta como domínio REAL do dono se o nome da fazenda casar estruturalmente com o domínio
        # (token exato OU token distintivo da fazenda é substring do rótulo concatenado, ex: CAMPARINO in fazendacamparino).
        hit = bool(dtok & farm_tok) or any(t in label.upper() for t in farm_tok if len(t)>=5)
        if not hit: continue                         # descarta agregador/classificado/notícia
        conf='alta'
        if d not in cand: cand[d]=conf
    best=None
    for c in ('alta','media','baixa'):
        ds=[d for d,cc in cand.items() if cc==c]
        if ds: best=(ds[0],c); break
    return best, li, ig, email, len(cand)

def main():
    if not KEY: print("FALTA SERPER_API_KEY", file=sys.stderr); sys.exit(2)
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.resto_referencia(
        cnpj_basico varchar(8) PRIMARY KEY, nome text, company_hint text, uf text, sinal text,
        dominio_cand text, dominio_conf text, linkedin text, instagram text, email_direto text,
        n_dominios int, buscado_em timestamptz DEFAULT now());""")
    cur.execute("""SELECT cnpj_basico, operador, company_hint, razao, uf, municipio, sinal, pri
                   FROM prospeccao.hunter_resto_todo
                   WHERE pri<=%s AND cnpj_basico NOT IN (SELECT cnpj_basico FROM prospeccao.resto_referencia)
                   ORDER BY pri, capital_mi DESC NULLS LAST LIMIT %s""",(MAXPRI,LIM))
    rows=cur.fetchall()
    NSHARD=int(os.getenv("NSHARD","1")); SHARD=int(os.getenv("SHARD","0"))
    rows=[r for k,r in enumerate(rows) if k % NSHARD == SHARD]   # fatia disjunta p/ paralelizar
    print(f"[Harvest de domínio/referência: {len(rows)} operadores | MAXPRI={MAXPRI} | shard {SHARD}/{NSHARD}]", file=sys.stderr, flush=True)
    nd=nli=nig=nem=0
    with httpx.Client():
        for i,r in enumerate(rows,1):
            nome=r['operador']; muni=r['municipio'] or ''
            ntok=toks(nome); ftok=toks(r['razao'])
            if MODO=="marca":
                # busca a MARCA da fazenda (núcleo distintivo) + contexto pecuária — não a pessoa
                marca=" ".join(sorted(ftok)) or r["company_hint"]
                q=f'{marca} {r["uf"]} (fazenda OR agropecuaria OR nelore OR pecuaria)'.strip()
            else:
                q=f'"{nome}" {r["company_hint"]} {muni} {r["uf"]}'.strip()
            try: j=serper(q)
            except Exception:
                print(f"  {i} Serper falhou — pulado", file=sys.stderr); continue
            best,li,ig,email,n=harvest(j,ntok,ftok)
            dom,conf=(best if best else (None,None))
            if dom: nd+=1
            if li: nli+=1
            if ig: nig+=1
            if email: nem+=1
            cur.execute("""INSERT INTO prospeccao.resto_referencia
                (cnpj_basico,nome,company_hint,uf,sinal,dominio_cand,dominio_conf,linkedin,instagram,email_direto,n_dominios)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET
                dominio_cand=EXCLUDED.dominio_cand,dominio_conf=EXCLUDED.dominio_conf,linkedin=EXCLUDED.linkedin,
                instagram=EXCLUDED.instagram,email_direto=EXCLUDED.email_direto,n_dominios=EXCLUDED.n_dominios,buscado_em=now()""",
                (r['cnpj_basico'],nome,r['company_hint'],r['uf'],r['sinal'],dom,conf,li,ig,email,n))
            time.sleep(0.3)
            if i%20==0: print(f"  {i}/{len(rows)} | dom {nd} li {nli} ig {nig} email {nem}", file=sys.stderr, flush=True)
    n=len(rows) or 1
    print(f"\n[FIM] {len(rows)} | domínio {nd} ({100*nd//n}%) | LinkedIn {nli} ({100*nli//n}%) | "
          f"Instagram {nig} ({100*nig//n}%) | e-mail direto {nem} ({100*nem//n}%)", file=sys.stderr, flush=True)
if __name__=="__main__": main()
