"""
Carregador de REBANHO REAL de um cliente (ex.: Monte Sião) — caminho 3.

Lê um CSV de matrizes/animais do produtor e:
  1. cria/atualiza o cliente em fazenda.cliente
  2. insere os animais em fazenda.animal (o lar próprio do rebanho do cliente)
  3. ESPELHA as fêmeas em mercado.reprodutor (sexo='F', fonte_programa='fazenda_<id>')
     pra elas aparecerem no Acasalamento. Se o CSV trouxer índices genômicos
     próprios da vaca (iqgg/gpd/aol/pes/mar), grava como avaliação da vaca →
     o cruzamento usa o mérito REAL dela (não o proxy da progênie).

DRY-RUN por padrão (faz tudo numa transação e dá ROLLBACK, mostrando o que faria).
Para gravar de verdade, passar --commit.

Uso (no container api):
  docker cp scripts/load_rebanho_cliente.py wins_agro_v1_api_1:/app/
  docker cp /caminho/rebanho.csv wins_agro_v1_api_1:/app/
  docker exec -w /app wins_agro_v1_api_1 python load_rebanho_cliente.py \
      --cliente "Fazenda Monte Sião" --uf TO --municipio "Porto Nacional" \
      --csv rebanho.csv [--commit]

Colunas do CSV (cabeçalho; só 'nome' e 'sexo' são obrigatórios):
  brinco, sisbov, registro, nome, raca, sexo, data_nascimento, categoria,
  composicao_racial, peso_kg, escore_corporal, pai_registro, pai_nome,
  mae_registro, mae_nome, iqgg, gpd, aol, pes, mar, obs
"""
import os
import csv
import sys
import argparse
import psycopg2

DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

# coluna do CSV de índice -> caracteristica_id
GENOMICO = {"iqgg": 20, "gpd": 8, "aol": 16, "pes": 12, "mar": 18}


def _s(v):
    v = (v or "").strip()
    return v or None


def _num(v):
    v = _s(v)
    if v is None:
        return None
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cliente", required=True)
    ap.add_argument("--csv", required=True)
    ap.add_argument("--uf")
    ap.add_argument("--municipio")
    ap.add_argument("--cnpj")
    ap.add_argument("--commit", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()

    # mapa sigla -> raca_id
    cur.execute("SELECT UPPER(sigla), id FROM catalogo.raca")
    RACA = {s: i for s, i in cur.fetchall()}

    # 1) cliente (upsert por razao_social)
    cur.execute("SELECT id FROM fazenda.cliente WHERE razao_social = %s", (args.cliente,))
    row = cur.fetchone()
    if row:
        cliente_id = row[0]
    else:
        cur.execute(
            """INSERT INTO fazenda.cliente (razao_social, uf, municipio, cnpj, criado_em)
               VALUES (%s, %s, %s, %s, now()) RETURNING id""",
            (args.cliente, args.uf, args.municipio, args.cnpj),
        )
        cliente_id = cur.fetchone()[0]
    fonte_prog = f"fazenda_{cliente_id}"
    fonte_ref = f"Rebanho {args.cliente}"

    n_animais = n_femeas = n_mirror = n_aval = 0
    with open(args.csv, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            nome = _s(r.get("nome"))
            sexo = (_s(r.get("sexo")) or "").upper()[:1]
            if not nome or sexo not in ("M", "F"):
                continue
            raca_id = RACA.get((_s(r.get("raca")) or "").upper())
            brinco = _s(r.get("brinco"))
            reg = _s(r.get("registro"))
            pai_r, pai_n = _s(r.get("pai_registro")), _s(r.get("pai_nome"))
            mae_r, mae_n = _s(r.get("mae_registro")), _s(r.get("mae_nome"))

            # 2) fazenda.animal
            cur.execute(
                """INSERT INTO fazenda.animal
                   (cliente_id, brinco, sisbov, registro_associacao, nome, especie_codigo,
                    raca_id, composicao_racial, sexo, data_nascimento, pai_registro_externo,
                    pai_nome_externo, mae_registro_externo, categoria, status, peso_atual_kg,
                    escore_corporal, obs, coletado_em)
                   VALUES (%s,%s,%s,%s,%s,'BOV',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())""",
                (cliente_id, brinco, _s(r.get("sisbov")), reg, nome, raca_id,
                 _s(r.get("composicao_racial")), sexo, _s(r.get("data_nascimento")),
                 pai_r, pai_n, mae_r, _s(r.get("categoria")), _s(r.get("status")) or "ativo",
                 _num(r.get("peso_kg")), _num(r.get("escore_corporal")), _s(r.get("obs"))),
            )
            n_animais += 1
            if sexo != "F" or raca_id is None:
                continue
            n_femeas += 1

            # 3) espelha a fêmea em mercado.reprodutor (pra entrar no acasalamento)
            registro_m = reg or (f"FZ{cliente_id}-{brinco}" if brinco else None)
            if not registro_m:
                continue
            cur.execute(
                """INSERT INTO mercado.reprodutor
                   (registro, nome, especie_codigo, raca_id, sexo, pai_registro, pai_nome,
                    mae_registro, mae_nome, fazenda_origem, uf, municipio,
                    fonte_referencia, fonte_programa, coletado_em)
                   VALUES (%s,%s,'BOV',%s,'F',%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
                   ON CONFLICT (registro, raca_id) DO UPDATE SET
                     nome=EXCLUDED.nome, pai_registro=EXCLUDED.pai_registro,
                     pai_nome=EXCLUDED.pai_nome, mae_registro=EXCLUDED.mae_registro,
                     mae_nome=EXCLUDED.mae_nome, fazenda_origem=EXCLUDED.fazenda_origem,
                     uf=EXCLUDED.uf, municipio=EXCLUDED.municipio,
                     fonte_programa=EXCLUDED.fonte_programa
                   RETURNING id""",
                (registro_m, nome, raca_id, pai_r, pai_n, mae_r, mae_n,
                 args.cliente, args.uf, args.municipio, fonte_ref, fonte_prog),
            )
            rid = cur.fetchone()[0]
            n_mirror += 1

            # índices genômicos próprios da vaca -> avaliacao (regrava)
            idx = {c: _num(r.get(c)) for c in GENOMICO if _num(r.get(c)) is not None}
            if idx:
                cur.execute(
                    "DELETE FROM mercado.avaliacao WHERE reprodutor_id=%s AND caracteristica_id = ANY(%s)",
                    (rid, [GENOMICO[c] for c in idx]),
                )
                for c, val in idx.items():
                    cur.execute(
                        """INSERT INTO mercado.avaliacao
                           (reprodutor_id, caracteristica_id, valor, eh_genomica, coletado_em)
                           VALUES (%s,%s,%s,true, now())""",
                        (rid, GENOMICO[c], val),
                    )
                    n_aval += 1

    print(f"cliente_id={cliente_id} ({args.cliente})")
    print(f"  fazenda.animal: {n_animais} animais ({n_femeas} fêmeas)")
    print(f"  mercado.reprodutor: {n_mirror} matrizes espelhadas")
    print(f"  mercado.avaliacao: {n_aval} índices genômicos próprios gravados")
    if args.commit:
        conn.commit()
        print("COMMIT — dados gravados.")
    else:
        conn.rollback()
        print("DRY-RUN — rollback (use --commit pra gravar).")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
