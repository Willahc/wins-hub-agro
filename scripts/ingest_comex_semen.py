"""Ingestao da exportacao de semen bovino e bovinos vivos por municipio (Comex Stat / MDIC).

Fonte: https://api-comexstat.mdic.gov.br  (endpoint POST /cities e POST /general).

Por que importa (mapa de players de genetica, NAO e' componente de score):
  - Semen bovino (NCM 05111000) exportado por municipio aponta onde ficam as centrais de
    inseminacao de alto padrao -> clientes naturais e concorrentes diretos do catalogo.
  - Bovinos vivos (NCM 0102) por municipio = exportadores de animais (matrizes/reprodutores).
  - Embrioes (NCM 04061000) complementam o mapa de material genetico.

LIMITACAO REAL DA FONTE (confirmada ao vivo em jun/2026, NAO e' bug do loader):
  O endpoint municipal POST /cities NAO aceita NCM de 8 digitos nem subposicao (HS6). So aceita
  filtro/detalhe ate' a POSICAO HS4 (campo "heading"). Logo, por municipio so' da' pra puxar:
      - HS4 0102  -> "Animais vivos da especie bovina"  (limpo: e' exatamente bovinos vivos)
      - HS4 0511  -> "Produtos de origem animal n.e."    (contem o semen 05111000, mas tambem
                     outros produtos animais; na pratica a maior parte da exportacao BR de 0511
                     e' material genetico bovino). E' o melhor proxy MUNICIPAL de semen possivel.
  Para o NCM 8 digitos ISOLADO (semen 05111000 puro, embrioes 04061000) usamos o endpoint
  POST /general, que aceita NCM completo mas so' detalha ate' ESTADO (UF), nao municipio.

Estrategia de ingestao (dois niveis na mesma tabela, distinguidos pela coluna `nivel`):
  nivel='MUNICIPIO' : POST /cities, HS4 0102 e 0511, detalhe city -> codigo_ibge resolvido.
  nivel='UF'        : POST /general, NCM8 05111000 / 0102* / 04061000, detalhe state -> uf.

Schema do POST (confirmado ao vivo, igual ao pacote R `comexr`):
  {"flow":"export","monthDetail":false,"period":{"from":"YYYY-MM","to":"YYYY-MM"},
   "filters":[{"filter":"heading","values":["0511"]}],
   "details":["city"],"metrics":["metricFOB","metricKG"]}
  query string ?language=pt . Rate limit ~1 req / 10s (HTTP 429 senao).

O /cities devolve o municipio como "noMunMinsgUf" = "Nome do Municipio - UF" (SEM codigo IBGE).
Resolvo codigo_ibge por (nome_normalizado + uf) contra referencia.municipio. Ha' um bucket
"Municipio nao declarado" -> gravado com nao_declarado=true e codigo_ibge NULL.

Roda DENTRO do container api (tem httpx + psycopg2 + rede + db host=db):
    docker exec -i wins_agro_v1-api-1 python3 - < scripts/ingest_comex_semen.py

Variaveis de ambiente opcionais:
    COMEX_FROM="2019-01"  COMEX_TO="2025-12"  (default 2019-01 .. 2025-12)

Idempotente: upsert ON CONFLICT (nivel, municipio, uf, ncm, ano) -- a chave usa o NOME do
municipio (nao o IBGE), entao cobre o caso codigo_ibge NULL sem colidir.
"""
import os
import sys
import time
import unicodedata

import httpx
import psycopg2
import psycopg2.extras

BASE = "https://api-comexstat.mdic.gov.br"
HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (WiNS Agro data ingest)",
}
RATE_SLEEP = 11.0  # API limita ~1 req / 10s -> 429

DB = dict(
    host=os.getenv("DB_HOST", "db"),
    port=int(os.getenv("DB_PORT", 5432)),
    dbname=os.getenv("POSTGRES_DB", "wins_agro"),
    user=os.getenv("POSTGRES_USER", "postgres"),
    password=os.getenv("POSTGRES_PASSWORD", ""),
)

# Nivel MUNICIPIO: HS4 (heading) -> descricao curta. So o que /cities aceita.
HEADINGS_MUNICIPIO = {
    "0102": "Bovinos vivos (HS4 0102)",
    "0511": "Produtos de origem animal n.e. (HS4 0511; inclui semen bovino 05111000)",
}
# Nivel UF: NCM 8 digitos isolado via /general (detalhe state).
NCMS_UF = {
    "05111000": "Semen de bovino",
    "04061000": "Queijos frescos / embrioes (NCM 04061000)",
}
# Bovinos vivos isolados por NCM8 sao varios (01022*); puxo por heading 0102 no /general (HS4)
# para ter a UF agregada sem precisar enumerar cada subitem.
HEADINGS_UF = {
    "0102": "Bovinos vivos (HS4 0102)",
}


# Nome do estado (como o /general devolve em pt) -> sigla UF. Evita uf NULL no nivel UF
# (NULL quebra o ON CONFLICT, que trata NULL <> NULL, e duplicaria a cada rodada).
UF_SIGLA = {
    "ACRE": "AC", "ALAGOAS": "AL", "AMAPA": "AP", "AMAZONAS": "AM", "BAHIA": "BA",
    "CEARA": "CE", "DISTRITO FEDERAL": "DF", "ESPIRITO SANTO": "ES", "GOIAS": "GO",
    "MARANHAO": "MA", "MATO GROSSO": "MT", "MATO GROSSO DO SUL": "MS",
    "MINAS GERAIS": "MG", "PARA": "PA", "PARAIBA": "PB", "PARANA": "PR",
    "PERNAMBUCO": "PE", "PIAUI": "PI", "RIO DE JANEIRO": "RJ",
    "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS", "RONDONIA": "RO",
    "RORAIMA": "RR", "SANTA CATARINA": "SC", "SAO PAULO": "SP", "SERGIPE": "SE",
    "TOCANTINS": "TO",
}


def norm(s: str) -> str:
    """UPPER sem acento, so alnum+espaco -- mesmo transform dos dois lados do join com IBGE."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.upper()
    out = [c if (c.isalnum() or c == " ") else " " for c in s]
    return " ".join("".join(out).split())


def period():
    return os.getenv("COMEX_FROM", "2019-01"), os.getenv("COMEX_TO", "2025-12")


def post(client, endpoint, body):
    """POST com retry/backoff respeitando o rate limit (429)."""
    url = f"{BASE}{endpoint}?language=pt"
    for attempt in range(5):
        try:
            r = client.post(url, json=body, timeout=120, headers=HEADERS)
            if r.status_code == 200:
                return r.json().get("data", {}).get("list", []) or []
            if r.status_code == 429:
                time.sleep(RATE_SLEEP + 4 * attempt)
                continue
            print(f"  ! HTTP {r.status_code} {endpoint}: {r.text[:200]}", flush=True)
            time.sleep(RATE_SLEEP)
        except Exception as e:
            print(f"  ! erro {endpoint}: {e!r}", flush=True)
            time.sleep(RATE_SLEEP)
    return []


def split_mun_uf(txt: str):
    """'Botucatu - SP' -> ('Botucatu','SP'). 'Municipio nao declarado - ...' -> (txt, None)."""
    if not txt:
        return txt, None
    # UF e' o ultimo token de 2 letras apos ' - '
    if " - " in txt:
        head, tail = txt.rsplit(" - ", 1)
        tail = tail.strip()
        if len(tail) == 2 and tail.isalpha():
            return head.strip(), tail.upper()
    return txt.strip(), None


def build_ibge_map(cur):
    """(nome_normalizado, uf) -> codigo_ibge a partir de referencia.municipio."""
    cur.execute("SELECT nome_normalizado, uf, codigo_ibge FROM referencia.municipio")
    m = {}
    for nome_norm, uf, ibge in cur.fetchall():
        m[(nome_norm, uf)] = ibge
    # Overrides de grafia/renomeacao que o Comex usa e nao batem no IBGE atual:
    m[(norm("Embu"), "SP")] = 3515103            # Embu -> Embu das Artes (renomeado 2010)
    m[(norm("Santa Isabel do Para"), "PA")] = 1506401
    return m


UPSERT = """
INSERT INTO prospeccao.comex_export_municipio
    (codigo_ibge, municipio, uf, ncm, descricao, nivel, ano, vl_fob_usd, kg, nao_declarado)
VALUES %s
ON CONFLICT (nivel, municipio, uf, ncm, ano) DO UPDATE SET
    codigo_ibge   = EXCLUDED.codigo_ibge,
    descricao     = EXCLUDED.descricao,
    vl_fob_usd    = EXCLUDED.vl_fob_usd,
    kg            = EXCLUDED.kg,
    nao_declarado = EXCLUDED.nao_declarado,
    updated_at    = now();
"""


def to_num(v):
    try:
        return float(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def main():
    pfrom, pto = period()
    print(f"Comex Stat ingest | periodo {pfrom}..{pto}", flush=True)
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()
    ibge_map = build_ibge_map(cur)
    print(f"  crosswalk IBGE carregado: {len(ibge_map)} municipios", flush=True)

    rows = []
    client = httpx.Client()

    # ---------- NIVEL MUNICIPIO (POST /cities, HS4) ----------
    for heading, desc in HEADINGS_MUNICIPIO.items():
        body = {
            "flow": "export", "monthDetail": False,
            "period": {"from": pfrom, "to": pto},
            "filters": [{"filter": "heading", "values": [heading]}],
            "details": ["city"],
            "metrics": ["metricFOB", "metricKG"],
        }
        data = post(client, "/cities", body)
        print(f"  /cities heading={heading}: {len(data)} linhas (municipio x ano)", flush=True)
        for d in data:
            mun_raw = d.get("noMunMinsgUf") or d.get("city") or ""
            mun, uf = split_mun_uf(mun_raw)
            nao_decl = "nao declarado" in mun.lower() or "não declarado" in mun.lower()
            ibge = None if nao_decl else ibge_map.get((norm(mun), uf))
            rows.append((
                ibge, mun_raw.strip() or "NAO DECLARADO", uf, heading, desc,
                "MUNICIPIO", int(d.get("year")),
                to_num(d.get("metricFOB")), to_num(d.get("metricKG")), nao_decl,
            ))
        time.sleep(RATE_SLEEP)

    # ---------- NIVEL UF (POST /general) ----------
    def pull_uf(filtro, valor, ncm_label, desc):
        body = {
            "flow": "export", "monthDetail": False,
            "period": {"from": pfrom, "to": pto},
            "filters": [{"filter": filtro, "values": [valor]}],
            "details": ["state"],
            "metrics": ["metricFOB", "metricKG"],
        }
        data = post(client, "/general", body)
        print(f"  /general {filtro}={valor}: {len(data)} linhas (UF x ano)", flush=True)
        for d in data:
            uf_nome = (d.get("state") or "").strip()
            sigla = UF_SIGLA.get(norm(uf_nome), "ND")  # 'ND' em vez de NULL -> ON CONFLICT estavel
            nao_decl = "nao declarado" in uf_nome.lower()
            rows.append((
                None, uf_nome or "NAO DECLARADO", sigla, ncm_label, desc,
                "UF", int(d.get("year")),
                to_num(d.get("metricFOB")), to_num(d.get("metricKG")), nao_decl,
            ))
        time.sleep(RATE_SLEEP)

    for ncm, desc in NCMS_UF.items():
        pull_uf("ncm", ncm, ncm, desc)
    for heading, desc in HEADINGS_UF.items():
        pull_uf("heading", heading, heading, desc)

    # ---------- upsert ----------
    if rows:
        psycopg2.extras.execute_values(cur, UPSERT, rows, page_size=500)
        conn.commit()
    print(f"\nTotal upsert: {len(rows)} linhas", flush=True)

    cur.execute("""
        SELECT nivel,
               count(*) linhas,
               count(*) FILTER (WHERE codigo_ibge IS NOT NULL) com_ibge,
               count(*) FILTER (WHERE nao_declarado) nao_decl
        FROM prospeccao.comex_export_municipio GROUP BY nivel ORDER BY nivel
    """)
    print("\n== Resumo por nivel ==", flush=True)
    for r in cur.fetchall():
        print(f"  {r[0]:9s} linhas={r[1]:5d} com_ibge={r[2]:5d} nao_declarado={r[3]}", flush=True)

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
