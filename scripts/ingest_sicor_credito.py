"""Ingestão do crédito rural pecuário do SICOR/BCB (OData v2) -> prospeccao.sicor_credito_municipio.

Fonte: https://olinda.bcb.gov.br/olinda/servico/SICOR/versao/v2/odata/
Entidades: InvestMunicipioProduto (INVESTIMENTO) e CusteioMunicipioProduto (CUSTEIO).

Por que importa (doc Fontes de Dados, secao 2.3 / 7): credito de INVESTIMENTO em bovinos por
municipio = fazendas expandindo rebanho / comprando reprodutores = lead quente. E o sinal aberto
mais direto de propensao de compra de genetica e vale 25% do score de municipio.

Particionamento: o Olinda capa a pagina em 10.000 linhas e NAO suporta $skip grande (erro 500),
entao NAO da pra paginar. Particiono por (cdProduto, AnoEmissao, MesEmissao) -> cada fatia < 10k.
Produtos pequenos sao puxados por ano inteiro; so refina por mes se a fatia bater no teto.

Crosswalk: o SICOR usa codigo de municipio/estado proprio do BCB (nao IBGE). Resolvo codigo_ibge
por (nome normalizado + UF). O mapa cdEstado(BCB)->UF e derivado dos proprios dados por "voto" de
municipios cujo nome e unico no Brasil (sem ambiguidade), e usado depois para desambiguar nomes
repetidos.

Roda DENTRO do container api (tem httpx + psycopg2 + rede + acesso ao db):
    docker exec -i wins_agro_v1-api-1 python3 - < scripts/ingest_sicor_credito.py
Variaveis de ambiente opcionais: SICOR_ANOS="2019-2026" (default 2013-2026).
Idempotente: upsert por (cd_municipio_bcb, ano, finalidade, cd_produto).
"""
import os
import sys
import time
import unicodedata
from collections import defaultdict, Counter

import httpx
import psycopg2
import psycopg2.extras

BASE = "https://olinda.bcb.gov.br/olinda/servico/SICOR/versao/v2/odata"
PAGE_CAP = 10000

DB = dict(
    host=os.getenv("DB_HOST", "db"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("POSTGRES_DB", "wins_agro"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD", ""),
)

# cdProduto SICOR -> rotulo (produtos pecuaria de bovinos de corte/genetica)
PRODUTOS = {
    "1300": "BOVINOS",
    "7580": "MATRIZES E REPRODUTORES",
    "5555": "CONFINAMENTO DE BOVINOS",
    "7720": "RASTREABILIDADE BOVINOS/BUBALINOS",
}

# (entidade OData, finalidade, campo de valor, campo de area)
# CusteioMunicipioProduto existe no service-doc mas devolve vazio/sem EntityType (quebrado no BCB
# em jun/2026) — e o score de municipio usa so INVESTIMENTO. Fica so investimento.
ENTIDADES = [
    ("InvestMunicipioProduto", "INVESTIMENTO", "VlInvest", "AreaInvest"),
]

MESES = [f"{m:02d}" for m in range(1, 13)]


def anos_range():
    spec = os.getenv("SICOR_ANOS", "2013-2026")
    a, b = spec.split("-")
    return [str(y) for y in range(int(a), int(b) + 1)]


def norm(s: str) -> str:
    """uppercase sem acento, so alnum+espaco — mesmo transform nos dois lados do join."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper()
    out = []
    for c in s:
        out.append(c if (c.isalnum() or c == " ") else " ")
    return " ".join("".join(out).split())


def fetch(client, entidade, valor_field, area_field, cd_prod, ano, mes=None):
    """Retorna lista de dicts de uma fatia. Refina por mes se bater no teto de pagina."""
    filt = f"cdProduto eq '{cd_prod}' and AnoEmissao eq '{ano}'"
    if mes:
        filt += f" and MesEmissao eq '{mes}'"
    sel = f"Municipio,cdMunicipio,cdEstado,nomeProduto,{valor_field},{area_field}"
    url = (
        f"{BASE}/{entidade}?$format=json&$top={PAGE_CAP}"
        f"&$filter={filt}&$select={sel}"
    )
    for attempt in range(4):
        try:
            r = client.get(url, timeout=120)
            if r.status_code == 200:
                rows = r.json().get("value", [])
                break
            # 500/403 transitorio -> backoff
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            time.sleep(1.5 * (attempt + 1))
    else:
        print(f"  ! FALHA fatia prod={cd_prod} ano={ano} mes={mes}", flush=True)
        return []
    # bateu no teto e ainda nao particionou por mes -> refina
    if len(rows) >= PAGE_CAP and mes is None:
        out = []
        for m in MESES:
            out.extend(fetch(client, entidade, valor_field, area_field, cd_prod, ano, m))
            time.sleep(0.3)
        return out
    return rows


def main():
    anos = anos_range()
    print(f"SICOR ingest | anos={anos[0]}..{anos[-1]} | produtos={list(PRODUTOS)}", flush=True)

    # agg[(cd_mun, nome, cd_est, ano, finalidade, cd_prod)] = [vl, area, n, nome_produto]
    agg = defaultdict(lambda: [0.0, 0.0, 0, None])

    with httpx.Client(headers={"Accept": "application/json"}) as client:
        for entidade, finalidade, vfield, afield in ENTIDADES:
            for cd_prod in PRODUTOS:
                # CUSTEIO so faz sentido para BOVINOS (1300); produtos de invest. especificos nao existem em custeio
                if finalidade == "CUSTEIO" and cd_prod != "1300":
                    continue
                for ano in anos:
                    rows = fetch(client, entidade, vfield, afield, cd_prod, ano)
                    for x in rows:
                        cd_mun = (x.get("cdMunicipio") or "").strip()
                        nome = (x.get("Municipio") or "").strip().strip('"')
                        cd_est = (x.get("cdEstado") or "").strip()
                        if not cd_mun:
                            continue
                        try:
                            vl = float(x.get(vfield) or 0)
                        except (TypeError, ValueError):
                            vl = 0.0
                        try:
                            ar = float(x.get(afield) or 0)
                        except (TypeError, ValueError):
                            ar = 0.0
                        k = (cd_mun, nome, cd_est, int(ano), finalidade, cd_prod)
                        rec = agg[k]
                        rec[0] += vl
                        rec[1] += ar
                        rec[2] += 1
                        rec[3] = (x.get("nomeProduto") or "").strip().strip('"') or PRODUTOS[cd_prod]
                    print(f"  {entidade[:7]} prod={cd_prod} ano={ano}: {len(rows)} contratos", flush=True)
                    time.sleep(0.2)

    print(f"chaves agregadas: {len(agg)}", flush=True)

    # ---- crosswalk ----
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT codigo_ibge, nome, uf FROM referencia.municipio")
    by_name = defaultdict(dict)          # nome_norm -> {uf: codigo_ibge}
    name_ufs = defaultdict(set)          # nome_norm -> set(uf)
    for ibge, nome, uf in cur.fetchall():
        nm = norm(nome)
        by_name[nm][uf] = ibge
        name_ufs[nm].add(uf)

    # cdEstado(BCB) -> UF por voto de nomes globalmente unicos
    votos = defaultdict(Counter)
    for (cd_mun, nome, cd_est, ano, fin, prod), _ in agg.items():
        nm = norm(nome)
        if cd_est and len(name_ufs.get(nm, ())) == 1:
            uf = next(iter(name_ufs[nm]))
            votos[cd_est][uf] += 1
    est2uf = {est: c.most_common(1)[0][0] for est, c in votos.items()}
    print(f"crosswalk cdEstado->UF resolvido: {len(est2uf)} estados", flush=True)

    # ---- resolver codigo_ibge e montar linhas ----
    linhas = []
    matched = 0
    unmatched_samples = []
    for (cd_mun, nome, cd_est, ano, fin, prod), (vl, ar, n, nomeprod) in agg.items():
        nm = norm(nome)
        uf = est2uf.get(cd_est)
        ibge = None
        ufs = by_name.get(nm)
        if ufs:
            if uf and uf in ufs:
                ibge = ufs[uf]
            elif len(ufs) == 1:
                ibge = next(iter(ufs.values()))
        if ibge:
            matched += 1
        elif len(unmatched_samples) < 15:
            unmatched_samples.append((nome, cd_est, uf))
        linhas.append((cd_mun, nome, cd_est, uf, ibge, ano, fin, prod,
                       nomeprod, round(vl, 2), round(ar, 2), n))

    print(f"linhas: {len(linhas)} | codigo_ibge resolvido: {matched} "
          f"({100*matched/max(len(linhas),1):.1f}%)", flush=True)
    if unmatched_samples:
        print("  amostra nao resolvida:", unmatched_samples[:10], flush=True)

    # ---- upsert ----
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO prospeccao.sicor_credito_municipio
            (cd_municipio_bcb, municipio_nome, cd_estado_bcb, uf, codigo_ibge,
             ano, finalidade, cd_produto, nome_produto, vl_total_brl, area_total_ha, n_contratos)
        VALUES %s
        ON CONFLICT (cd_municipio_bcb, ano, finalidade, cd_produto) DO UPDATE SET
            municipio_nome = EXCLUDED.municipio_nome,
            cd_estado_bcb  = EXCLUDED.cd_estado_bcb,
            uf             = EXCLUDED.uf,
            codigo_ibge    = EXCLUDED.codigo_ibge,
            nome_produto   = EXCLUDED.nome_produto,
            vl_total_brl   = EXCLUDED.vl_total_brl,
            area_total_ha  = EXCLUDED.area_total_ha,
            n_contratos    = EXCLUDED.n_contratos,
            updated_at     = now()
        """,
        linhas,
        page_size=2000,
    )
    conn.commit()
    cur.execute("SELECT count(*), count(codigo_ibge) FROM prospeccao.sicor_credito_municipio")
    tot, res = cur.fetchone()
    print(f"OK | tabela agora: {tot} linhas, {res} com codigo_ibge", flush=True)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
