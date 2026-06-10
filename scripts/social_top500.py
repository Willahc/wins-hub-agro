#!/usr/bin/env python3
"""Piloto Instagram->WhatsApp nos 500: busca DuckDuckGo o Instagram + WhatsApp da fazenda
e extrai do resultado (IG direto é murado/429, então não tocamos nele). Canal que parece
ser o real do agro. GRÁTIS. Polido (throttle + backoff) p/ não tomar bloqueio.

Roda no container api: docker exec wins_agro_v1_api_1 python /app/social_top500.py
"""
import os, re, sys, time, random
import psycopg2, psycopg2.extras, httpx

DB = dict(host=os.getenv("DB_HOST","db"), port=int(os.getenv("DB_PORT",5432)),
          dbname=os.getenv("POSTGRES_DB","wins_agro"), user=os.getenv("POSTGRES_USER","postgres"),
          password=os.getenv("POSTGRES_PASSWORD",""))
UAS = ["Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
       "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36",
       "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16 Safari/605.1.15"]

IG_BAD = {"p","explore","reel","reels","tv","accounts","about","privacy","legal","developer","directory"}
RE_IG  = re.compile(r'instagram\.com/([A-Za-z0-9_.]{2,30})', re.I)
RE_WA  = re.compile(r'(?:wa\.me/|api\.whatsapp\.com/send\?phone=)(\+?\d{10,13})', re.I)
RE_ZAP = re.compile(r'(?:whats|whatsapp|zap|cel\.?|celular)[^0-9]{0,14}(\(?\d{2}\)?\s?9\d{4}[-\s]?\d{4})', re.I)
RE_TEL = re.compile(r'\(?\d{2}\)?\s?9?\d{4}[-\s]?\d{4}')

def short_razao(r):
    r = re.sub(r'\b(LTDA|S/?A|S\.A\.?|EIRELI|ME|EPP|PARTICIPACOES|E PARTICIPACOES|AGROPECUARIA|AGRO PECUARIA|AGRONEGOCIOS|ADMINISTRADORA DE BENS)\b','',r,flags=re.I)
    return re.sub(r'\s+',' ',r).strip()[:45]

def ddg(q, ua):
    r = httpx.get("https://lite.duckduckgo.com/lite/", params={"q":q},
                  headers={"User-Agent":ua,"Accept-Language":"pt-BR,pt"}, timeout=15, follow_redirects=True)
    return r.status_code, (r.text if r.status_code==200 else "")

def digits(s): return re.sub(r'\D','',s or '')

def search_farm(row, ua):
    q = f'{short_razao(row["razao"])} {row["municipio"]} instagram whatsapp'
    for attempt in range(3):
        try:
            st, t = ddg(q, ua)
            if st == 200: break
            time.sleep(20 + attempt*20)
        except Exception:
            time.sleep(8)
            t = ""
    else:
        return None
    # instagram handle
    ig = None
    for h in RE_IG.findall(t):
        if h.lower() not in IG_BAD and not h.isdigit():
            ig = h.lower(); break
    # whatsapp: wa.me primeiro, depois "whatsapp <num>"
    wa = None
    m = RE_WA.search(t)
    if m: wa = digits(m.group(1))
    if not wa:
        m = RE_ZAP.search(t)
        if m and 10 <= len(digits(m.group(1))) <= 11: wa = digits(m.group(1))
    # telefone celular genérico no texto (menor confiança)
    cel = None
    for c in (digits(x) for x in RE_TEL.findall(t)):
        if len(c)==11 and c[2]=='9':  # celular
            cel = c; break
    return dict(cnpj_basico=row["cnpj_basico"], instagram=ig, whatsapp=wa, celular=cel,
                status=("whatsapp" if wa else "celular" if cel else "instagram" if ig else "nada"))

def main():
    conn = psycopg2.connect(**DB); conn.autocommit=True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.top500_social(
        cnpj_basico varchar(8) PRIMARY KEY, instagram text, whatsapp text, celular text,
        status text, buscado_em timestamptz DEFAULT now());""")
    cur.execute("SELECT cnpj_basico, razao, municipio, uf FROM prospeccao.top500_pilot ORDER BY rank")
    rows = cur.fetchall()
    print(f"[Instagram->WhatsApp em {len(rows)} fazendas via DDG]", file=sys.stderr, flush=True)
    agg = {}; hit_ig=hit_wa=hit_cel=0; blocked=0
    for i, row in enumerate(rows, 1):
        res = search_farm(row, random.choice(UAS))
        time.sleep(2.2 + random.random())   # polido
        if res is None:
            blocked += 1
            cur.execute("INSERT INTO prospeccao.top500_social(cnpj_basico,status) VALUES(%s,'bloqueado') ON CONFLICT(cnpj_basico) DO UPDATE SET status='bloqueado',buscado_em=now()",(row["cnpj_basico"],))
            continue
        agg[res["status"]] = agg.get(res["status"],0)+1
        hit_ig += bool(res["instagram"]); hit_wa += bool(res["whatsapp"]); hit_cel += bool(res["celular"])
        cur.execute("""INSERT INTO prospeccao.top500_social(cnpj_basico,instagram,whatsapp,celular,status)
            VALUES(%(cnpj_basico)s,%(instagram)s,%(whatsapp)s,%(celular)s,%(status)s)
            ON CONFLICT(cnpj_basico) DO UPDATE SET instagram=EXCLUDED.instagram,whatsapp=EXCLUDED.whatsapp,
            celular=EXCLUDED.celular,status=EXCLUDED.status,buscado_em=now()""", res)
        if i % 25 == 0:
            print(f"  {i}/{len(rows)} | IG {hit_ig} · WhatsApp {hit_wa} · cel {hit_cel} · bloq {blocked}", file=sys.stderr, flush=True)
    n=len(rows)
    print(f"\n[FIM] {n} | Instagram {hit_ig} ({100*hit_ig//n}%) · WhatsApp {hit_wa} ({100*hit_wa//n}%) · celular {hit_cel} ({100*hit_cel//n}%) · bloqueado {blocked}", file=sys.stderr, flush=True)

if __name__ == "__main__":
    main()
