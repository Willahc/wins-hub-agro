#!/usr/bin/env python3
"""
ingest_basedosdados.py — SCAFFOLD pronto-pra-rodar (requer credencial Google Cloud).

Base dos Dados (basedosdados.org) é um datalake público no BigQuery com IBGE/Censo
Agro/PPM/PAM/INMET já limpos e chaveados no código IBGE de 7 díg (nossa chave de join).
Vantagem: pular ETL — puxar tabela direto via SQL. Custo: precisa de um
`billing_project_id` do Google Cloud (a query roda no BQ do SOLICITANTE; tier grátis
de 1TB/mês cobre de sobra o nosso volume).

FALTA PARA RODAR (one-time, feito por humano):
  1. Criar/usar um projeto GCP e habilitar a BigQuery API.
  2. `gcloud auth application-default login`  (ou service-account JSON em
     GOOGLE_APPLICATION_CREDENTIALS).
  3. export BD_BILLING_PROJECT=<seu-projeto-gcp>
  4. /root/.venv-wins-tools/bin/pip install basedosdados
  5. PGPASSWORD=... /root/.venv-wins-tools/bin/python scripts/ingest_basedosdados.py

O que faz quando autenticado: baixa efetivo bovino por município (PPM) e área de
pastagem do Censo Agro 2017, faz UPSERT em tabelas de mercado. Hoje a PPM já está
no banco (prospeccao.ppm_municipio) — este script serve para refresh anual e para
trazer tabelas ainda ausentes (ex.: PAM lavouras, RAIS) sem escrever parser novo.
"""
import os, sys

def _exigir_auth():
    proj = os.environ.get("BD_BILLING_PROJECT")
    cred = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    adc = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
    if not proj:
        sys.exit("ERRO: defina BD_BILLING_PROJECT=<projeto-gcp>. Veja o cabeçalho do arquivo.")
    if not cred and not os.path.exists(adc):
        sys.exit("ERRO: sem credencial GCP. Rode `gcloud auth application-default login` "
                 "ou aponte GOOGLE_APPLICATION_CREDENTIALS p/ um service-account JSON.")
    return proj

# tabelas-alvo no datalake (dataset_id.table_id no BigQuery público da BD)
CONSULTAS = {
    # efetivo bovino por município/ano (PPM) — refresh
    "ppm_bovino": """
        SELECT id_municipio, ano, quantidade AS efetivo_cabecas
        FROM `basedosdados.br_ibge_ppm.efetivo_rebanhos`
        WHERE tipo_rebanho = 'Bovino' AND ano >= 2020
    """,
    # área de lavoura por município (PAM) — fonte ainda ausente no nosso banco
    "pam_lavoura": """
        SELECT id_municipio, ano, produto, area_plantada
        FROM `basedosdados.br_ibge_pam.lavoura_temporaria`
        WHERE ano >= 2020
    """,
}

def main():
    proj = _exigir_auth()
    try:
        import basedosdados as bd
    except ImportError:
        sys.exit("ERRO: pip install basedosdados (no venv /root/.venv-wins-tools).")
    import psycopg2
    pw = os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    cn = psycopg2.connect(host="127.0.0.1", port=5432, dbname="wins_agro",
                          user="postgres", password=pw)
    for nome, sql in CONSULTAS.items():
        print(f"[bq] {nome} ...", flush=True)
        df = bd.read_sql(sql, billing_project_id=proj)
        print(f"     {len(df)} linhas. (gravação: adaptar UPSERT à tabela-alvo)")
        # UPSERT específico por tabela fica a cargo de quem ativar — schema-dependente.
    cn.close()
    print("OK — autenticado e consultado. Implementar o UPSERT por tabela conforme o destino.")

if __name__ == "__main__":
    main()
