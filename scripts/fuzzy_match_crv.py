"""Liga preços comerciais (CRV) aos touros genéticos (Geneplus) por nome normalizado,
dentro da mesma raça. Cria oferta no touro Geneplus com o preço do CRV correspondente,
para que as raças novas tenham DEP **e** preço no matching/arbitragem.

Roda no container api.
"""
import os, re, unicodedata, psycopg2

DB = {
    "host": os.getenv("DB_HOST", "db"), "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}
FONTE = "CRV match fuzzy (nome)"
STOP = {"FIV", "TE", "IA", "DA", "DO", "DE", "DOS", "DAS", "MS", "FB", "JR",
        "II", "III", "IV", "RG", "RGD", "POI", "TM", "GUZERA", "NELORE",
        "SENEPOL", "BRANGUS", "BRAHMAN", "CANCHIM", "CARACU", "SINDI",
        "TABAPUA", "MONTANA", "LIMOUSIN", "GERTRUDIS", "SANTA", "LEITEIRO"}


def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    s = s.upper()
    toks = re.findall(r"[A-Z0-9]+", s)
    toks = [t for t in toks if t not in STOP and len(t) >= 2]
    return " ".join(toks)


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    crv_central = None
    cur.execute("SELECT id FROM catalogo.central WHERE nome='CRV Brasil'")
    r = cur.fetchone()
    crv_central = r[0] if r else None

    # touros genéticos (Geneplus) por raça
    cur.execute("""
        SELECT DISTINCT r.id, r.nome, r.raca_id
        FROM mercado.reprodutor r
        WHERE r.fonte_referencia LIKE 'Geneplus%%'
          AND EXISTS (SELECT 1 FROM mercado.avaliacao a WHERE a.reprodutor_id=r.id)
    """)
    gen = {}
    for rid, nome, raca in cur.fetchall():
        gen.setdefault((raca, norm(nome)), rid)

    # touros CRV com preço
    cur.execute("""
        SELECT r.id, r.nome, r.raca_id, o.preco_dose_brl
        FROM mercado.reprodutor r
        JOIN mercado.touro_oferta o ON o.reprodutor_id=r.id
        WHERE o.fonte_referencia LIKE 'CRV Brasil%%'
    """)
    crv = cur.fetchall()

    n_match = 0
    for rid_crv, nome, raca, preco in crv:
        key = (raca, norm(nome))
        if not key[1]:
            continue
        rid_gen = gen.get(key)
        if not rid_gen or rid_gen == rid_crv:
            continue
        # cria oferta no touro genético (idempotente: remove a anterior dessa fonte)
        cur.execute(
            "DELETE FROM mercado.touro_oferta WHERE reprodutor_id=%s AND fonte_referencia=%s",
            (rid_gen, FONTE),
        )
        cur.execute(
            """INSERT INTO mercado.touro_oferta
                 (reprodutor_id, central_id, nome_comercial, preco_dose_brl,
                  tipo_match, fuzzy_score, fonte_referencia, coletado_em)
               VALUES (%s,%s,%s,%s,'fuzzy_nome',1.0,%s, now())""",
            (rid_gen, crv_central, nome[:200], preco, FONTE),
        )
        n_match += 1
    conn.commit()
    print(f"genéticos {len(gen)} | CRV c/ preço {len(crv)} | matches criados {n_match}")
    conn.close()


if __name__ == "__main__":
    main()
