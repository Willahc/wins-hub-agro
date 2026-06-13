"""Ingestão ADITIVA de PREÇOS de sêmen LEITEIRO (Holandês, Jersey, Girolando,
Gir Leiteiro, Guzerá Leiteiro, Sindi) de duas lojas:

  CRV Brasil (loja Tray, JSON-LD schema.org/Product)  -> central CRVBR
  ABS Global (loja VTEX, /api/catalog_system)          -> central ABS

Para cada produto:
  1. classifica a raça pela URL/categoria;
  2. extrai (nome comercial, preço da dose convencional);
  3. casa por raça + nome normalizado a um mercado.reprodutor existente
     (preferindo touros com avaliação genética — ex.: Sumário Holandês);
  4. se não casar, cria um reprodutor "stub" (sexo M, registro CRV-SLUG-/ABS-)
     para que o preço fique catalogado e o touro apareça no app;
  5. grava a oferta em mercado.touro_oferta com bull_external_id + ON CONFLICT
     (idempotente; NÃO apaga ofertas de outras fontes).

Roda no container api:
  python ingest_dairy_precos.py
Lê /tmp/crv_dairy_prods.json (lista de URLs) e /tmp/abs_leite.json (produtos VTEX).
"""
import os
import re
import json
import time
import unicodedata
import httpx
import psycopg2

DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

# raça siglas/ids dos leiteiros
RACA = {"holandes": 21, "jersey": 23, "girolando": 38, "gir-leiteiro": 22,
        "guzera": 4, "sindi": 6}
# (Guzerá=4, Sindi=6 são zebuínos; aqui só leiteiros — Guzerá/Sindi leiteiros entram na sua raça)

STOP = {"FIV", "TE", "ET", "IA", "DA", "DO", "DE", "DOS", "DAS", "PB", "PO", "RG",
        "POI", "PP", "SEMEN", "CONVENCIONAL", "SEXADO", "LEITE", "HOLANDES", "HOLANDESA",
        "JERSEY", "GIROLANDO", "GIR", "LEITEIRO", "GUZERA", "SINDI", "PRETO", "BRANCO",
        "VERMELHO", "USA", "EUA", "HOLANDA", "BRASIL", "NOVA", "ZELANDIA", "ALEMANHA",
        "DOSE", "JR", "II", "III", "IV"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().upper()
    toks = re.findall(r"[A-Z0-9]+", s)
    toks = [t for t in toks if t not in STOP and len(t) >= 2]
    return " ".join(toks)


def breed_from_url(u):
    s = unicodedata.normalize("NFKD", u or "").encode("ascii", "ignore").decode().lower()
    if "jersolando" in s:
        return "girolando"
    if "jersey" in s:
        return "jersey"
    if "gir-leiteiro" in s or "gi-leiteiro" in s or "gi leiteiro" in s:
        return "gir-leiteiro"
    if "girolando" in s:
        return "girolando"
    if "guzera" in s:
        return "guzera"
    if "sindi" in s:
        return "sindi"
    if "holandes" in s or "holstein" in s or "frisian" in s:
        return "holandes"
    return None


def breed_from_cats(cats, name):
    blob = (" ".join(cats) + " " + name).lower()
    return breed_from_url(blob)


def jsonld_price(htmltext):
    for b in re.findall(r'application/ld\+json[^>]*>(.*?)</script>', htmltext, re.S):
        try:
            j = json.loads(b)
        except Exception:
            continue
        if not isinstance(j, dict):
            continue
        off = j.get("offers")
        price = None
        if isinstance(off, dict):
            price = off.get("price")
        elif isinstance(off, list) and off:
            price = off[0].get("price")
        if price not in (None, "", "0"):
            try:
                return j.get("name"), float(str(price).replace(",", "."))
            except ValueError:
                return j.get("name"), None
    return None, None


def get_central(cur, conn, sigla, nome, site):
    cur.execute("SELECT id FROM catalogo.central WHERE sigla=%s", (sigla,))
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("SELECT COALESCE(MAX(id),0)+1 FROM catalogo.central")
    nid = cur.fetchone()[0]
    cur.execute("INSERT INTO catalogo.central (id,sigla,nome,site) VALUES (%s,%s,%s,%s)",
                (nid, sigla, nome, site))
    conn.commit()
    return nid


def load_breed_index(cur):
    """Mapa (raca_id, nome_normalizado) -> reprodutor_id, preferindo touros c/ avaliação."""
    cur.execute("""
        SELECT r.id, r.nome, r.raca_id,
               EXISTS(SELECT 1 FROM mercado.avaliacao a WHERE a.reprodutor_id=r.id) AS tem_aval
        FROM mercado.reprodutor r
        WHERE r.raca_id = ANY(%s)
    """, (list(set(RACA.values())),))
    idx = {}
    for rid, nome, raca, tem in cur.fetchall():
        key = (raca, norm(nome))
        if not key[1]:
            continue
        # prefere touro com avaliação genética
        cur_rid = idx.get(key)
        if cur_rid is None:
            idx[key] = (rid, tem)
        elif tem and not cur_rid[1]:
            idx[key] = (rid, tem)
    return {k: v[0] for k, v in idx.items()}


def ensure_reprodutor(cur, raca_id, registro, nome):
    cur.execute(
        """INSERT INTO mercado.reprodutor
             (registro, nome, especie_codigo, raca_id, sexo, fonte_referencia, coletado_em)
           VALUES (%s,%s,'BOV',%s,'M',%s, now())
           ON CONFLICT (registro, raca_id) DO UPDATE SET nome=EXCLUDED.nome
           RETURNING id""",
        (registro[:50], nome[:200], raca_id, "Loja leiteiro (stub preço)"),
    )
    return cur.fetchone()[0]


def upsert_oferta(cur, rid, central_id, nome_com, preco, url, ext_id, tipo, fonte):
    cur.execute(
        """INSERT INTO mercado.touro_oferta
             (reprodutor_id, central_id, nome_comercial, preco_dose_brl,
              url_oferta, bull_external_id, tipo_match, fonte_referencia, coletado_em)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now())
           ON CONFLICT (central_id, bull_external_id) WHERE bull_external_id IS NOT NULL
           DO UPDATE SET reprodutor_id=EXCLUDED.reprodutor_id,
                         nome_comercial=EXCLUDED.nome_comercial,
                         preco_dose_brl=EXCLUDED.preco_dose_brl,
                         url_oferta=EXCLUDED.url_oferta,
                         tipo_match=EXCLUDED.tipo_match,
                         fonte_referencia=EXCLUDED.fonte_referencia,
                         coletado_em=now()""",
        (rid, central_id, nome_com[:200], preco, (url or "")[:500], ext_id[:50],
         tipo, fonte),
    )


def ingest_crv(cur, conn, idx):
    central = get_central(cur, conn, "CRVBR", "CRV Brasil", "https://loja.crvbrasil.com.br")
    urls = json.load(open("/tmp/crv_dairy_prods.json"))
    client = httpx.Client(timeout=30, verify=False, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
    fonte = "CRV Loja Leiteiro 2026-06 (JSON-LD)"
    n_match = n_stub = n_skip = 0
    for u in urls:
        breed = breed_from_url(u)
        raca = RACA.get(breed)
        if not raca:
            n_skip += 1
            continue
        try:
            r = client.get(u)
            text = r.content.decode("iso-8859-1", "ignore")
            nome_com, price = jsonld_price(text)
        except Exception:
            nome_com, price = None, None
        if not price or price <= 0:
            n_skip += 1
            continue
        nome_com = nome_com or u.rstrip("/").split("/")[-1].replace("-", " ").title()
        slug = u.rstrip("/").split("/")[-1]
        ext_id = "CRVBR-" + slug
        nk = norm(nome_com)
        rid = idx.get((raca, nk))
        if rid:
            tipo = "fuzzy_nome"
            n_match += 1
        else:
            reg = ("CRV-SLUG-" + slug)[:50]
            rid = ensure_reprodutor(cur, raca, reg, nome_com)
            idx[(raca, nk)] = rid
            tipo = "url"
            n_stub += 1
        upsert_oferta(cur, rid, central, nome_com, price, u, ext_id, tipo, fonte)
        if (n_match + n_stub) % 40 == 0:
            conn.commit()
        time.sleep(0.05)
    conn.commit()
    print(f"  CRV leite: {n_match} casados a touro existente, {n_stub} stubs criados, {n_skip} sem preço/raça")
    return n_match + n_stub


def ingest_abs(cur, conn, idx):
    central = get_central(cur, conn, "ABS", "ABS Brasil", "http://touros.abspecplan.com.br")
    prods = json.load(open("/tmp/abs_leite.json"))
    fonte = "ABS Loja VTEX Leiteiro 2026-06"
    n_match = n_stub = n_skip = 0
    for p in prods:
        name = p.get("productName") or ""
        cats = [c for c in p.get("categories", []) if "/Sêmens/Leite/" in c]
        breed = breed_from_cats(cats, name)
        raca = RACA.get(breed)
        it = (p.get("items") or [{}])[0]
        sellers = it.get("sellers") or [{}]
        off = sellers[0].get("commertialOffer", {}) if sellers else {}
        price = off.get("Price")
        refid = None
        for r in (it.get("referenceId") or []):
            if r.get("Value"):
                refid = r["Value"]
        ext_id = "ABS-" + (refid or str(p.get("productId")))
        url = "https://loja.absglobal.com/" + (p.get("linkText") or "") + "/p"
        if not raca or not price or price <= 0:
            n_skip += 1
            continue
        nk = norm(name)
        rid = idx.get((raca, nk))
        if rid:
            tipo = "fuzzy_nome"
            n_match += 1
        else:
            reg = ("ABS-LEITE-" + str(p.get("productId")))[:50]
            rid = ensure_reprodutor(cur, raca, reg, name)
            idx[(raca, nk)] = rid
            tipo = "url"
            n_stub += 1
        upsert_oferta(cur, rid, central, name, float(price), url, ext_id, tipo, fonte)
    conn.commit()
    print(f"  ABS leite: {n_match} casados a touro existente, {n_stub} stubs criados, {n_skip} sem preço/raça")
    return n_match + n_stub


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    idx = load_breed_index(cur)
    print(f"  índice de touros leiteiros existentes: {len(idx)} chaves (raça+nome)")
    a = ingest_crv(cur, conn, idx)
    b = ingest_abs(cur, conn, idx)
    print(f"TOTAL ofertas leiteiras gravadas/atualizadas: {a + b}")
    conn.close()


if __name__ == "__main__":
    main()
