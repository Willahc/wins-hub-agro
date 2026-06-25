#!/usr/bin/env python3
"""
ingest_pam_lavoura.py — persiste a PAM (Produção Agrícola Municipal, lavoura
temporária) do BigQuery/Base dos Dados em mercado.pam_lavoura. Dado NOVO grátis
(tier 1TB/mês), complementa o pasto/pecuária com área de LAVOURA por município
— alimenta o Radar ILP (pecuária→agricultura) no nível território.

Fonte: basedosdados.br_ibge_pam.lavoura_temporaria (id_municipio, ano, produto,
area_plantada). ~918k linhas. Cria a tabela + bulk insert (idempotente: TRUNCATE).

Uso: set -a && . ./.env && . ./scripts/.env.gcp && set +a
     /root/.venv-wins-tools/bin/python scripts/ingest_pam_lavoura.py
"""
import os, sys
import psycopg2
from psycopg2.extras import execute_values

def main():
    proj = os.environ.get("BD_BILLING_PROJECT")
    if not proj:
        sys.exit("ERRO: BD_BILLING_PROJECT ausente (source scripts/.env.gcp).")
    import basedosdados as bd
    print("[bq] baixando PAM lavoura_temporaria (ano>=2018)...", flush=True)
    df = bd.read_sql(
        """SELECT id_municipio, ano, produto, area_plantada
           FROM `basedosdados.br_ibge_pam.lavoura_temporaria`
           WHERE ano >= 2018 AND area_plantada IS NOT NULL""",
        billing_project_id=proj)
    print(f"[bq] {len(df):,} linhas baixadas.", flush=True)

    pw = os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    cn = psycopg2.connect(host="127.0.0.1", port=5432, dbname="wins_agro", user="postgres", password=pw)
    cur = cn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mercado.pam_lavoura (
            codigo_ibge   integer NOT NULL,
            ano           integer NOT NULL,
            produto       text NOT NULL,
            area_plantada numeric,
            PRIMARY KEY (codigo_ibge, ano, produto)
        )""")
    cur.execute("TRUNCATE mercado.pam_lavoura")
    rows = [(int(r.id_municipio), int(r.ano), str(r.produto),
             float(r.area_plantada) if r.area_plantada is not None else None)
            for r in df.itertuples(index=False)]
    execute_values(cur,
        "INSERT INTO mercado.pam_lavoura (codigo_ibge,ano,produto,area_plantada) VALUES %s "
        "ON CONFLICT (codigo_ibge,ano,produto) DO UPDATE SET area_plantada=EXCLUDED.area_plantada",
        rows, page_size=5000)
    cn.commit()
    cur.execute("SELECT count(*), count(DISTINCT codigo_ibge), max(ano) FROM mercado.pam_lavoura")
    n, muns, ymax = cur.fetchone()
    print(f"[ok] mercado.pam_lavoura: {n:,} linhas, {muns} municípios, ano máx {ymax}", flush=True)
    cn.close()

if __name__ == "__main__":
    main()
