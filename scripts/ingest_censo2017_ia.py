"""Ingestão do uso de inseminação artificial (IA) e do efetivo bovino por município (IBGE).

Objetivo de negócio: "estabelecimentos que NÃO usam IA" por município = quem ainda
não adotou genética melhorada = ICP primário da plataforma (vale ~20% do score do
município). A coluna estab_sem_ia é a que alimenta o score.

IMPORTANTE — fonte real (premissa do brief corrigida ao vivo):
  O Censo Agropecuário 2017 NÃO publicou no SIDRA nenhuma tabela/variável/classificação
  de "inseminação artificial" por município (varredura dos 1407 agregados do Censo: zero
  hits para período 2017). Os IDs citados no brief (6927/6930/6933) também não batem
  (6930 = ovinos, 6927 = suínos). A ÚNICA fonte SIDRA de IA por município é o
  Censo Agropecuário 2006. Portanto:

  - Uso de IA  -> Censo 2006, SIDRA tab 1673 / var 2072 (nº de estab. que produziram
                  leite de vaca) / classificação 341 "Uso de inseminação artificial",
                  categorias 0=Total, 8063=Usa, 8064=Não usa.
                  Universo = estabelecimentos que produziram leite de vaca.
  - Efetivo    -> Censo 2017 (real), SIDRA tab 6910 / var 2326 (nº estab. com bovinos)
    bovino       e var 2057 (nº de cabeças de bovinos), demais classificações fixadas em Total.

API SIDRA v3:
  https://servicodados.ibge.gov.br/api/v3/agregados/{tab}/periodos/{ano}/variaveis/{var}
      ?localidades=N6[all]&classificacao={cls}[{cat}]
  N6 = municípios; o id da localidade na resposta é o código IBGE de 7 dígitos.

Supressões/sem dado no SIDRA vêm como "X", "-", "..", "..." -> tratadas como NULL.

Roda DENTRO do container api (tem httpx + psycopg2 + acesso ao db host="db").
Uso:  docker exec -i wins_agro_v1-api-1 python3 - < scripts/ingest_censo2017_ia.py
Idempotente: upsert por codigo_ibge (ON CONFLICT). Reexecuções regravam os valores.
"""
import os
import re
import sys
import httpx
import psycopg2
import psycopg2.extras

BASE = "https://servicodados.ibge.gov.br/api/v3/agregados"
DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

# valores que o SIDRA usa para "sem informação / suprimido" -> NULL
NULOS = {"X", "-", "..", "...", "", None}


def to_int(v):
    """Converte string do SIDRA em int; supressões/sem dado -> None."""
    if v is None:
        return None
    s = str(v).strip()
    if s in NULOS:
        return None
    try:
        return int(float(s.replace(",", ".")))
    except ValueError:
        return None


def split_municipio(nome_loc):
    """Extrai (nome, uf). O SIDRA pode devolver 'São Paulo (SP)' (consulta pontual)
    ou 'Jaru - RO' (consulta N6[all]); cobrimos ambos."""
    nome_loc = (nome_loc or "").strip()
    m = re.match(r"^(.*)\s+\(([A-Z]{2})\)\s*$", nome_loc)      # 'Nome (UF)'
    if m:
        return m.group(1).strip(), m.group(2)
    m = re.match(r"^(.*?)\s*-\s*([A-Z]{2})\s*$", nome_loc)     # 'Nome - UF'
    if m:
        return m.group(1).strip(), m.group(2)
    return nome_loc, None


def fetch(url):
    print(f"  GET {url}")
    r = httpx.get(url, timeout=180)
    r.raise_for_status()
    return r.json()


def serie_por_municipio(resultado_bloco, ano):
    """Mapeia codigo_ibge(int) -> (nome, uf, valor) das series de um bloco de resultados."""
    out = {}
    for s in resultado_bloco["series"]:
        loc = s["localidade"]
        cod = int(loc["id"])
        nome, uf = split_municipio(loc["nome"])
        out[cod] = (nome, uf, to_int(s["serie"].get(ano)))
    return out


def carregar_ia():
    """Tab 1673 (Censo 2006): Total / Usa / Não usa por município."""
    cats = {"0": "total", "8063": "usa", "8064": "nao_usa"}
    url = (f"{BASE}/1673/periodos/2006/variaveis/2072"
           f"?localidades=N6[all]&classificacao=341[{','.join(cats)}]")
    data = fetch(url)
    # data[0] é a variável 2072; cada bloco de resultados tem a categoria 341 corrente
    dados = {}  # cod -> {nome, uf, total, com, sem}
    for bloco in data[0]["resultados"]:
        cat_341 = bloco["classificacoes"][0]["categoria"]  # {"0":"Total"} etc.
        cat_id = next(iter(cat_341.keys()))
        slot = cats.get(cat_id)
        if slot is None:
            continue
        for cod, (nome, uf, val) in serie_por_municipio(bloco, "2006").items():
            d = dados.setdefault(cod, {"nome": nome, "uf": uf,
                                       "total": None, "usa": None, "nao_usa": None})
            d[slot] = val
    return dados


def carregar_efetivo():
    """Tab 6910 (Censo 2017): nº estab. com bovinos (2326) e nº de cabeças (2057)."""
    # fixa as 4 classificações da tabela na categoria Total
    cls_total = {"829": "46302", "218": "46502", "3244": "47078", "12517": "113601"}
    clsq = "|".join(f"{c}[{cat}]" for c, cat in cls_total.items())
    url = (f"{BASE}/6910/periodos/2017/variaveis/2326|2057"
           f"?localidades=N6[all]&classificacao={clsq}")
    data = fetch(url)
    dados = {}  # cod -> {estab_bovinos, efetivo_bovino}
    for var in data:
        slot = "estab_bovinos" if var["id"] == "2326" else "efetivo_bovino"
        for bloco in var["resultados"]:
            for cod, (nome, uf, val) in serie_por_municipio(bloco, "2017").items():
                d = dados.setdefault(cod, {"nome": nome, "uf": uf,
                                           "estab_bovinos": None, "efetivo_bovino": None})
                d[slot] = val
                # guarda nome/uf mais confiável (2017) caso 2006 não tenha o município
                d["nome"], d["uf"] = nome, uf
    return dados


def main():
    print("[1/3] Baixando uso de IA (Censo 2006, tab 1673)…")
    ia = carregar_ia()
    print(f"      municípios com linha de IA: {len(ia)}")

    print("[2/3] Baixando efetivo bovino (Censo 2017, tab 6910)…")
    efe = carregar_efetivo()
    print(f"      municípios com linha de efetivo: {len(efe)}")

    # une por codigo_ibge (efetivo 2017 cobre todos os municípios; IA cobre leiteiros)
    todos = set(ia) | set(efe)
    rows = []
    for cod in todos:
        i = ia.get(cod, {})
        e = efe.get(cod, {})
        nome = e.get("nome") or i.get("nome")
        uf = e.get("uf") or i.get("uf")
        rows.append((
            cod, nome, uf,
            i.get("total"), i.get("usa"), i.get("nao_usa"),
            e.get("estab_bovinos"), e.get("efetivo_bovino"),
        ))

    print(f"[3/3] Upsert de {len(rows)} municípios…")
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_values(
                cur,
                """
                INSERT INTO prospeccao.censo2017_ia_municipio
                    (codigo_ibge, municipio, uf, estab_leite_total,
                     estab_com_ia, estab_sem_ia, estab_bovinos, efetivo_bovino, updated_at)
                VALUES %s
                ON CONFLICT (codigo_ibge) DO UPDATE SET
                    municipio         = EXCLUDED.municipio,
                    uf                = EXCLUDED.uf,
                    estab_leite_total = EXCLUDED.estab_leite_total,
                    estab_com_ia      = EXCLUDED.estab_com_ia,
                    estab_sem_ia      = EXCLUDED.estab_sem_ia,
                    estab_bovinos     = EXCLUDED.estab_bovinos,
                    efetivo_bovino    = EXCLUDED.efetivo_bovino,
                    updated_at        = now()
                """,
                rows,
                template="(%s,%s,%s,%s,%s,%s,%s,%s,now())",
                page_size=1000,
            )
        conn.commit()
    finally:
        conn.close()

    print(f"OK — {len(rows)} municípios gravados em prospeccao.censo2017_ia_municipio.")


if __name__ == "__main__":
    main()
