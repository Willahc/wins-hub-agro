#!/usr/bin/env python3
"""Enriquece a fila de leads (corte) com os DECISORES reais via QSA da Receita
(BrasilAPI, gratuito, ao vivo) e PERSISTE em prospeccao.lead_decisor.

Resolve 'e-mail fiscal != decisor': o sócio-administrador pessoa física de uma
fazenda familiar É quem decide a compra de sêmen. ICP: marca CORPORATIVO quando
os sócios são só holdings/S.A. (não é o comprador Nelore elite da Monte Sião).

Resumível: pula CNPJ já gravado (a menos de --redo). UPSERT por linha → progresso
parcial nunca se perde. Throttle p/ rate-limit BrasilAPI; 429 -> backoff.

Uso (container api):
  docker exec wins_agro_v1_api_1 python /app/enrich_decisores.py [--ufs MS,GO,MT,TO] [--nacional] [--limit N] [--redo]
"""
import os, sys, time, json, argparse
import psycopg2, psycopg2.extras, httpx

ap = argparse.ArgumentParser()
ap.add_argument("--ufs", default="MS,GO,MT,TO")
ap.add_argument("--nacional", action="store_true")
ap.add_argument("--limit", type=int, default=100000)
ap.add_argument("--cap-min", type=float, default=5_000_000)
ap.add_argument("--cap-max", type=float, default=1e12)   # sem teto p/ persistência (tipo marca corporativo)
ap.add_argument("--redo", action="store_true", help="re-enriquece mesmo já gravados")
A = ap.parse_args()
UFS = None if A.nacional else A.ufs.split(",")

DB = dict(host=os.getenv("DB_HOST", "db"), port=int(os.getenv("DB_PORT", 5432)),
          dbname=os.getenv("POSTGRES_DB", "wins_agro"), user=os.getenv("POSTGRES_USER", "postgres"),
          password=os.getenv("POSTGRES_PASSWORD", ""))

SQL = """
SELECT * FROM (
  SELECT DISTINCT ON (e.cnpj_basico)
         e.cnpj_basico,
         e.cnpj_basico||e.cnpj_ordem||e.cnpj_dv AS cnpj14,
         COALESCE(NULLIF(em.razao_social,''), e.nome_fantasia) AS razao,
         e.municipio_nome AS municipio, e.uf,
         e.ddd_1||e.telefone_1 AS tel,
         em.capital_social::numeric AS cap
  FROM cnpj.estabelecimento_rural e
  LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico=e.cnpj_basico
  WHERE e.cnae_fiscal_principal='0151201' AND e.situacao_cadastral='02'
    AND e.telefone_1 IS NOT NULL
    AND (%(ufs)s IS NULL OR e.uf = ANY(%(ufs)s))
    AND em.capital_social::numeric BETWEEN %(cmin)s AND %(cmax)s
) s ORDER BY cap DESC LIMIT %(lim)s;
"""

DECISOR_QUALS = ("Administrador", "Sócio-Administrador", "Sócio", "Presidente",
                 "Diretor", "Titular", "Empresário", "Proprietário")
HOLDING_HINT = (" S/A", " S.A", " S A", "PARTICIPAC", " LTDA", "HOLDING", "EMPREEND", " FUNDO", "INVESTIMENT")

def is_pessoa(nome):
    n = (nome or "").upper()
    return not any(h in n for h in HOLDING_HINT)

def fetch_qsa(client, cnpj):
    for attempt in range(5):
        try:
            r = client.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}", timeout=25)
            if r.status_code == 429:
                time.sleep(5 + attempt * 5); continue
            if r.status_code == 504:
                time.sleep(2 + attempt); continue
            if r.status_code != 200:
                return None, f"http {r.status_code}"
            return r.json(), None
        except Exception as ex:
            time.sleep(2 + attempt)
            if attempt == 4:
                return None, str(ex)[:40]
    return None, "rate-limit"

def main():
    conn = psycopg2.connect(**DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(SQL, dict(ufs=UFS, cmin=A.cap_min, cmax=A.cap_max, lim=A.limit))
    rows = cur.fetchall()

    done = set()
    if not A.redo:
        cur.execute("SELECT cnpj_basico FROM prospeccao.lead_decisor")
        done = {r["cnpj_basico"] for r in cur.fetchall()}
    todo = [r for r in rows if r["cnpj_basico"] not in done]
    scope = "NACIONAL" if A.nacional else ",".join(UFS)
    print(f"[scope {scope}] {len(rows)} candidatos | {len(done)} já feitos | {len(todo)} a fazer", file=sys.stderr, flush=True)

    UPSERT = """
    INSERT INTO prospeccao.lead_decisor
      (cnpj_basico,cnpj14,razao,uf,municipio,tipo,decisores,decisor_top,situacao_viva,porte,qsa,enriched_at)
    VALUES (%(cnpj_basico)s,%(cnpj14)s,%(razao)s,%(uf)s,%(municipio)s,%(tipo)s,%(decisores)s,%(decisor_top)s,
            %(situacao_viva)s,%(porte)s,%(qsa)s,now())
    ON CONFLICT (cnpj_basico) DO UPDATE SET
      tipo=EXCLUDED.tipo, decisores=EXCLUDED.decisores, decisor_top=EXCLUDED.decisor_top,
      situacao_viva=EXCLUDED.situacao_viva, porte=EXCLUDED.porte, qsa=EXCLUDED.qsa, enriched_at=now();
    """
    icp = corp = err = 0
    with httpx.Client(headers={"User-Agent": "wins-agro/decisores"}) as client:
        for i, row in enumerate(todo, 1):
            data, e = fetch_qsa(client, row["cnpj14"])
            time.sleep(0.7)
            situacao = porte = ""
            decisores, qsa_json = [], None
            if data:
                situacao = data.get("descricao_situacao_cadastral", "")
                porte    = data.get("porte", "")
                qsa_json = json.dumps(data.get("qsa") or [], ensure_ascii=False)
                for s in (data.get("qsa") or []):
                    nome = (s.get("nome_socio") or "").strip()
                    qual = (s.get("qualificacao_socio") or "").strip()
                    if nome and is_pessoa(nome) and any(q in qual for q in DECISOR_QUALS):
                        decisores.append((nome, qual))
            tipo = "FAMILIAR/ICP" if decisores else ("CORPORATIVO" if data else "ERRO")
            if tipo == "FAMILIAR/ICP": icp += 1
            elif tipo == "CORPORATIVO": corp += 1
            else: err += 1
            # decisor_top = 1º administrador, senão 1º sócio
            top = next((f"{n} ({q})" for n, q in decisores if "dminist" in q or "Presid" in q or "Diret" in q),
                       (f"{decisores[0][0]} ({decisores[0][1]})" if decisores else None))
            cur.execute(UPSERT, dict(
                cnpj_basico=row["cnpj_basico"], cnpj14=row["cnpj14"], razao=row["razao"],
                uf=row["uf"], municipio=row["municipio"], tipo=tipo,
                decisores="; ".join(f"{n} ({q})" for n, q in decisores) or None,
                decisor_top=top, situacao_viva=situacao or ("erro:"+(e or "")), porte=porte,
                qsa=qsa_json,
            ))
            if i % 25 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)} | ICP {icp} · corp {corp} · erro {err}", file=sys.stderr, flush=True)
    print(f"[OK] gravados {len(todo)} | ICP {icp} · corporativo {corp} · erro {err}", file=sys.stderr, flush=True)

if __name__ == "__main__":
    main()
