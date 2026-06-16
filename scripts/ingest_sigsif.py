"""Ingestão SIGSIF/MAPA — abates por categoria/UF + estabelecimentos SIF (frigoríficos).

Fonte: Portal de Dados Abertos do MAPA (CKAN), dataset "Serviço de Inspeção
Federal (SIF)" / PGA-SIGSIF. URLs dos CSV descobertas via API CKAN
package_search (q=sif) — pkg "servico-de-inspecao-federal-sif". Todos os CSV são
Latin-1 (ISO-8859-1), separador ';'. A API exige User-Agent de browser (sem ele
o endpoint devolve 403 sem corpo).

Duas camadas de negócio:
  (a) prospeccao.sigsif_abate_categoria_uf  — abate por CATEGORIA × UF × município
      × ano/mês. A coluna CATEGORIA do CSV mistura espécie e categoria fina: além
      de "Bovino" existem "Touro/Touruno", "Vaca", "Novilho", "Vitelo" etc.
      *** "Touro/Touruno" é o proxy de descarte de reprodutor = troca de genética;
      é a linha que alimenta 20% do score de município/UF. *** A espécie é
      derivada (deriva_especie) p/ filtrar bovinos sem depender de string exata.
  (b) prospeccao.sigsif_estabelecimento — frigoríficos/estabelecimentos SIF ativos
      por município/UF (mapa de compradores de gado gordo). O CSV repete cada
      NR_SIF por habilitação-de-exportação; deduplicamos ao grão físico
      (nr_sif, area_categoria, categoria_classe).

Roda DENTRO do container api (httpx + pandas + psycopg2 + acesso ao db host="db").
Uso (via stdin pipe, scripts/ não está montado no container):
    docker exec -i wins_agro_v1-api-1 python3 - < scripts/ingest_sigsif.py
Idempotente: CREATE TABLE IF NOT EXISTS + UNIQUE + upsert ON CONFLICT.
Crosswalk IBGE: join município por nome_normalizado + UF contra referencia.municipio.
"""
import os
import io
import sys
import unicodedata
import httpx
import pandas as pd
import psycopg2
import psycopg2.extras

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124 Safari/537.36"}
BASE = ("https://dados.agricultura.gov.br/dataset/"
        "062166e3-b515-4274-8e7d-68aadd64b820/resource")
URLS = {
    "categoria_uf": f"{BASE}/239eaa90-35cd-4b67-8902-d34eda3dca53/download/"
                    "sigsifquantitativoanimaisabatidoscategoriauf.csv",
    "estab": f"{BASE}/97277e92-264a-4dc0-9aea-f87b8ea93798/download/"
             "sigsifestabelecimentosregistradosnosif.csv",
}
DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}
FONTE = "SIGSIF/MAPA (CKAN dados.agricultura.gov.br)"

DDL = """
CREATE SCHEMA IF NOT EXISTS prospeccao;

CREATE TABLE IF NOT EXISTS prospeccao.sigsif_abate_categoria_uf (
    id            bigserial PRIMARY KEY,
    ano           integer NOT NULL,
    mes           integer NOT NULL,
    uf            char(2),
    municipio_nome text,
    codigo_ibge   integer,
    categoria     text NOT NULL,   -- valor cru (ex: 'Touro/Touruno','Vaca','Bovino')
    especie       text,            -- derivada (Bovino/Bubalino/Suino/Ave/...)
    quantidade    bigint,
    fonte         text DEFAULT 'SIGSIF/MAPA (CKAN dados.agricultura.gov.br)',
    updated_at    timestamptz DEFAULT now(),
    UNIQUE (ano, mes, uf, municipio_nome, categoria)
);
CREATE INDEX IF NOT EXISTS ix_sigsif_abate_ibge ON prospeccao.sigsif_abate_categoria_uf (codigo_ibge);
CREATE INDEX IF NOT EXISTS ix_sigsif_abate_cat_uf ON prospeccao.sigsif_abate_categoria_uf (categoria, uf);

CREATE TABLE IF NOT EXISTS prospeccao.sigsif_estabelecimento (
    id               bigserial PRIMARY KEY,
    cpf_cnpj         text,
    razao_social     text,
    nome_fantasia    text,
    nr_sif           text NOT NULL,
    situacao         text,
    municipio        text,
    uf               char(2),
    codigo_ibge      integer,
    area_categoria   text NOT NULL,
    categoria_classe text NOT NULL,
    telefone         text,
    email            text,
    fonte            text DEFAULT 'SIGSIF/MAPA (CKAN dados.agricultura.gov.br)',
    updated_at       timestamptz DEFAULT now(),
    UNIQUE (nr_sif, area_categoria, categoria_classe)
);
CREATE INDEX IF NOT EXISTS ix_sigsif_estab_ibge ON prospeccao.sigsif_estabelecimento (codigo_ibge);
CREATE INDEX IF NOT EXISTS ix_sigsif_estab_uf ON prospeccao.sigsif_estabelecimento (uf, area_categoria);
"""


def norm(s):
    if s is None:
        return None
    s = str(s).strip()
    if not s or s.lower() == "nan":
        return None
    s = "".join(c for c in unicodedata.normalize("NFKD", s)
                if not unicodedata.combining(c))
    return s.upper().strip()


def deriva_especie(cat):
    """Mapeia a CATEGORIA crua p/ uma espécie macro, p/ filtrar bovinos."""
    c = (cat or "").lower()
    bov = ("bovino", "touro", "touruno", "vaca", "novilh", "vitelo",
           "boi", "garrote", "bezerr")
    if any(t in c for t in bov):
        return "Bovino"
    if "bubalin" in c or "bufal" in c or "bufala" in c:
        return "Bubalino"
    if "suino" in c or "leita" in c or "porco" in c or "porca" in c or "javali" in c:
        return "Suino"
    if any(t in c for t in ("ovino", "ovelha", "cordeir", "carneiro")):
        return "Ovino"
    if any(t in c for t in ("caprino", "cabrit", "bode")):
        return "Caprino"
    if any(t in c for t in ("equino", "muar", "asinino", "cavalo", "egua")):
        return "Equino"
    if any(t in c for t in ("frango", "galinha", "galo", "peru", "aves", "galeto",
                            "codorna", "pato", "ganso", "marreco", "avestruz")):
        return "Ave"
    return "Outros"


def fetch_csv(url):
    with httpx.Client(timeout=300, verify=False, follow_redirects=True, headers=UA) as c:
        raw = c.get(url).content
    return pd.read_csv(io.BytesIO(raw), sep=";", encoding="latin-1",
                       on_bad_lines="skip", dtype=str)


def carrega_crosswalk(cur):
    """{(nome_normalizado, uf): codigo_ibge}"""
    cur.execute("SELECT nome_normalizado, uf, codigo_ibge FROM referencia.municipio")
    xw = {}
    for nome, uf, ibge in cur.fetchall():
        if nome and uf:
            xw[(nome, uf)] = ibge
    return xw


def ingest_abate(conn, xw):
    df = fetch_csv(URLS["categoria_uf"])
    df = df.rename(columns=str.strip)
    n_raw = len(df)
    print(f"[abate] CSV bruto: {n_raw} linhas, cols={list(df.columns)}")
    # --- limpeza vetorizada (2,5M linhas: nada de itertuples) ---
    df["ANO"] = pd.to_numeric(df["ANO"], errors="coerce")
    df["MES"] = pd.to_numeric(df["MES"], errors="coerce")
    df["QUANTIDADE"] = pd.to_numeric(df["QUANTIDADE"], errors="coerce")
    df = df.dropna(subset=["ANO", "MES", "CATEGORIA"])
    df["ANO"] = df["ANO"].astype("int32")
    df["MES"] = df["MES"].astype("int32")
    df["CATEGORIA"] = df["CATEGORIA"].str.strip()
    df["uf"] = df["UF_PROCEDENCIA"].fillna("").str.strip().str[:2]
    df["mun"] = df["MUNICIPIO_PROCEDENCIA"].fillna("").str.strip()
    df = df[df["CATEGORIA"] != ""]
    # agrega ao grão UNIQUE (soma qtd de eventuais homônimos repetidos)
    g = (df.groupby(["ANO", "MES", "uf", "mun", "CATEGORIA"], dropna=False)
           ["QUANTIDADE"].sum().reset_index())
    # crosswalk IBGE (nome normalizado + UF) vetorizado
    g["nn"] = g["mun"].map(norm)
    g["uf2"] = g["uf"].replace("", pd.NA)
    g["codigo_ibge"] = [xw.get((nn, uf)) if (nn and isinstance(uf, str)) else None
                        for nn, uf in zip(g["nn"], g["uf"])]
    g["especie"] = g["CATEGORIA"].map(deriva_especie)
    resolved = int(g["codigo_ibge"].notna().sum())
    # ibge/qtd vêm como numpy.float64 (coluna tem None) -> converter p/ int Python
    payload = [
        (int(a), int(m), (uf or None), (mun or None),
         (None if pd.isna(ibge) else int(ibge)), cat, esp,
         (None if pd.isna(q) else int(q)))
        for a, m, uf, mun, cat, esp, ibge, q in zip(
            g["ANO"], g["MES"], g["uf"], g["mun"], g["CATEGORIA"],
            g["especie"], g["codigo_ibge"], g["QUANTIDADE"])
    ]
    sql = """
        INSERT INTO prospeccao.sigsif_abate_categoria_uf
            (ano, mes, uf, municipio_nome, codigo_ibge, categoria, especie, quantidade)
        VALUES %s
        ON CONFLICT (ano, mes, uf, municipio_nome, categoria) DO UPDATE SET
            codigo_ibge = EXCLUDED.codigo_ibge,
            especie = EXCLUDED.especie,
            quantidade = EXCLUDED.quantidade,
            fonte = EXCLUDED.fonte,
            updated_at = now();
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, payload, page_size=5000)
    conn.commit()
    print(f"[abate] upsert {len(payload)} linhas agregadas (de {n_raw} brutas); "
          f"IBGE resolvido em {resolved}/{len(payload)} ({100*resolved/max(len(payload),1):.1f}%)")


def ingest_estab(conn, xw):
    df = fetch_csv(URLS["estab"])
    df = df.rename(columns=str.strip)
    print(f"[estab] CSV bruto: {len(df)} linhas, cols={list(df.columns)}")
    # grão físico: 1 linha por (nr_sif, area_categoria, categoria_classe)
    # as multiplicações vêm de habilitações de exportação (ocorrências)
    df = df.fillna("")
    df = df.drop_duplicates(subset=["NR_SIF", "AREA_CATEGORIA", "CATEGORIA_CLASSE"])
    rows = []
    resolved = 0
    for r in df.itertuples(index=False):
        nr = (r.NR_SIF or "").strip()
        area = (r.AREA_CATEGORIA or "").strip()
        classe = (r.CATEGORIA_CLASSE or "").strip()
        if not nr or not area or not classe:
            continue
        uf = (r.UF or "").strip()[:2] or None
        mun = (r.MUNICIPIO or "").strip() or None
        ibge = xw.get((norm(mun), uf)) if (mun and uf) else None
        if ibge:
            resolved += 1
        rows.append((
            (r.CPF_CNPJ or "").strip() or None,
            (r.RAZAO_SOCIAL or "").strip() or None,
            (r.NOME_FANTASIA or "").strip() or None,
            nr, (r.SITUACAO or "").strip() or None,
            mun, uf, ibge, area, classe,
            (r.TELEFONE or "").strip() or None,
            (r.EMAIL or "").strip() or None,
        ))
    sql = """
        INSERT INTO prospeccao.sigsif_estabelecimento
            (cpf_cnpj, razao_social, nome_fantasia, nr_sif, situacao,
             municipio, uf, codigo_ibge, area_categoria, categoria_classe,
             telefone, email)
        VALUES %s
        ON CONFLICT (nr_sif, area_categoria, categoria_classe) DO UPDATE SET
            cpf_cnpj = EXCLUDED.cpf_cnpj,
            razao_social = EXCLUDED.razao_social,
            nome_fantasia = EXCLUDED.nome_fantasia,
            situacao = EXCLUDED.situacao,
            municipio = EXCLUDED.municipio,
            uf = EXCLUDED.uf,
            codigo_ibge = EXCLUDED.codigo_ibge,
            telefone = EXCLUDED.telefone,
            email = EXCLUDED.email,
            fonte = EXCLUDED.fonte,
            updated_at = now();
    """
    with conn.cursor() as cur:
        psycopg2.extras.execute_values(cur, sql, rows, page_size=5000)
    conn.commit()
    print(f"[estab] upsert {len(rows)} linhas; IBGE resolvido em "
          f"{resolved}/{len(rows)}")


def main():
    conn = psycopg2.connect(**DB)
    with conn.cursor() as cur:
        cur.execute(DDL)
    conn.commit()
    with conn.cursor() as cur:
        xw = carrega_crosswalk(cur)
    print(f"[crosswalk] {len(xw)} municípios carregados de referencia.municipio")
    ingest_abate(conn, xw)
    ingest_estab(conn, xw)
    conn.close()
    print("OK")


if __name__ == "__main__":
    main()
