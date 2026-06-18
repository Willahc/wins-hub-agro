#!/usr/bin/env python3
"""Fecha o canal e-mail das fazendas do TOP-3/UF que estao no buraco real:
e-mail de contador/terceiro ou SEM e-mail. O Hunter.io so funciona com dominio
proprio -> 1o descobre o dominio oficial via Serper, depois (se HK no ambiente)
roda o Hunter email-finder com o nome do decisor. Sem HK, so descobre o dominio
e enfileira. Idempotente.

Roda no host. HK (chave Hunter) opcional via env: HK=xxxx python scripts/hunter_gap_top3.py
"""
import os, re, sys, time, pathlib, json
import psycopg2, psycopg2.extras, httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent
env = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1); env[k.strip()] = v.strip()

SERPER_KEY = env.get("SERPER_API_KEY", "").strip()
HK = os.environ.get("HK", "").strip()        # chave Hunter (secret, passada em runtime)
DB = dict(host="127.0.0.1", port=int(env.get("DB_PORT", 5432)),
          dbname=env.get("POSTGRES_DB", "wins_agro"),
          user=env.get("POSTGRES_USER", "postgres"),
          password=env.get("POSTGRES_PASSWORD", ""))

FREE = {"gmail.com","hotmail.com","outlook.com","yahoo.com.br","yahoo.com","live.com",
        "bol.com.br","terra.com.br","uol.com.br","icloud.com","uol.com","terra.ocm.br"}
BAD_DOM = re.compile(r"(contab|assessor|advoc|advog|consultor|contador|\.adv\.|spheraconsultoria)")
# dominios que nunca sao site da fazenda
SKIP = re.compile(r"(facebook|instagram|linkedin|youtube|twitter|tiktok|wikipedia|google|"
                  r"jusbrasil|econodata|cnpj|consultasocio|empresascnpj|guiamais|serasa|"
                  r"experian|listasrapidas|listamais|escavador|informecadastral|cnpja|"
                  r"solutudo|apontador|telelistas|guiafacil|encontreempresa|"
                  r"gov\.br|receita|globo|terra\.com|mercadolivre|olx|elo7|b2brazil|"
                  r"triceleads|juridicoonline|farmby|leadlovers|rdstation|^app\.)")
SUF = {"FILHO","FILHA","JUNIOR","NETO","NETA","SOBRINHO","JR"}


def split_nome(d):
    w = [x for x in re.sub(r"\(.*", "", d or "").strip().split() if len(x) > 1]
    if not w: return None, None
    first, last = w[0], w[-1]
    if last.upper() in SUF and len(w) >= 2: last = w[-2]
    return first, last


def serper(q):
    r = httpx.post("https://google.serper.dev/search",
                   headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                   json={"q": q, "gl": "br", "hl": "pt", "num": 10}, timeout=25)
    r.raise_for_status(); return r.json()


def descobre_dominio(fazenda, razao, municipio, uf):
    if not SERPER_KEY: return None
    q = f'"{razao}" {municipio} {uf} site OR contato'
    try:
        data = serper(q)
    except Exception:
        return None
    cand = []
    for o in data.get("organic", []):
        link = o.get("link", "")
        m = re.match(r"https?://([^/]+)/?", link)
        if not m: continue
        host = m.group(1).lower().replace("www.", "")
        if SKIP.search(host) or BAD_DOM.search(host): continue
        if host in FREE: continue
        if host.endswith(".com.br") or host.endswith(".agr.br") or host.endswith(".com") or host.endswith(".net.br"):
            cand.append(host)
    # so aceita dominio que CONTENHA um pedaco do nome da fazenda/razao
    # (site proprio real); senao trata como "sem dominio" — evita agregador/lixo.
    STOP = {"agropecuaria","fazenda","ltda","agro","participacoes","companhia","cia","rural","e"}
    toks = [t.lower() for t in re.findall(r"[A-Za-z]{4,}", (razao or "") + " " + (fazenda or ""))
            if t.lower() not in STOP]
    for h in cand:
        if any(t[:5] in h for t in toks):
            return h
    return None


def hunter_find(dom, decisor):
    first, last = split_nome(decisor)
    if not first: return None, None, "sem nome"
    try:
        j = httpx.get("https://api.hunter.io/v2/email-finder",
                      params={"domain": dom, "first_name": first, "last_name": last, "api_key": HK},
                      timeout=25).json()
        d = j.get("data", {})
        return d.get("email"), d.get("score"), ("achado" if d.get("email") else "vazio")
    except Exception as e:
        return None, None, f"erro:{type(e).__name__}"


def main():
    conn = psycopg2.connect(**DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # fila persistente
    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.hunter_gap_top3(
        cnpj text PRIMARY KEY, uf text, fazenda text, decisor text, classe text,
        dominio_descoberto text, email_hunter text, hunter_score int, status text,
        atualizado_em timestamptz DEFAULT now());""")

    cur.execute("""
      SELECT t.cnpj, t.uf, t.fazenda, t.decisor_nome AS decisor, t.municipio,
             ld.razao, ld.email, lower(split_part(ld.email,'@',2)) AS dom, ld.email_tier
      FROM prospeccao.prospect_top3_final t
      JOIN prospeccao.lead_demanda ld ON ld.cnpj_completo = t.cnpj
      WHERE ld.email IS NULL OR ld.email=''
         OR ld.email_tier='rfb-contador'
         OR lower(split_part(ld.email,'@',2)) ~ '(contab|assessor|advoc|advog|consultor|contador)'
      ORDER BY t.uf, t.rank_uf;
    """)
    rows = cur.fetchall()
    print(f"[{len(rows)} fazendas no buraco do e-mail (contador/3o ou sem e-mail)]", file=sys.stderr)
    if HK:
        print("[HK presente -> vai rodar Hunter nos dominios encontrados]", file=sys.stderr)
    else:
        print("[SEM HK -> so descobre dominio e enfileira; rode de novo com HK=xxxx p/ achar o e-mail]", file=sys.stderr)

    for r in rows:
        classe = "sem e-mail" if not r["email"] else ("contador" if (r["email_tier"] == "rfb-contador" or BAD_DOM.search(r["dom"] or "")) else "3o")
        dom = descobre_dominio(r["fazenda"], r["razao"], r["municipio"], r["uf"])
        email = score = None; status = "sem dominio publico"
        if dom:
            status = "dominio achado (aguarda Hunter)" if not HK else None
            if HK:
                email, score, status = hunter_find(dom, r["decisor"])
                if email:
                    # grava tambem no hunter_email canonico (mesma tabela dos outros)
                    cur.execute("""INSERT INTO prospeccao.hunter_email(cnpj_basico,decisor,dominio,email_decisor,score,status)
                        VALUES (left(regexp_replace(%s,'\\D','','g'),8),%s,%s,%s,%s,'achado')
                        ON CONFLICT (cnpj_basico) DO UPDATE SET email_decisor=EXCLUDED.email_decisor,
                        dominio=EXCLUDED.dominio, score=EXCLUDED.score, status='achado';""",
                        (r["cnpj"], r["decisor"], dom, email, score))
        cur.execute("""INSERT INTO prospeccao.hunter_gap_top3
            (cnpj,uf,fazenda,decisor,classe,dominio_descoberto,email_hunter,hunter_score,status,atualizado_em)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
            ON CONFLICT (cnpj) DO UPDATE SET dominio_descoberto=EXCLUDED.dominio_descoberto,
            email_hunter=COALESCE(EXCLUDED.email_hunter,prospeccao.hunter_gap_top3.email_hunter),
            hunter_score=EXCLUDED.hunter_score, status=EXCLUDED.status, classe=EXCLUDED.classe,
            atualizado_em=now();""",
            (r["cnpj"], r["uf"], r["fazenda"], r["decisor"], classe, dom, email, score, status))
        print(f"  {r['uf']} {r['fazenda'][:30]:<30} [{classe:9}] dom={dom or '-'} email={email or '-'} ({status})", file=sys.stderr)
        time.sleep(0.5)

    print("\n[fila em prospeccao.hunter_gap_top3]", file=sys.stderr)


if __name__ == "__main__":
    main()
