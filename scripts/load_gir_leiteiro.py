"""Carrega touros Gir Leiteiro (PTA Leite) do 2º Sumário Genômico Embrapa.
PDF texto-extraível (sem OCR). Roda no container api. Lê /app/girleit_bulls.json.
PTAL -> PTA_LEITE(32) E IQGg(20) (mérito; matching normaliza por raça).
"""
import os, json, psycopg2

DB = {
    "host": os.getenv("DB_HOST", "db"), "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}
RACA = 22  # Gir Leiteiro (GIRL)
FONTE = "2º Sumário Genômico Gir Leiteiro Embrapa (PDF)"
PROG = "embrapa_gir_leiteiro"
ALVO = [32, 20]  # PTA_LEITE e IQGg(mérito)


def main():
    bulls = json.load(open("/app/girleit_bulls.json"))
    conn = psycopg2.connect(**DB); cur = conn.cursor()
    n_rep = n_aval = 0
    for b in bulls:
        cur.execute(
            """INSERT INTO mercado.reprodutor
                 (registro, nome, especie_codigo, raca_id, fonte_referencia, fonte_programa, coletado_em)
               VALUES (%s,%s,'BOV',%s,%s,%s, now())
               ON CONFLICT (registro, raca_id) DO UPDATE SET
                 nome=EXCLUDED.nome, fonte_referencia=EXCLUDED.fonte_referencia,
                 fonte_programa=EXCLUDED.fonte_programa
               RETURNING id""",
            (b["registro"], b["nome"], RACA, FONTE, PROG),
        )
        rid = cur.fetchone()[0]; n_rep += 1
        cur.execute("DELETE FROM mercado.avaliacao WHERE reprodutor_id=%s AND caracteristica_id = ANY(%s)",
                    (rid, ALVO))
        for cid in ALVO:
            cur.execute("""INSERT INTO mercado.avaliacao
                             (reprodutor_id, caracteristica_id, valor, acuracia, coletado_em)
                           VALUES (%s,%s,%s,%s, now())""",
                        (rid, cid, b["ptal"], b.get("ptal_ac")))
            n_aval += 1
    conn.commit()
    print(f"Gir Leiteiro: {n_rep} reprodutores, {n_aval} avaliações")
    conn.close()


if __name__ == "__main__":
    main()
