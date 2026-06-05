"""Ingestão de DEPs reais do Geneplus (sumários públicos) para popular raças além do Nelore.

Fonte: API JSON pública POST /publico/sumario/{id}/filtro/iqg_basico/desc/{page}
(paginator Laravel; cada animal traz ident/nome/sexo/DEPs com acurácia e percentil).

Roda DENTRO do container api (tem httpx + psycopg2 + acesso ao db).
Uso:  python ingest_geneplus.py senepol        # uma raça
      python ingest_geneplus.py all             # todas as raças cobertas
Idempotente: upsert do reprodutor por (registro, raca_id); avaliações regravadas por animal.
"""
import os
import re
import sys
import time
import html as htmllib
import httpx
import psycopg2
import psycopg2.extras

BASE = "https://gppluson.geneplus.com.br"
DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

# sumario_id Geneplus -> (raca_id nosso, slug, nome)
BREEDS = {
    "senepol": (2, 8, "senepol", "Senepol"),
    "canchim": (3, 14, "canchim", "Canchim"),
    "caracu": (4, 15, "caracu", "Caracu"),
    "brahman": (5, 2, "brahman", "Brahman"),
    "brangus": (6, 17, "brangus", "Brangus"),
    "santagertrudis": (7, 19, "santa-gertrudis", "Santa Gertrudis"),
    "limousin": (8, 13, "limousin", "Limousin"),
    "sindi": (9, 6, "sindi", "Sindi"),
    "guzera": (11, 4, "guzera", "Guzerá"),
    "tabapua": (13, 7, "tabapua", "Tabapuã"),
    "montana": (19, 20, "montana", "Montana"),
}

# campo JSON Geneplus -> caracteristica_id nosso
CARAC = {
    "iqg_basico": 20, "pn_dep": 1, "pd_dep": 5, "tmd": 6, "ps_dep": 7,
    "gpd_dep": 8, "cfd_dep": 9, "cfs_dep": 10, "pes_dep": 12,
    "aol_dep": 16, "egs_dep": 17, "mar_dep": 18, "car_dep": 19,
}
# acurácia/percentil quando existirem (sufixos no JSON)
ACC = {"pn_dep": "pn_acc", "pd_dep": "pd_acc", "ps_dep": "ps_acc", "gpd_dep": "gpd_acc",
       "cfd_dep": "cfd_acc", "cfs_dep": "cfs_acc", "pes_dep": "pes_acc",
       "aol_dep": "aol_acc", "egs_dep": "egs_acc", "mar_dep": "mar_acc", "car_dep": "car_acc"}
PCT = {"iqg_basico": "iqg_basico_pt", "pn_dep": "pn_pt", "pd_dep": "pd_pt", "tmd": "tmd_pt",
       "ps_dep": "ps_pt", "gpd_dep": "gpd_pt", "cfd_dep": "cfd_pt", "cfs_dep": "cfs_pt",
       "pes_dep": "pes_pt", "aol_dep": "aol_pt", "egs_dep": "egs_pt", "mar_dep": "mar_pt",
       "car_dep": "car_pt"}


def get_session():
    """Cria client httpx com cookie + csrf token de uma página pública."""
    client = httpx.Client(timeout=40, headers={"User-Agent": "Mozilla/5.0"})
    r = client.get(f"{BASE}/publico/sumario/1")
    m = re.search(r'name="csrf-token" content="([^"]+)"', r.text)
    token = m.group(1) if m else ""
    client.headers.update({
        "X-CSRF-TOKEN": token,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
    })
    return client


def fetch_breed(client, sumario_id):
    """Retorna a lista completa de animais (todas as páginas)."""
    # Paginação real é via ?page=N (o último segmento do path é fixo). Sem isso
    # o endpoint devolve sempre a 1ª página.
    animais = []
    page = 1
    while True:
        url = f"{BASE}/publico/sumario/{sumario_id}/filtro/iqg_basico/desc/0?page={page}"
        r = client.post(url, data={})
        if r.status_code != 200:
            break
        j = r.json()
        data = j.get("data", [])
        if not data:
            break
        animais.extend(data)
        last = j.get("last_page", 1)
        if j.get("current_page", page) >= last:
            break
        page += 1
        time.sleep(0.2)
    return animais


def _num(v):
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def ingest(conn, key):
    sumario_id, raca_id, slug, nome = BREEDS[key]
    client = get_session()
    animais = fetch_breed(client, sumario_id)
    print(f"  [{nome}] {len(animais)} animais recebidos da API")
    if not animais:
        return 0, 0

    fonte = f"Geneplus Público {nome}"
    cur = conn.cursor()
    n_rep = n_aval = 0
    for a in animais:
        registro = (a.get("ident") or "").strip()
        nome_an = (a.get("nome") or registro or "—").strip()
        if not registro:
            continue
        sx = a.get("sx") if a.get("sx") in ("M", "F") else None
        url = f"{BASE}/{slug}/sumario/atj/{registro}/2024"
        cur.execute(
            """
            INSERT INTO mercado.reprodutor
                (registro, nome, especie_codigo, raca_id, sexo, data_nascimento,
                 consanguinidade, genotipado, fazenda_origem, fonte_referencia, fonte_url, coletado_em)
            VALUES (%s,%s,'BOV',%s,%s,%s,%s,%s,%s,%s,%s, now())
            ON CONFLICT (registro, raca_id) DO UPDATE SET
                nome = EXCLUDED.nome, sexo = EXCLUDED.sexo,
                data_nascimento = EXCLUDED.data_nascimento,
                consanguinidade = EXCLUDED.consanguinidade,
                genotipado = EXCLUDED.genotipado,
                fazenda_origem = EXCLUDED.fazenda_origem,
                fonte_referencia = EXCLUDED.fonte_referencia,
                fonte_url = EXCLUDED.fonte_url
            RETURNING id
            """,
            (registro, nome_an, raca_id, sx, a.get("dtn"),
             _num(a.get("cc")), bool(a.get("genotipado")),
             (a.get("fazenda_nome") or None), fonte, url),
        )
        rid = cur.fetchone()[0]
        n_rep += 1

        # regrava avaliações desta fonte (idempotente)
        cur.execute(
            "DELETE FROM mercado.avaliacao WHERE reprodutor_id=%s AND caracteristica_id = ANY(%s)",
            (rid, list(CARAC.values())),
        )
        for field, carac_id in CARAC.items():
            val = _num(a.get(field))
            if val is None:
                continue
            acc = _num(a.get(ACC.get(field))) if ACC.get(field) else None
            pct = _num(a.get(PCT.get(field))) if PCT.get(field) else None
            cur.execute(
                """INSERT INTO mercado.avaliacao
                   (reprodutor_id, caracteristica_id, valor, acuracia, percentil, coletado_em)
                   VALUES (%s,%s,%s,%s,%s, now())""",
                (rid, carac_id, val, acc, pct),
            )
            n_aval += 1
    conn.commit()
    print(f"  [{nome}] {n_rep} reprodutores, {n_aval} avaliações gravadas")
    return n_rep, n_aval


def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "senepol").lower()
    keys = list(BREEDS.keys()) if arg == "all" else [arg]
    conn = psycopg2.connect(**DB)
    tot_r = tot_a = 0
    for k in keys:
        if k not in BREEDS:
            print(f"  raça desconhecida: {k}")
            continue
        r, a = ingest(conn, k)
        tot_r += r
        tot_a += a
    conn.close()
    print(f"TOTAL: {tot_r} reprodutores, {tot_a} avaliações")


if __name__ == "__main__":
    main()
