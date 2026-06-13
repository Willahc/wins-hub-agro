"""Ingestão de FÊMEAS avaliadas (matrizes reais) do sumário público Geneplus.

Fonte: sumário "Fêmeas do Futuro®" do GP PLUS ON (Embrapa Geneplus).
  Diferente do sumário de touros, este publica MATRIZES com índice IQGg real,
  DEPs, acurácia, percentil, data de nascimento, fazenda de origem e pedigree
  (pai/mãe). Ou seja: fêmeas DE VERDADE avaliadas — não nomes de pedigree.

Endpoint (mesmo paginator Laravel do ingest_geneplus.py, mas com contrato=<id>):
  POST /publico/sumario/{sumario_id}/filtro/iqg_basico/desc/0
       data = {page, contrato, _token}
  O parametro `contrato` seleciona a tabela "Fêmeas do Futuro" (vide BREEDS).

Apenas 2 raças publicam sumário de fêmeas no Geneplus público:
  - Nelore  (sumario 1,  contrato 1148) ~19,5 mil fêmeas
  - Montana (sumario 19, contrato 1271) ~293 fêmeas
As demais raças só publicam touros (sem opção "Fêmeas do Futuro").

Carrega em mercado.reprodutor com sexo='F', fonte_programa='geneplus_femea'.
IQGg + DEPs vão para mercado.avaliacao. Idempotente: upsert por (registro,raca_id),
avaliações desta fonte regravadas por animal. Faz UPGRADE de linhas pedigree_dam
existentes (mesmo registro) para fêmea avaliada real.

Roda DENTRO do container api:
  docker exec -i wins_agro_v1_api_1 python /caminho/ingest_geneplus_femeas.py [nelore|montana|all]
"""
import os
import re
import sys
import time
import httpx
import psycopg2

BASE = "https://gppluson.geneplus.com.br"
DB = {
    "host": os.getenv("DB_HOST", "db"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("POSTGRES_DB", "wins_agro"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", ""),
}

# key -> (sumario_id Geneplus, contrato fêmeas, raca_id nosso, slug, nome)
BREEDS = {
    "nelore":  (1,  1148, 1,  "nelore",  "Nelore"),
    "montana": (19, 1271, 20, "montana", "Montana"),
}

# campo JSON Geneplus -> caracteristica_id nosso  (igual ao ingest de touros)
CARAC = {
    "iqg_basico": 20, "pn_dep": 1, "pd_dep": 5, "tmd": 6, "ps_dep": 7,
    "gpd_dep": 8, "cfd_dep": 9, "cfs_dep": 10, "pes_dep": 12,
    "aol_dep": 16, "egs_dep": 17, "mar_dep": 18, "car_dep": 19,
}
ACC = {"pn_dep": "pn_acc", "pd_dep": "pd_acc", "ps_dep": "ps_acc", "gpd_dep": "gpd_acc",
       "cfd_dep": "cfd_acc", "cfs_dep": "cfs_acc", "pes_dep": "pes_acc",
       "aol_dep": "aol_acc", "egs_dep": "egs_acc", "mar_dep": "mar_acc", "car_dep": "car_acc"}
PCT = {"iqg_basico": "iqg_basico_pt", "pn_dep": "pn_pt", "pd_dep": "pd_pt", "tmd": "tmd_pt",
       "ps_dep": "ps_pt", "gpd_dep": "gpd_pt", "cfd_dep": "cfd_pt", "cfs_dep": "cfs_pt",
       "pes_dep": "pes_pt", "aol_dep": "aol_pt", "egs_dep": "egs_pt", "mar_dep": "mar_pt",
       "car_dep": "car_pt"}


def get_session(sumario_id):
    client = httpx.Client(timeout=60, verify=False, follow_redirects=True,
                          headers={"User-Agent": "Mozilla/5.0"})
    r = client.get(f"{BASE}/publico/sumario/{sumario_id}")
    m = re.search(r'name="csrf-token" content="([^"]+)"', r.text)
    token = m.group(1) if m else ""
    client.headers.update({
        "X-CSRF-TOKEN": token,
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
    })
    return client, token


def fetch_breed(client, token, sumario_id, contrato):
    animais = []
    page = 1
    while True:
        url = f"{BASE}/publico/sumario/{sumario_id}/filtro/iqg_basico/desc/0"
        for attempt in range(3):
            try:
                r = client.post(url, data={"page": page, "contrato": contrato, "_token": token})
                break
            except Exception as e:
                if attempt == 2:
                    print(f"    page {page} falhou: {e}")
                    return animais
                time.sleep(1.5)
        if r.status_code != 200:
            break
        j = r.json()
        data = j.get("data", [])
        if not data:
            break
        animais.extend(data)
        last = j.get("last_page", 1)
        cur = j.get("current_page", page)
        if page == 1:
            print(f"    total={j.get('total')} paginas={last}")
        if cur % 100 == 0:
            print(f"    ... pagina {cur}/{last} ({len(animais)} fêmeas)")
        if cur >= last:
            break
        page += 1
        time.sleep(0.1)
    return animais


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def ingest(conn, key):
    sumario_id, contrato, raca_id, slug, nome = BREEDS[key]
    client, token = get_session(sumario_id)
    print(f"  [{nome}] coletando Fêmeas do Futuro (contrato {contrato})...")
    animais = fetch_breed(client, token, sumario_id, contrato)
    print(f"  [{nome}] {len(animais)} fêmeas recebidas da API")
    if not animais:
        return 0, 0

    fonte = f"Geneplus Fêmeas do Futuro {nome}"
    cur = conn.cursor()
    n_rep = n_aval = n_female = 0
    for a in animais:
        registro = (a.get("ident") or "").strip()
        if not registro:
            continue
        nome_an = (a.get("nome") or registro or "—").strip()
        sx = a.get("sx") if a.get("sx") in ("M", "F") else "F"
        if sx != "F":
            continue  # somente fêmeas (evitar overlap com agente dos touros)
        n_female += 1
        url = f"{BASE}/{slug}/sumario/atj/{registro}/2024"
        cur.execute(
            """
            INSERT INTO mercado.reprodutor
                (registro, nome, especie_codigo, raca_id, sexo, data_nascimento,
                 consanguinidade, genotipado, fazenda_origem,
                 pai_registro, pai_nome, mae_registro, mae_nome,
                 fonte_referencia, fonte_url, fonte_programa, coletado_em)
            VALUES (%s,%s,'BOV',%s,'F',%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'geneplus_femea', now())
            ON CONFLICT (registro, raca_id) DO UPDATE SET
                nome = EXCLUDED.nome, sexo = 'F',
                data_nascimento = COALESCE(EXCLUDED.data_nascimento, mercado.reprodutor.data_nascimento),
                consanguinidade = COALESCE(EXCLUDED.consanguinidade, mercado.reprodutor.consanguinidade),
                genotipado = EXCLUDED.genotipado,
                fazenda_origem = COALESCE(EXCLUDED.fazenda_origem, mercado.reprodutor.fazenda_origem),
                pai_registro = COALESCE(NULLIF(EXCLUDED.pai_registro,''), mercado.reprodutor.pai_registro),
                pai_nome = COALESCE(NULLIF(EXCLUDED.pai_nome,''), mercado.reprodutor.pai_nome),
                mae_registro = COALESCE(NULLIF(EXCLUDED.mae_registro,''), mercado.reprodutor.mae_registro),
                mae_nome = COALESCE(NULLIF(EXCLUDED.mae_nome,''), mercado.reprodutor.mae_nome),
                fonte_referencia = EXCLUDED.fonte_referencia,
                fonte_url = EXCLUDED.fonte_url,
                fonte_programa = 'geneplus_femea'
            RETURNING id
            """,
            (registro, nome_an, raca_id, a.get("dtn"),
             _num(a.get("cc")), bool(a.get("genotipado")),
             (a.get("fazenda_nome") or None),
             (a.get("p_ident") or None), (a.get("p_nome") or None),
             (a.get("m_ident") or None), (a.get("m_nome") or None),
             fonte, url),
        )
        rid = cur.fetchone()[0]
        n_rep += 1

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
        if n_rep % 2000 == 0:
            conn.commit()
            print(f"    gravadas {n_rep} fêmeas...")
    conn.commit()
    print(f"  [{nome}] {n_rep} fêmeas, {n_aval} avaliações gravadas (de {n_female} F na API)")
    return n_rep, n_aval


def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    keys = list(BREEDS.keys()) if arg == "all" else [arg]
    conn = psycopg2.connect(**DB)
    tot_r = tot_a = 0
    for k in keys:
        if k not in BREEDS:
            print(f"  raça sem sumário de fêmeas: {k}")
            continue
        r, a = ingest(conn, k)
        tot_r += r
        tot_a += a
    conn.close()
    print(f"TOTAL: {tot_r} fêmeas avaliadas, {tot_a} avaliações")


if __name__ == "__main__":
    main()
