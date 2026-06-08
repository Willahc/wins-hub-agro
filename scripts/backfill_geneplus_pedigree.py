"""
Backfill de pedigree (pai / mãe / avô materno) nos touros Geneplus multi-raça.

A lista pública do Geneplus JÁ traz o pedigree (p_ident/p_nome = pai,
m_ident/m_nome = mãe, pm_ident/pm_nome = avô materno) — o ingest original
só não parseava esses campos. Aqui fazemos UPDATE nos reprodutores já
cadastrados (match por registro+raca_id), preenchendo o pedigree. Depois
o build_matrizes.sql (genérico) materializa as matrizes dessas raças.

Idempotente. Não insere touros novos — só atualiza os existentes.
Rodar no container api:
  docker cp scripts/backfill_geneplus_pedigree.py wins_agro_v1_api_1:/app/
  docker exec -w /app wins_agro_v1_api_1 python backfill_geneplus_pedigree.py
"""
import os
import re
import time
import httpx
import psycopg2

BASE = "https://gppluson.geneplus.com.br"

# sumario_id Geneplus -> raca_id nosso (mesmo mapa do ingest_geneplus.py)
BREEDS = {
    2: 8, 3: 14, 4: 15, 5: 2, 6: 17, 7: 19, 8: 13, 9: 6, 11: 4, 13: 7, 19: 20,
}
# raca_id -> nome (log)
NOMES = {8: "Senepol", 14: "Canchim", 15: "Caracu", 2: "Brahman", 17: "Brangus",
         19: "Santa Gertrudis", 13: "Limousin", 6: "Sindi", 4: "Guzerá",
         7: "Tabapuã", 20: "Montana"}

DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}


def get_session():
    client = httpx.Client(timeout=40, headers={"User-Agent": "Mozilla/5.0"})
    r = client.get(f"{BASE}/publico/sumario/1")
    m = re.search(r'name="csrf-token" content="([^"]+)"', r.text)
    client.headers.update({
        "X-CSRF-TOKEN": m.group(1) if m else "",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
    })
    return client


def fetch_breed(client, sumario_id):
    animais, page = [], 1
    while True:
        url = f"{BASE}/publico/sumario/{sumario_id}/filtro/iqg_basico/desc/0?page={page}"
        j = None
        for tentativa in range(3):
            try:
                r = client.post(url, data={})
                if r.status_code != 200:
                    time.sleep(0.5)
                    continue
                j = r.json()
                break
            except Exception as e:
                time.sleep(0.6)
                if tentativa == 2:
                    print(f"    [pagina {page} sumario {sumario_id}] falha: {e}")
        if not j:
            break
        data = j.get("data", [])
        if not data:
            break
        animais.extend(data)
        if j.get("current_page", page) >= j.get("last_page", 1):
            break
        page += 1
        time.sleep(0.15)
    return animais


def _s(v):
    v = (v or "").strip()
    return v or None


def main():
    client = get_session()
    conn = psycopg2.connect(**DB)
    conn.autocommit = False
    cur = conn.cursor()
    import sys
    only = {int(x) for x in sys.argv[1:]} if len(sys.argv) > 1 else None
    total_upd = 0
    for sumario_id, raca_id in BREEDS.items():
        if only and sumario_id not in only:
            continue
        try:
            animais = fetch_breed(client, sumario_id)
        except Exception as e:
            print(f"  sumario {sumario_id} ({NOMES.get(raca_id, raca_id)}): ERRO no fetch: {e}")
            continue
        upd = 0
        for a in animais:
            registro = _s(a.get("ident"))
            if not registro:
                continue
            pai_r, pai_n = _s(a.get("p_ident")), _s(a.get("p_nome"))
            mae_r, mae_n = _s(a.get("m_ident")), _s(a.get("m_nome"))
            avo_r, avo_n = _s(a.get("pm_ident")), _s(a.get("pm_nome"))
            if not mae_r:
                continue
            cur.execute(
                """
                UPDATE mercado.reprodutor
                SET pai_registro = COALESCE(%s, pai_registro),
                    pai_nome = COALESCE(%s, pai_nome),
                    mae_registro = COALESCE(%s, mae_registro),
                    mae_nome = COALESCE(%s, mae_nome),
                    avo_materno_registro = COALESCE(%s, avo_materno_registro),
                    avo_materno_nome = COALESCE(%s, avo_materno_nome)
                WHERE registro = %s AND raca_id = %s AND sexo = 'M'
                """,
                (pai_r, pai_n, mae_r, mae_n, avo_r, avo_n, registro, raca_id),
            )
            upd += cur.rowcount
        conn.commit()
        total_upd += upd
        print(f"  sumario {sumario_id:3} ({NOMES.get(raca_id, raca_id)}): {len(animais)} animais, {upd} touros com pedigree atualizado")
    print(f"TOTAL touros atualizados: {total_upd}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
