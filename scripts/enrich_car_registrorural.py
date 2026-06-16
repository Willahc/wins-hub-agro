"""Enriquecimento DIRECIONADO do elo CNPJ -> CAR -> área via API Registro Rural.

Resolve o gargalo do geomatch (o CAR público anonimizou o dono): a Registro Rural vende,
por API, a ligação CNPJ->imóvel que as fontes públicas não dão mais. Em vez de comprar a base
toda, enriquece SÓ o subconjunto premium (default: os 1.592 leads do Radar ILP) -> grava em
prospeccao.fazenda_area -> o motor v_fazenda_matriz acende (matriz-por-fazenda) e o NDVI passa
a rodar por polígono real desses leads.

Fluxo por CNPJ:
  1. GET /car/busca/cpfcnpj?cpfcnpj=<14dig>&tipo_busca=0  -> lista de códigos CAR do titular
     (o código CAR embute o IBGE: "RS-1234567-...." -> 1234567 = codigo_ibge do município)
  2. GET /car/consulta/{numero_car}/dados                 -> área (e demais dados) do imóvel
  3. upsert (cnpj_basico, codigo_car, codigo_ibge, area_ha) em prospeccao.fazenda_area

Modelo PAGO (carteira/pay-per-query): cada chamada consome crédito. Por isso é direcionado e
idempotente (pula CNPJ já enriquecido). LGPD: só CNPJ (PJ) — nunca CPF de PF (ver
deliverables/MEMO_LGPD_geomatch.md).

Uso (dentro do container api, que tem rede+psycopg2):
    docker exec -i -e REGISTRORURAL_API_KEY=xxxx wins_agro_v1-api-1 python3 - < scripts/enrich_car_registrorural.py
Variáveis:
    REGISTRORURAL_API_KEY  chave da API (sem ela, roda em DRY-RUN: só conta o alvo, não chama nada)
    ALVO_SQL               SQL que retorna (cnpj_basico, cnpj14) — default: leads do ILP
    LIMITE                 nº máx de CNPJs nesta execução (default 100, p/ controlar custo)
"""
import os
import re
import sys
import time
import json

import httpx
import psycopg2
import psycopg2.extras

BASE = "https://api-gateway-v2.registrorural.com.br"
API_KEY = os.getenv("REGISTRORURAL_API_KEY", "").strip()
LIMITE = int(os.getenv("LIMITE", "100"))
PAUSA = 0.4  # s entre chamadas (cortesia + evita rajada)

DB = dict(host=os.getenv("DB_HOST", "db"), port=int(os.getenv("DB_PORT", 5432)),
          dbname=os.getenv("POSTGRES_DB", "wins_agro"), user=os.getenv("POSTGRES_USER", "postgres"),
          password=os.getenv("POSTGRES_PASSWORD", ""))

# Alvo default: CNPJs distintos dos leads do Radar ILP, ainda não enriquecidos.
ALVO_SQL = os.getenv("ALVO_SQL", """
    SELECT DISTINCT l.cnpj_basico,
           regexp_replace(l.cnpj_completo, '\\D', '', 'g') AS cnpj14
    FROM prospeccao.ilp_lead l
    WHERE l.cnpj_completo IS NOT NULL
      AND NOT EXISTS (SELECT 1 FROM prospeccao.fazenda_area fa WHERE fa.cnpj_basico = l.cnpj_basico)
""")

CAR_RE = re.compile(r'^[A-Z]{2}-(\d{7})-')  # extrai IBGE do código CAR


def _ibge_do_car(codigo_car):
    m = CAR_RE.match(codigo_car or "")
    return int(m.group(1)) if m else None


def _achar_area(obj):
    """Procura recursivamente um campo de área (ha) na resposta da consulta do CAR."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (int, float)) and re.search(r'area', k, re.I) and 'perc' not in k.lower():
                return float(v)
        for v in obj.values():
            a = _achar_area(v)
            if a is not None:
                return a
    elif isinstance(obj, list):
        for v in obj:
            a = _achar_area(v)
            if a is not None:
                return a
    return None


def buscar_cars(client, cnpj14):
    r = client.get(f"{BASE}/car/busca/cpfcnpj",
                   params={"cpfcnpj": cnpj14, "tipo_busca": "0", "size": "100"}, timeout=40)
    r.raise_for_status()
    d = r.json()
    return d.get("data", []) if d.get("found") else []


def consultar_car(client, numero_car):
    r = client.get(f"{BASE}/car/consulta/{numero_car}/dados",
                   params={"allow_incomplete_data": "true"}, timeout=40)
    if r.status_code != 200:
        return None
    return r.json()


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    # garante idempotência por código CAR
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_fazenda_area_car "
                "ON prospeccao.fazenda_area(codigo_car) WHERE codigo_car IS NOT NULL")
    conn.commit()

    cur.execute(ALVO_SQL)
    alvo = cur.fetchall()
    print(f"alvo: {len(alvo)} CNPJs a enriquecer (limite desta execução: {LIMITE})", flush=True)

    if not API_KEY:
        print("DRY-RUN: REGISTRORURAL_API_KEY ausente — nada foi chamado/gravado.\n"
              f"  Setaria a chave e rodaria os {min(len(alvo), LIMITE)} primeiros (custo = nº de "
              "consultas de CAR). Ex.: docker exec -i -e REGISTRORURAL_API_KEY=... -e LIMITE=50 ...",
              flush=True)
        return

    alvo = alvo[:LIMITE]
    linhas, n_cnpj_ok, n_car, consultas = [], 0, 0, 0
    with httpx.Client(headers={"X-API-Key": API_KEY, "Accept": "application/json"}) as client:
        for i, (cnpj_basico, cnpj14) in enumerate(alvo, 1):
            try:
                cars = buscar_cars(client, cnpj14); consultas += 1
            except Exception as e:
                print(f"  [{i}] {cnpj14}: falha na busca ({e})", flush=True); time.sleep(PAUSA); continue
            if cars:
                n_cnpj_ok += 1
            for car in cars:
                ibge = _ibge_do_car(car)
                area = None
                try:
                    dados = consultar_car(client, car); consultas += 1
                    area = _achar_area(dados) if dados else None
                except Exception:
                    pass
                linhas.append((cnpj_basico, car, ibge, area, f"ilp:{cnpj_basico}", "registrorural"))
                n_car += 1
                time.sleep(PAUSA)
            print(f"  [{i}/{len(alvo)}] {cnpj14}: {len(cars)} CAR(s)", flush=True)
            time.sleep(PAUSA)

    if linhas:
        psycopg2.extras.execute_values(cur, """
            INSERT INTO prospeccao.fazenda_area
                (cnpj_basico, codigo_car, codigo_ibge, area_ha, lead_ref, fonte_geomatch)
            VALUES %s
            ON CONFLICT (codigo_car) DO UPDATE SET
                cnpj_basico=EXCLUDED.cnpj_basico, codigo_ibge=EXCLUDED.codigo_ibge,
                area_ha=COALESCE(EXCLUDED.area_ha, prospeccao.fazenda_area.area_ha),
                fonte_geomatch=EXCLUDED.fonte_geomatch, updated_at=now()
        """, linhas, page_size=500)
        conn.commit()
    print(f"OK | CNPJs com CAR: {n_cnpj_ok}/{len(alvo)} | imóveis gravados: {n_car} | "
          f"chamadas à API (custo): {consultas}", flush=True)
    cur.close(); conn.close()


if __name__ == "__main__":
    main()
