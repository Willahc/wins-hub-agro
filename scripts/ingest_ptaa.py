"""Ingestão da Pesquisa Trimestral do Abate de Animais (PTAA / IBGE) -> prospeccao.ptaa_abate_uf.

Fonte: IBGE SIDRA, agregado 1092 ("...bovinos abatidos, no mês e no trimestre,
por tipo de rebanho e tipo de inspeção"). API v3 de agregados.
  variável 284 = "Animais abatidos" (Cabeças)
  classificação 18 = "Tipo de rebanho bovino"
      categorias: 55=Bois, 56=Vacas, 111734=Novilhos, 111735=Novilhas, 57=Vitelos e vitelas
  (Total/992 e demais classificações — inspeção 12529, referência temporal 12716 — ficam
   no agregado "Total" automaticamente quando não especificadas: 118225 e 115236.)
Níveis territoriais: só N1 (Brasil) e N3 (UF) — a PTAA NÃO tem município. Gravamos em nível UF.

Business: abate de VACAS por UF sinaliza liquidação de matrizes (oportunidade de reposição
genética). Puxamos os últimos ~12 trimestres por UF e categoria.

Roda DENTRO do container api (tem httpx + psycopg2 + acesso ao db).
Uso:  docker exec -i wins_agro_v1-api-1 python3 - < scripts/ingest_ptaa.py
Idempotente: upsert por (codigo_uf, periodo, categoria).
"""
import os
import sys
import time
import httpx
import psycopg2
import psycopg2.extras

AGREGADO = "1092"
VARIAVEL = "284"            # Animais abatidos (Cabeças)
CLS = "18"                 # Tipo de rebanho bovino
N_PERIODOS = 12            # últimos ~12 trimestres
ESPECIE = "Bovino"

# categoria_id SIDRA -> nome canônico (excluímos 992=Total; queremos só as quebras)
CATEGORIAS = {
    "55": "Boi",
    "56": "Vaca",
    "111734": "Novilho",
    "111735": "Novilha",
    "57": "Vitelo/Bezerro",
}

BASE = "https://servicodados.ibge.gov.br/api/v3/agregados"

DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

DDL = """
CREATE SCHEMA IF NOT EXISTS prospeccao;
CREATE TABLE IF NOT EXISTS prospeccao.ptaa_abate_uf (
    uf         char(2),
    codigo_uf  int       NOT NULL,
    periodo    text      NOT NULL,   -- ex 202504 (ano + trimestre)
    ano        int       NOT NULL,
    trimestre  int       NOT NULL,
    categoria  text      NOT NULL,   -- Boi / Vaca / Novilho / Novilha / Vitelo/Bezerro
    especie    text,
    cabecas    bigint,
    fonte      text      DEFAULT 'IBGE/PTAA SIDRA 1092 var284',
    updated_at timestamptz DEFAULT now(),
    UNIQUE (codigo_uf, periodo, categoria)
);
"""


def fetch(client, cat_ids):
    """Puxa todas as UFs (N3) para as categorias dadas, últimos N_PERIODOS trimestres."""
    cats = ",".join(cat_ids)
    url = (f"{BASE}/{AGREGADO}/periodos/-{N_PERIODOS}/variaveis/{VARIAVEL}"
           f"?localidades=N3[all]&classificacao={CLS}[{cats}]")
    r = client.get(url, timeout=120)
    r.raise_for_status()
    return r.json()


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute(DDL)
    conn.commit()

    # de-para codigo_uf (2 dígitos) -> sigla UF, a partir da base de referência
    cur.execute("SELECT DISTINCT codigo_uf, uf FROM referencia.municipio WHERE codigo_uf IS NOT NULL")
    cod2uf = {str(c): u for c, u in cur.fetchall()}
    print(f"de-para codigo_uf->sigla: {len(cod2uf)} UFs", flush=True)

    linhas = []
    with httpx.Client(headers={"Accept": "application/json"}) as client:
        data = fetch(client, list(CATEGORIAS.keys()))
        for var in data:
            for bloco in var.get("resultados", []):
                # identifica a categoria deste bloco pela classificação 18
                cat_nome = None
                for c in bloco.get("classificacoes", []):
                    if c.get("id") == CLS:
                        cat_id = next(iter(c["categoria"].keys()))
                        cat_nome = CATEGORIAS.get(cat_id)
                if not cat_nome:
                    continue
                for serie in bloco.get("series", []):
                    loc = serie["localidade"]
                    codigo_uf = loc["id"]          # 2 dígitos
                    uf = cod2uf.get(codigo_uf)
                    for periodo, valor in serie["serie"].items():
                        if valor in (None, "...", "-", "X", ".."):
                            continue
                        try:
                            cabecas = int(float(valor))
                        except (TypeError, ValueError):
                            continue
                        ano = int(periodo[:4])
                        trimestre = int(periodo[4:])
                        linhas.append((uf, int(codigo_uf), periodo, ano, trimestre,
                                       cat_nome, ESPECIE, cabecas))
    print(f"linhas coletadas: {len(linhas)}", flush=True)
    if not linhas:
        print("ERRO: nenhuma linha — abortando.", flush=True)
        sys.exit(1)

    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO prospeccao.ptaa_abate_uf
            (uf, codigo_uf, periodo, ano, trimestre, categoria, especie, cabecas)
        VALUES %s
        ON CONFLICT (codigo_uf, periodo, categoria) DO UPDATE SET
            uf         = EXCLUDED.uf,
            ano        = EXCLUDED.ano,
            trimestre  = EXCLUDED.trimestre,
            especie    = EXCLUDED.especie,
            cabecas    = EXCLUDED.cabecas,
            updated_at = now()
        """,
        linhas,
        page_size=2000,
    )
    conn.commit()

    cur.execute("SELECT count(*), count(DISTINCT periodo), count(DISTINCT codigo_uf) "
                "FROM prospeccao.ptaa_abate_uf")
    tot, nper, nuf = cur.fetchone()
    print(f"OK | tabela: {tot} linhas, {nper} trimestres, {nuf} UFs", flush=True)
    cur.execute("SELECT min(periodo), max(periodo) FROM prospeccao.ptaa_abate_uf")
    print("  trimestres cobertos: {} .. {}".format(*cur.fetchone()), flush=True)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
