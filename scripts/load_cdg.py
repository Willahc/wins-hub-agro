"""Carrega touros Hereford/Braford do Sumário Conexão Delta G (PDF texto).
Achado via busca web (Serper) → site do programa → PDF limpo (bypass recaptcha GenSys).
Índice Final -> IDX_FINAL_CDG(54) E IQGg(20) (mérito; matching normaliza por raça).
"""
import os, json, psycopg2

DB = {
    "host": os.getenv("DB_HOST", "db"), "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}
RACA = {"HEREFORD": 10, "BRAFORD": 11}
FONTE = "Sumário Conexão Delta G (PDF)"
PROG = "conexao_deltag"
ALVO = [54, 20]  # IDX_FINAL_CDG e IQGg(mérito)


def main():
    bulls = json.load(open("/app/cdg_bulls.json"))
    conn = psycopg2.connect(**DB); cur = conn.cursor()
    n_rep = n_aval = 0
    for b in bulls:
        raca_id = RACA.get(b["raca"])
        if not raca_id:
            continue
        cur.execute(
            """INSERT INTO mercado.reprodutor
                 (registro, nome, especie_codigo, raca_id, fonte_referencia, fonte_programa, coletado_em)
               VALUES (%s,%s,'BOV',%s,%s,%s, now())
               ON CONFLICT (registro, raca_id) DO UPDATE SET
                 nome=EXCLUDED.nome, fonte_referencia=EXCLUDED.fonte_referencia,
                 fonte_programa=EXCLUDED.fonte_programa
               RETURNING id""",
            (b["registro"], b["nome"], raca_id, FONTE, PROG),
        )
        rid = cur.fetchone()[0]; n_rep += 1
        cur.execute("DELETE FROM mercado.avaliacao WHERE reprodutor_id=%s AND caracteristica_id = ANY(%s)",
                    (rid, ALVO))
        for cid in ALVO:
            cur.execute("""INSERT INTO mercado.avaliacao (reprodutor_id, caracteristica_id, valor, coletado_em)
                           VALUES (%s,%s,%s, now())""", (rid, cid, b["indice_final"]))
            n_aval += 1
    conn.commit()
    print(f"Conexão Delta G: {n_rep} reprodutores, {n_aval} avaliações")
    conn.close()


if __name__ == "__main__":
    main()
