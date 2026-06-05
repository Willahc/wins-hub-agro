"""Carrega os touros Wagyu (OCR do sumário ABCBRW) no banco. Roda no container api.
Lê /app/wagyu_bulls.json (gerado no host por wagyu_ocr.py).

Mapeamento de característica:
  marmoreio    -> MAR (18) E IQGg (20)*  (*para Wagyu, marmoreio é o índice de mérito)
  rendimento   -> 51 (cria)
  peso_carcaca -> 52 (cria)
  peso_vivo    -> 53 (cria)
"""
import os, json, psycopg2

DB = {
    "host": os.getenv("DB_HOST", "db"), "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}
RACA_WAGYU = 44
FONTE = "Sumário Wagyu ABCBRW 02/2025 (OCR)"

NOVAS = [
    (51, "WAG_REND", "Rendimento de Carcaça (Wagyu)", "carcaca"),
    (52, "WAG_PCAR", "Peso de Carcaça (Wagyu)", "carcaca"),
    (53, "WAG_PVIV", "Peso Vivo (Wagyu)", "crescimento"),
]
TRAIT_CARAC = {
    "marmoreio": [18, 20],   # MAR + IQGg (mérito Wagyu)
    "rendimento": [51],
    "peso_carcaca": [52],
    "peso_vivo": [53],
}


def main():
    bulls = json.load(open("/app/wagyu_bulls.json"))
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    for cid, sigla, nome, grupo in NOVAS:
        cur.execute(
            """INSERT INTO catalogo.caracteristica (id, sigla, nome, grupo, tipo, aplicavel_especies)
               VALUES (%s,%s,%s,%s,'DEP','BOV') ON CONFLICT (id) DO NOTHING""",
            (cid, sigla, nome, grupo),
        )
    conn.commit()

    n_rep = n_aval = 0
    todas_carac = sorted({c for lst in TRAIT_CARAC.values() for c in lst})
    for b in bulls:
        cur.execute(
            """INSERT INTO mercado.reprodutor
                 (registro, nome, especie_codigo, raca_id, data_nascimento, fonte_referencia, coletado_em)
               VALUES (%s,%s,'BOV',%s,%s,%s, now())
               ON CONFLICT (registro, raca_id) DO UPDATE SET
                 nome=EXCLUDED.nome, data_nascimento=EXCLUDED.data_nascimento,
                 fonte_referencia=EXCLUDED.fonte_referencia
               RETURNING id""",
            (b["registro"], b["nome"], RACA_WAGYU, b.get("dtn"), FONTE),
        )
        rid = cur.fetchone()[0]
        n_rep += 1
        cur.execute(
            "DELETE FROM mercado.avaliacao WHERE reprodutor_id=%s AND caracteristica_id = ANY(%s)",
            (rid, todas_carac),
        )
        for trait, info in b["traits"].items():
            for cid in TRAIT_CARAC.get(trait, []):
                cur.execute(
                    """INSERT INTO mercado.avaliacao
                         (reprodutor_id, caracteristica_id, valor, acuracia, coletado_em)
                       VALUES (%s,%s,%s,%s, now())""",
                    (rid, cid, info["depg"], info["acc"]),
                )
                n_aval += 1
    conn.commit()
    print(f"Wagyu: {n_rep} reprodutores, {n_aval} avaliações")
    conn.close()


if __name__ == "__main__":
    main()
