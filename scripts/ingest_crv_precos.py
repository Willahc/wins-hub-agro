"""Importa PREÇOS comerciais do catálogo CRV Brasil (loja Tray) via JSON-LD.

Cada reprodutor já importado do CRV tem fonte_url -> página do produto, que expõe
schema.org/Product com offers.price (preço da dose convencional). Cria ofertas em
mercado.touro_oferta atribuídas à central 'CRV Brasil'.

Roda no container api:  python ingest_crv_precos.py [all|<sigla>]
Idempotente: regrava a oferta CRV de cada reprodutor.
"""
import os
import re
import sys
import json
import time
import httpx
import psycopg2

DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}
FONTE = "CRV Brasil - Loja (JSON-LD)"


def get_central(conn):
    cur = conn.cursor()
    cur.execute("SELECT id FROM catalogo.central WHERE nome = 'CRV Brasil'")
    row = cur.fetchone()
    if row:
        return row[0]
    cur.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM catalogo.central")
    new_id = cur.fetchone()[0]
    cur.execute(
        "INSERT INTO catalogo.central (id, sigla, nome, site) VALUES (%s,'CRVBR','CRV Brasil','https://loja.crvbrasil.com.br')",
        (new_id,),
    )
    conn.commit()
    return new_id


def parse_price(htmltext):
    """Extrai (nome, preco) do JSON-LD schema.org/Product."""
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


def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "all").upper()
    conn = psycopg2.connect(**DB)
    central_id = get_central(conn)
    cur = conn.cursor()

    where = "r.fonte_url LIKE '%%loja.crvbrasil%%'"
    params = []
    if arg != "ALL":
        where += " AND ra.sigla = %s"
        params.append(arg)
    cur.execute(
        f"""SELECT r.id, r.nome, r.fonte_url, ra.sigla
            FROM mercado.reprodutor r JOIN catalogo.raca ra ON ra.id = r.raca_id
            WHERE {where}""",
        params,
    )
    alvos = cur.fetchall()
    print(f"  {len(alvos)} touros CRV para precificar (central_id={central_id})")

    client = httpx.Client(timeout=25, headers={"User-Agent": "Mozilla/5.0"}, follow_redirects=True)
    n_ok = n_skip = 0
    for rid, nome, url, sigla in alvos:
        try:
            r = client.get(url)
            text = r.content.decode("iso-8859-1", "ignore")
            nome_com, price = parse_price(text)
        except Exception:
            price = None
            nome_com = None
        if not price or price <= 0:
            n_skip += 1
            continue
        cur.execute(
            "DELETE FROM mercado.touro_oferta WHERE reprodutor_id=%s AND central_id=%s",
            (rid, central_id),
        )
        cur.execute(
            """INSERT INTO mercado.touro_oferta
               (reprodutor_id, central_id, nome_comercial, preco_dose_brl,
                url_oferta, tipo_match, fonte_referencia, coletado_em)
               VALUES (%s,%s,%s,%s,%s,'url',%s, now())""",
            (rid, central_id, (nome_com or nome)[:200], price, url[:500], FONTE),
        )
        n_ok += 1
        if n_ok % 50 == 0:
            conn.commit()
            print(f"    ... {n_ok} precificados")
        time.sleep(0.1)
    conn.commit()
    print(f"  OK: {n_ok} ofertas gravadas, {n_skip} sem preço")
    conn.close()


if __name__ == "__main__":
    main()
