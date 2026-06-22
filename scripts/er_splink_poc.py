#!/usr/bin/env python3
"""
er_splink_poc.py — entity resolution sobre a base de empresas.

ACHADO DA PoC (jun/2026):
  - prospeccao.cnpj_rural já é deduplicado por CNPJ; só há ~81 grupos de
    razão+UF idênticos em 25.849 empresas, e vários "nomes parecidos" são
    entidades genuinamente distintas (SPEs numeradas etc.).
  - Splink (Fellegi-Sunter não-supervisionado) roda na nossa infra mas NÃO
    discrimina nessa tabela: sem massa de matches verdadeiros, o EM fica preso
    no prior. O ganho do Splink é em LINKAGEM CROSS-SOURCE (o problema real do
    Perfil 360: casar empresa <-> player de genética / cabanha / decisor por
    nome quando o CNPJ falta), não em deduplicar uma tabela já limpa.

Este script entrega 2 coisas:
  (A) DETERMINÍSTICO (default, roda): grupos mesmo-nome+UF com CNPJ distinto ->
      prospeccao.er_grupo_nome_uf. Candidatos a holding/mesmo dono; alimenta o
      vetor "ponto cego das holdings".
  (B) link_splink_cross_source(): esqueleto pronto p/ quando formos ligar
      cnpj_rural a outra fonte (genética/cabanha) — aí o EM tem sinal.

Read-only nas tabelas existentes. Roda no host (porta 5432 publicada):
    set -a && . ./.env && set +a
    PGPASSWORD="$POSTGRES_PASSWORD" /root/.venv-wins-tools/bin/python scripts/er_splink_poc.py
"""
import os, re, warnings
import psycopg2, pandas as pd
from psycopg2.extras import execute_values
warnings.filterwarnings("ignore")

SUFIXOS = r"\b(LTDA|EIRELI|S A|SA|ME|EPP|AGROPECUARIA|AGRO|FAZENDA|FAZ|SOCIEDADE|EMPRESARIA)\b"

def norm_nome(s):
    if not s: return None
    s = re.sub(r"[^A-Za-z0-9 ]", " ", str(s).upper())
    s = re.sub(SUFIXOS, " ", s)
    return re.sub(r"\s+", " ", s).strip() or None

def conn():
    pw = os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    return psycopg2.connect(host="127.0.0.1", port=5432, dbname="wins_agro",
                            user="postgres", password=pw)

def grupos_deterministicos(cn):
    df = pd.read_sql("SELECT cnpj,razao_social,uf,municipio FROM prospeccao.cnpj_rural "
                     "WHERE razao_social IS NOT NULL", cn)
    df["razao_norm"] = df.razao_social.map(norm_nome)
    df = df[df.razao_norm.notna()].copy()
    df["cnpj_basico"] = df.cnpj.str[:8]
    df["grp"] = df.razao_norm + "|" + df.uf.fillna("")
    g = df.groupby("grp").agg(ncnpj=("cnpj_basico", "nunique")).reset_index()
    multi = g[g.ncnpj > 1]
    out = df[df.grp.isin(multi.grp)].copy()
    out["cluster_id"] = out.grp.astype("category").cat.codes

    c = cn.cursor()
    c.execute("""DROP TABLE IF EXISTS prospeccao.er_grupo_nome_uf;
        CREATE TABLE prospeccao.er_grupo_nome_uf(
          cluster_id int, cnpj char(14), cnpj_basico char(8),
          razao_social text, razao_norm text, uf char(2), municipio text);""")
    execute_values(c, """INSERT INTO prospeccao.er_grupo_nome_uf
        (cluster_id,cnpj,cnpj_basico,razao_social,razao_norm,uf,municipio) VALUES %s""",
        list(out[["cluster_id","cnpj","cnpj_basico","razao_social",
                  "razao_norm","uf","municipio"]].itertuples(index=False, name=None)),
        page_size=1000)
    cn.commit()
    print(f"[det] {len(df)} empresas -> {len(multi)} grupos / {len(out)} empresas "
          f"(mesmo nome+UF, CNPJ distinto) gravados em prospeccao.er_grupo_nome_uf")

def link_splink_cross_source(df_esq, df_dir):
    """Esqueleto p/ linkar duas fontes por nome+UF+município (o caso onde Splink
    rende). Cada df precisa de: unique_id, razao_norm, uf, municipio.
    Bloqueia por UF+início-do-nome; treina u por amostragem e m por EM em blocos
    com matches verdadeiros (block_on razao_norm). Retorna o df de pares previstos.
    """
    from splink import DuckDBAPI, Linker, SettingsCreator, block_on
    import splink.comparison_library as cl
    settings = SettingsCreator(
        link_type="link_only",
        comparisons=[
            cl.JaroWinklerAtThresholds("razao_norm", [0.92, 0.85]),
            cl.ExactMatch("uf"),
            cl.JaroWinklerAtThresholds("municipio", [0.9]),
        ],
        blocking_rules_to_generate_predictions=[block_on("uf", "substr(razao_norm,1,4)")],
    )
    lk = Linker([df_esq, df_dir], settings, db_api=DuckDBAPI())
    lk.training.estimate_u_using_random_sampling(max_pairs=2_000_000)
    lk.training.estimate_parameters_using_expectation_maximisation(block_on("razao_norm"))
    lk.training.estimate_parameters_using_expectation_maximisation(block_on("municipio"))
    return lk.inference.predict(threshold_match_probability=0.9).as_pandas_dataframe()

if __name__ == "__main__":
    cn = conn()
    grupos_deterministicos(cn)
    cn.close()
