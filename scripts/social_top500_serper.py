#!/usr/bin/env python3
"""Piloto Instagram->WhatsApp nos 500 via SERPER (Google Search API, JSON, sem bloqueio de IP).
Pra cada fazenda: 1 busca no Google -> extrai Instagram, WhatsApp (wa.me / 'whatsapp <num>'),
telefone do knowledgeGraph/places, e o site próprio. Canal real do agro.

Lê a chave de SERPER_API_KEY (env). Free tier do Serper (2.500 créditos) cobre os 500 de sobra.
Roda: docker exec -e SERPER_API_KEY=xxxx wins_agro_v1_api_1 python /app/social_top500_serper.py
"""
import os, re, sys, time
import psycopg2, psycopg2.extras, httpx

KEY = os.getenv("SERPER_API_KEY","").strip()
if not KEY:
    print("FALTA SERPER_API_KEY", file=sys.stderr); sys.exit(2)
DB = dict(host=os.getenv("DB_HOST","db"), port=int(os.getenv("DB_PORT",5432)),
          dbname=os.getenv("POSTGRES_DB","wins_agro"), user=os.getenv("POSTGRES_USER","postgres"),
          password=os.getenv("POSTGRES_PASSWORD",""))

IG_BAD = {"p","explore","reel","reels","tv","accounts","about","privacy","legal","developer","directory","stories"}
RE_IG  = re.compile(r'instagram\.com/([A-Za-z0-9_.]{2,30})', re.I)
RE_WA  = re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=|whatsapp\.com/send\?phone=)(\+?\d{10,13})', re.I)
RE_ZAP = re.compile(r'(?:whats\s?app|whatsapp|zap)[^0-9]{0,16}(\(?\d{2}\)?\s?9\d{4}[-\s]?\d{4})', re.I)
RE_TEL = re.compile(r'\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}')
SOCIAL_DIR = ('instagram.com','facebook.com','linkedin.com','youtube.com','twitter.com','tiktok.com',
              'econodata','consultasocio','cnpj','escavador','solutudo','apontador','telelistas','guiamais')

def digits(s): return re.sub(r'\D','',s or '')

def serper(q):
    r = httpx.post("https://google.serper.dev/search",
                   headers={"X-API-KEY":KEY,"Content-Type":"application/json"},
                   json={"q":q,"gl":"br","hl":"pt","num":10}, timeout=20)
    r.raise_for_status(); return r.json()

def extract(j, razao):
    blob = " ".join([j.get("knowledgeGraph",{}).get("title",""),
                     str(j.get("knowledgeGraph",{}).get("attributes",{})),
                     j.get("knowledgeGraph",{}).get("phoneNumber","")])
    for o in j.get("organic",[]):
        blob += " "+o.get("title","")+" "+o.get("snippet","")+" "+o.get("link","")
    for p in j.get("places",[]) or []:
        blob += " "+p.get("title","")+" "+str(p.get("phoneNumber",""))
    # instagram handle
    ig=None
    for h in RE_IG.findall(blob):
        if h.lower() not in IG_BAD and not h.isdigit(): ig=h.lower(); break
    # whatsapp
    wa=None
    m=RE_WA.search(blob)
    if m: wa=digits(m.group(1))
    if not wa:
        m=RE_ZAP.search(blob)
        if m and 10<=len(digits(m.group(1)))<=11: wa=digits(m.group(1))
    # celular genérico
    cel=None
    for c in (digits(x) for x in RE_TEL.findall(blob)):
        if len(c)==11 and c[2]=='9': cel=c; break
    # telefone do knowledgeGraph/places (alta confiança)
    kg_tel=digits(j.get("knowledgeGraph",{}).get("phoneNumber","")) or \
           (digits(j.get("places",[{}])[0].get("phoneNumber","")) if j.get("places") else "")
    # site próprio (1º organic que não é social/diretório)
    site=None
    for o in j.get("organic",[]):
        l=o.get("link","")
        if l and not any(s in l for s in SOCIAL_DIR): site=l; break
    return ig, wa, cel, (kg_tel or None), site

def main():
    conn=psycopg2.connect(**DB); conn.autocommit=True
    cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.top500_social(
        cnpj_basico varchar(8) PRIMARY KEY, instagram text, whatsapp text, celular text,
        tel_kg text, site text, status text, buscado_em timestamptz DEFAULT now());""")
    for col in ("tel_kg","site"):
        cur.execute(f"ALTER TABLE prospeccao.top500_social ADD COLUMN IF NOT EXISTS {col} text;")
    cur.execute("SELECT cnpj_basico, razao, municipio, uf FROM prospeccao.top500_pilot ORDER BY rank")
    rows=cur.fetchall()
    print(f"[Serper Instagram->WhatsApp em {len(rows)} fazendas]", file=sys.stderr, flush=True)
    hi=hw=hc=ht=0
    for i,row in enumerate(rows,1):
        rz=re.sub(r'\b(LTDA|S/?A|EIRELI|ME|EPP)\b','',row["razao"],flags=re.I).strip()
        q=f'"{rz}" {row["municipio"]} {row["uf"]} (instagram OR whatsapp OR contato)'
        try:
            ig,wa,cel,kg,site=extract(serper(q), rz)
        except Exception as e:
            print(f"  {i} ERRO {str(e)[:50]}", file=sys.stderr, flush=True); time.sleep(2); continue
        st="whatsapp" if (wa or kg) else "celular" if cel else "instagram" if ig else "site" if site else "nada"
        hi+=bool(ig); hw+=bool(wa); hc+=bool(cel); ht+=bool(kg)
        cur.execute("""INSERT INTO prospeccao.top500_social(cnpj_basico,instagram,whatsapp,celular,tel_kg,site,status)
            VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(cnpj_basico) DO UPDATE SET instagram=EXCLUDED.instagram,
            whatsapp=EXCLUDED.whatsapp,celular=EXCLUDED.celular,tel_kg=EXCLUDED.tel_kg,site=EXCLUDED.site,
            status=EXCLUDED.status,buscado_em=now()""",(row["cnpj_basico"],ig,wa,cel,kg,site,st))
        time.sleep(0.4)
        if i%25==0: print(f"  {i}/{len(rows)} | IG {hi} · WhatsApp {hw} · tel-Google {ht} · cel {hc}", file=sys.stderr, flush=True)
    n=len(rows)
    print(f"\n[FIM] {n} | Instagram {hi} ({100*hi//n}%) · WhatsApp {hw} ({100*hw//n}%) · tel-Google {ht} ({100*ht//n}%) · cel {hc} ({100*hc//n}%)", file=sys.stderr, flush=True)

if __name__=="__main__":
    main()
