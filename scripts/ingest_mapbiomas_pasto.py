#!/usr/bin/env python3
"""
ingest_mapbiomas_pasto.py — popula prospeccao.pasto_municipal com área de pastagem
por município (MapBiomas). Alimenta Pasto Limpo (BASF), o pipeline NDVI e o mapa de
desertos (área de pasto por território).

Fonte: planilha pública de cobertura municipal do MapBiomas (Coleção 10.1), aba
COVERAGE_10.1 — área (ha) por município/classe/ano. Pastagem = class_id 15.
Download direto (sem auth). O município vem por NOME -> mapeado p/ código IBGE via
referencia.municipio (nome_normalizado + UF).

Roda no host (porta 5432 publicada):
    set -a && . ./.env && set +a
    PGPASSWORD="$POSTGRES_PASSWORD" /root/.venv-wins-tools/bin/python \
        scripts/ingest_mapbiomas_pasto.py [--ano 2023] [--xlsx <caminho>] [--gee]

Sem --xlsx, baixa o arquivo (Google Drive) para data/mapbiomas/.
Validação automática: total nacional deve cair em ~150-170 Mha.
"""
import os, sys, argparse, unicodedata, re
import psycopg2
from psycopg2.extras import execute_values

PASTAGEM_CLASS_ID = 15
GDRIVE_ID = "1p0dLrhvKymPhrSithsRBMRgHlFHq0FUf"  # MapBiomas Col.10.1 Biomas/Estados/Municípios
LOCAL_XLSX = "data/mapbiomas/coverage_municipality_col10.xlsx"

def normz(s):
    """upper + sem acento; apóstrofo/ponto removidos SEM espaço (D'AGUA->DAGUA, casa a
    referência), demais pontuações viram espaço."""
    if s is None: return None
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper()
    s = re.sub(r"['`´.]", "", s)            # apóstrofo/ponto: remove (não vira espaço)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    return " ".join(s.split()) or None

def baixar(dest):
    import urllib.request
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    url = f"https://drive.usercontent.google.com/download?id={GDRIVE_ID}&export=download&confirm=t"
    print(f"[dl] baixando MapBiomas coverage -> {dest} ...", flush=True)
    urllib.request.urlretrieve(url, dest)
    if os.path.getsize(dest) < 1_000_000:
        sys.exit("ERRO: download muito pequeno (provável interstitial do Drive). Baixe manual.")

def via_xlsx(path, ano, cn):
    import pandas as pd
    want = {"state_acronym", "municipality", "class_id", str(ano), ano}
    df = pd.read_excel(path, sheet_name="COVERAGE_10.1", usecols=lambda c: c in want)
    ycol = ano if ano in df.columns else str(ano)
    past = df[df.class_id == PASTAGEM_CLASS_ID].copy()
    past["mz"] = past.municipality.map(normz)
    g = past.groupby(["state_acronym", "mz"])[ycol].sum().reset_index()
    g = g[g[ycol] > 0]

    ref = pd.read_sql("SELECT codigo_ibge, nome_normalizado, uf FROM referencia.municipio", cn)
    ref["mz"] = ref.nome_normalizado.map(normz)
    por_uf = {(r.uf, r.mz): int(r.codigo_ibge) for r in ref.itertuples(index=False)}
    # fallback: nome único no país (recupera divergência de UF/grafia)
    nome_unico = ref.groupby("mz").codigo_ibge.nunique()
    por_nome = {r.mz: int(r.codigo_ibge) for r in ref.itertuples(index=False)
                if nome_unico.get(r.mz, 0) == 1}

    por_cod, orf = {}, []
    for uf, mz, ha in g[["state_acronym", "mz", ycol]].itertuples(index=False):
        cod = por_uf.get((uf, mz)) or por_nome.get(mz)
        if cod:                              # agrega: município partido entre bioma/UF soma
            por_cod[cod] = por_cod.get(cod, 0.0) + float(ha)
        else:
            orf.append((uf, mz))
    rows = [(c, round(h, 2)) for c, h in por_cod.items()]
    print(f"[map] {len(rows)} municípios IBGE casados de {len(g)} linhas-fonte "
          f"({100*(len(g)-len(orf))/len(g):.1f}%) | órfãos: {len(orf)}"
          + (f" ex.: {orf[:5]}" if orf else ""))
    return rows

def via_gee(ano, cn):
    try:
        import ee
    except ImportError:
        sys.exit("ERRO: pip install earthengine-api.")
    try:
        ee.Initialize()
    except Exception:
        sys.exit("ERRO: Earth Engine não autenticado (`earthengine authenticate` + projeto GCP). "
                 "Mesma pendência do geomatch/NDVI.")
    sys.exit("GEE autenticado: implementar reduceRegions do asset de pastagem por malha IBGE.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ano", type=int, default=2023)
    ap.add_argument("--xlsx", default=LOCAL_XLSX)
    ap.add_argument("--gee", action="store_true")
    args = ap.parse_args()

    pw = os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    cn = psycopg2.connect(host="127.0.0.1", port=5432, dbname="wins_agro",
                          user="postgres", password=pw)

    if args.gee:
        rows = via_gee(args.ano, cn)
    else:
        if not os.path.exists(args.xlsx):
            baixar(args.xlsx)
        rows = via_xlsx(args.xlsx, args.ano, cn)

    c = cn.cursor()
    execute_values(c, f"""
        INSERT INTO prospeccao.pasto_municipal (codigo_ibge, pasto_municipal_ha, fonte)
        SELECT v.cod, v.ha, 'MapBiomas Col.10.1 (pastagem {args.ano})'
        FROM (VALUES %s) v(cod, ha)
        ON CONFLICT (codigo_ibge) DO UPDATE
          SET pasto_municipal_ha = EXCLUDED.pasto_municipal_ha, fonte = EXCLUDED.fonte
    """, rows, template="(%s, %s)", page_size=1000)
    cn.commit()
    c.execute("SELECT count(*), round(sum(pasto_municipal_ha)/1e6, 1) FROM prospeccao.pasto_municipal")
    n, mha = c.fetchone()
    flag = "OK" if mha and 140 <= float(mha) <= 180 else "CONFERIR (fora de 140-180 Mha)"
    print(f"[ok] pasto_municipal: {n} municípios, {mha} Mha total -> sanity {flag}")
    cn.close()

if __name__ == "__main__":
    main()
