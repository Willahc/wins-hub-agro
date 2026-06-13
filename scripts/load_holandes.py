"""Carrega touros da raça Holandesa do Sumário Nacional de Touros 2013 (Embrapa/ABCBRH).

Fonte: Embrapa Gado de Leite, Documentos 167 (PDF texto-extraível, sem OCR):
  https://www.infoteca.cnptia.embrapa.br/infoteca/bitstream/doc/1064552/1/DOC167SumarioTourosHolandescompleto.pdf

Tabelas 3/4: ranking por PTA Leite (PTAL). Cada linha:
  <NOME>  AX######  PTAL  CGi  Conf  NF  NR  PTAG ... PTAP ... Ano  Origem

Mapeia:
  PTAL -> PTA_LEITE(32) E IQGg(20)  (o matching usa IQGg como mérito; p/ leite o mérito é PTA Leite,
                                     normalizado por raça)
  PTAG -> PTA_GORDURA(33), PTAP -> PTA_PROTEINA(34) quando disponíveis.

Uso: rodar no container api:  python load_holandes.py
Idempotente: ON CONFLICT (registro, raca_id) DO NOTHING/UPDATE.
"""
import os
import re
import psycopg2

DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}
RACA = 21  # Holandês
FONTE = "Sumário Nacional Touros Holandês 2013 Embrapa/ABCBRH (PDF)"
PROG = "sumario_holandes"
TXT = "/tmp/holandes.txt"

# linha de dados: NOME  AX######  PTAL CGi Conf NF NR  PTAG CGi Conf NF NR  PTAP ...  Ano Origem
ROW = re.compile(
    r"^(?P<nome>.+?)\s+(?P<reg>AX\d{6})\s+"
    r"(?P<ptal>-?\d+\.\d+)\s+\d+\s+\d+\s+\d+\s+\d+\s+"          # PTAL CGi Conf NF NR
    r"(?P<ptag>-?\d+\.\d+|\.)\s+\S+\s+\S+\s+\S+\s+\S+\s+"        # PTAG CGi Conf NF NR
    r"(?P<ptap>-?\d+\.\d+|\.)"                                  # PTAP
)


def parse():
    bulls = {}
    for line in open(TXT, encoding="utf-8"):
        m = ROW.match(line.strip())
        if not m:
            continue
        reg = m.group("reg")
        nome = re.sub(r"\s+", " ", m.group("nome")).strip()
        ptag = m.group("ptag")
        ptap = m.group("ptap")
        bulls[reg] = {  # dedup por registro (Tabela 4 repete nacionais da Tabela 3)
            "registro": reg,
            "nome": nome,
            "ptal": float(m.group("ptal")),
            "ptag": float(ptag) if ptag != "." else None,
            "ptap": float(ptap) if ptap != "." else None,
        }
    return list(bulls.values())


def main():
    bulls = parse()
    print(f"  {len(bulls)} touros Holandês parseados do PDF")
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    n_rep = n_aval = n_new = 0
    for b in bulls:
        cur.execute(
            """INSERT INTO mercado.reprodutor
                 (registro, nome, especie_codigo, raca_id, sexo,
                  fonte_referencia, fonte_programa, coletado_em)
               VALUES (%s,%s,'BOV',%s,'M',%s,%s, now())
               ON CONFLICT (registro, raca_id) DO UPDATE SET
                 nome=EXCLUDED.nome, sexo='M',
                 fonte_referencia=EXCLUDED.fonte_referencia,
                 fonte_programa=EXCLUDED.fonte_programa
               RETURNING (xmax = 0) AS inserted, id""",
            (b["registro"], b["nome"], RACA, FONTE, PROG),
        )
        inserted, rid = cur.fetchone()
        n_rep += 1
        if inserted:
            n_new += 1
        # avaliacoes: PTAL -> 32 e 20; PTAG -> 33; PTAP -> 34
        pares = [(32, b["ptal"]), (20, b["ptal"])]
        if b["ptag"] is not None:
            pares.append((33, b["ptag"]))
        if b["ptap"] is not None:
            pares.append((34, b["ptap"]))
        cids = [c for c, _ in pares]
        cur.execute(
            "DELETE FROM mercado.avaliacao WHERE reprodutor_id=%s AND caracteristica_id = ANY(%s)",
            (rid, cids),
        )
        for cid, val in pares:
            cur.execute(
                """INSERT INTO mercado.avaliacao
                     (reprodutor_id, caracteristica_id, valor, coletado_em)
                   VALUES (%s,%s,%s, now())""",
                (rid, cid, val),
            )
            n_aval += 1
    conn.commit()
    print(f"Holandês: {n_rep} reprodutores ({n_new} novos), {n_aval} avaliações")
    conn.close()


if __name__ == "__main__":
    main()
