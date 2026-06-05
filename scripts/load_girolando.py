"""Carrega touros Girolando (PTA Leite) do Sumário Embrapa. Roda no container api.
Lê /app/giro_bulls.json (gerado no host por giro_parse.py, do PDF texto — sem OCR).

Mapeia PTAL (PTA Produção de Leite, kg) -> PTA_LEITE(32) E IQGg(20).
O IQGg(20) é usado pelo matching como índice de mérito; para leiteiras o mérito é o
PTA Leite. As escalas diferem entre raças, então o matching normaliza POR RAÇA.
Gordura/proteína NÃO entram (posição de coluna instável entre variantes de tabela).
"""
import os, json, psycopg2

DB = {
    "host": os.getenv("DB_HOST", "db"), "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}
RACA_GIRO = 38
FONTE = "Sumário Girolando Embrapa 06/2025 (PDF)"
ALVO = [32, 20]  # PTA_LEITE e IQGg(mérito)


def main():
    bulls = json.load(open("/app/giro_bulls.json"))
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    n_rep = n_aval = 0
    for b in bulls:
        cur.execute(
            """INSERT INTO mercado.reprodutor
                 (registro, nome, especie_codigo, raca_id, fonte_referencia, coletado_em)
               VALUES (%s,%s,'BOV',%s,%s, now())
               ON CONFLICT (registro, raca_id) DO UPDATE SET
                 nome=EXCLUDED.nome, fonte_referencia=EXCLUDED.fonte_referencia
               RETURNING id""",
            (b["registro"], b["nome"], RACA_GIRO, FONTE),
        )
        rid = cur.fetchone()[0]
        n_rep += 1
        cur.execute(
            "DELETE FROM mercado.avaliacao WHERE reprodutor_id=%s AND caracteristica_id = ANY(%s)",
            (rid, ALVO),
        )
        for cid in ALVO:
            cur.execute(
                """INSERT INTO mercado.avaliacao
                     (reprodutor_id, caracteristica_id, valor, acuracia, coletado_em)
                   VALUES (%s,%s,%s,%s, now())""",
                (rid, cid, b["ptal"], b.get("ptal_ac")),
            )
            n_aval += 1
    conn.commit()
    print(f"Girolando: {n_rep} reprodutores, {n_aval} avaliações")
    conn.close()


if __name__ == "__main__":
    main()
