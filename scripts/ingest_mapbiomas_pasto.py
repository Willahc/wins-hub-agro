#!/usr/bin/env python3
"""
ingest_mapbiomas_pasto.py — popula prospeccao.pasto_municipal (hoje 0 linhas) com
área de pastagem por município, MapBiomas. Alimenta Pasto Limpo (BASF), o pipeline
NDVI e o mapa de desertos (qualidade/área de pasto por território).

Dois caminhos:

  (A) ESTATÍSTICA MUNICIPAL (sem auth) — default.
      MapBiomas publica a planilha de cobertura/uso por município. Aponte a URL/arquivo
      via --xlsx (download manual em https://brasil.mapbiomas.org/estatisticas/) e o
      script agrega a classe Pastagem (id 15) por código IBGE e faz UPSERT.
      Sem credencial nenhuma.

  (B) GEE (--gee) — requer Earth Engine autenticado.
      Usa o asset público de pastagem da Coleção 9 e reduz por município.
      FALTA: `earthengine authenticate` + projeto GCP com Earth Engine API.
      (mesma pendência que travou o geomatch/NDVI.)

Roda no host:
    PGPASSWORD=... /root/.venv-wins-tools/bin/python scripts/ingest_mapbiomas_pasto.py \
        --xlsx /caminho/ESTATISTICAS_MAPBIOMAS_MUNICIPIO.xlsx
"""
import os, sys, argparse
import psycopg2
from psycopg2.extras import execute_values

PASTAGEM_CLASS_ID = 15  # classe "Pastagem" no esquema de legenda MapBiomas

def via_xlsx(path, ano):
    import pandas as pd
    # a planilha municipal traz colunas por classe/ano; layout varia entre coleções,
    # então selecionamos defensivamente as colunas de código IBGE e da classe pastagem.
    df = pd.read_excel(path)
    cols = {c.lower(): c for c in df.columns}
    cod = next((cols[k] for k in cols if "geocode" in k or "ibge" in k or "municipio_id" in k), None)
    if not cod:
        sys.exit(f"Não achei coluna de código IBGE na planilha. Colunas: {list(df.columns)[:12]}")
    # heurística: coluna cujo nome contenha 'pasture'/'pastagem' e o ano
    alvo = [cols[k] for k in cols if ("pasture" in k or "pastagem" in k) and str(ano) in k]
    if not alvo:
        alvo = [cols[k] for k in cols if "pasture" in k or "pastagem" in k]
    if not alvo:
        sys.exit("Não achei coluna de pastagem. Confirme o layout da planilha MapBiomas.")
    g = df.groupby(cod)[alvo[0]].sum().reset_index()
    g.columns = ["codigo_ibge", "pasto_ha"]
    g = g[g.pasto_ha > 0]
    return [(int(r.codigo_ibge), float(r.pasto_ha)) for r in g.itertuples(index=False)]

def via_gee(ano):
    try:
        import ee
    except ImportError:
        sys.exit("ERRO: pip install earthengine-api (no venv).")
    try:
        ee.Initialize()
    except Exception:
        sys.exit("ERRO: Earth Engine não autenticado. Rode `earthengine authenticate` "
                 "e configure um projeto GCP com a Earth Engine API. "
                 "(mesma pendência do geomatch/NDVI.)")
    sys.exit("GEE autenticado: implementar reduceRegions do asset de pastagem por "
             "malha municipal IBGE. Esqueleto deixado — preencher com o asset da Coleção.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", help="planilha municipal MapBiomas (caminho local)")
    ap.add_argument("--gee", action="store_true", help="usar Earth Engine (requer auth)")
    ap.add_argument("--ano", type=int, default=2023)
    args = ap.parse_args()

    if args.gee:
        rows = via_gee(args.ano)
    elif args.xlsx:
        rows = via_xlsx(args.xlsx, args.ano)
    else:
        sys.exit("Informe --xlsx <planilha MapBiomas> (sem auth) ou --gee (requer auth). "
                 "Download: https://brasil.mapbiomas.org/estatisticas/")

    pw = os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    cn = psycopg2.connect(host="127.0.0.1", port=5432, dbname="wins_agro",
                          user="postgres", password=pw)
    c = cn.cursor()
    execute_values(c, """
        INSERT INTO prospeccao.pasto_municipal (codigo_ibge, pasto_municipal_ha, fonte)
        SELECT v.codigo_ibge, v.ha, 'MapBiomas (agregado municipal)'
        FROM (VALUES %s) AS v(codigo_ibge, ha)
        ON CONFLICT (codigo_ibge) DO UPDATE SET pasto_municipal_ha = EXCLUDED.pasto_municipal_ha
    """, rows, template="(%s, %s)", page_size=1000)
    cn.commit()
    print(f"OK — {len(rows)} municípios gravados em prospeccao.pasto_municipal")
    cn.close()

if __name__ == "__main__":
    main()
