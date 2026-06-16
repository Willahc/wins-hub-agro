#!/usr/bin/env python3
"""
enrich_holdings_blindspot.py — enriquece o "ponto cego das holdings".

Lê prospeccao.holding_blind_spot (cnpj_basico de empresas SEM CNAE agro mas
controladas por sócios que também estão na nossa base pecuária), consulta a
BrasilAPI no estabelecimento matriz, classifica (HOLDING / AGRO_OUTRO / OUTRO)
e, para HOLDING e AGRO_OUTRO, faz UPSERT em prospeccao.cnpj_rural (cadastro) e
prospeccao.lead_decisor (decisor/QSA) — mesmo formato da empresa LAMÃO inserida
à mão, mas com tipo='HOLDING/SOCIO' para distinguir esse vetor de descoberta.

Conexão: psycopg2 -> host="db" (rodar DENTRO do container wins_agro_v1-db-1 NÃO;
rodamos via `docker compose exec` no serviço que tem rede com o db, OU dentro do
container app). Mesmo mecanismo de enrich_extra_brasilapi.py: psycopg2.connect com
host="db" e senha em POSTGRES_PASSWORD. Resumível e com rate limit educado (~0.7s
entre chamadas + backoff em 429), igual aos scripts existentes.

Para rodar (quando a tabela estiver populada):
  docker compose exec -T -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" app \
      python3 scripts/enrich_holdings_blindspot.py
"""
import os, re, sys, time, json
import psycopg2, psycopg2.extras, httpx

DB = dict(host="db", dbname="wins_agro", user="postgres",
          password=os.environ['POSTGRES_PASSWORD'])

# qualificações que indicam decisor (igual enrich_extra_brasilapi.py)
QUALS = ("Administrador", "Sócio-Administrador", "Sócio", "Presidente",
         "Diretor", "Titular", "Proprietário")
# marcadores de pessoa jurídica (não é pessoa-decisor)
HOLD = (" S/A", " S.A", "PARTICIPAC", "HOLDING", "EMPREEND", " FUNDO", " LTDA", " EIRELI")


def pessoa(n):
    u = (n or "").upper()
    return not any(h in u for h in HOLD)


# ---------- dígito verificador / cnpj14 ----------
def calc_dv(cnpj12):
    """Calcula os 2 dígitos verificadores a partir dos 12 primeiros dígitos."""
    def dv(base):
        pesos = list(range(2, 10)) * 2
        s = sum(int(d) * p for d, p in zip(reversed(base), pesos))
        r = s % 11
        return '0' if r < 2 else str(11 - r)
    d1 = dv(cnpj12)
    d2 = dv(cnpj12 + d1)
    return d1 + d2


def matriz_cnpj14(cnpj_basico):
    base = re.sub(r'\D', '', str(cnpj_basico)).zfill(8)[:8]
    cnpj12 = base + '0001'
    return cnpj12 + calc_dv(cnpj12)


# ---------- BrasilAPI (retries + backoff em 429) ----------
def fetch_cnpj(client, cnpj14):
    for a in range(4):
        try:
            r = client.get(f"https://brasilapi.com.br/api/cnpj/v1/{cnpj14}", timeout=20)
            if r.status_code == 429:
                time.sleep(4 + a * 4)
                continue
            if r.status_code != 200:
                return None
            return r.json()
        except Exception:
            time.sleep(2)
    return None


# ---------- classificação ----------
def cnae_str(cnae_fiscal):
    """Normaliza cnae_fiscal (int 6810201) para string de 7 dígitos '6810201'."""
    if cnae_fiscal is None:
        return ""
    return re.sub(r'\D', '', str(cnae_fiscal)).zfill(7)


def cnae_fmt(cnae_fiscal):
    """7 dígitos -> 'NNNN-N/NN' (formato cnpj_rural, ex. 6810-2/01)."""
    s = cnae_str(cnae_fiscal)
    if len(s) != 7:
        return s
    return f"{s[:4]}-{s[4]}/{s[5:]}"


def classify(cnae_fiscal):
    s = cnae_str(cnae_fiscal)
    # HOLDING: holding/imobiliária/participações (6810, 6462, 6463 e demais 64xx)
    if s[:4] in ("6810", "6462", "6463") or s[:2] == "64":
        return "HOLDING"
    # AGRO que escapou do filtro original (agricultura 01, pecuária 02->na CNAE BR
    # agro é 01/02/03: agricultura/pecuária, produção florestal, pesca/aquicultura)
    if s[:2] in ("01", "02", "03"):
        return "AGRO_OUTRO"
    return "OUTRO"


# ---------- montagem dos registros ----------
def secundarios_text(cnaes_sec):
    """cnaes_secundarios (lista de {codigo, descricao}) -> texto curto p/ cnpj_rural.text."""
    parts = []
    for c in (cnaes_sec or []):
        desc = (c.get("descricao") or "").strip()
        cod = c.get("codigo")
        if desc:
            parts.append(desc)
        elif cod:
            parts.append(str(cod))
    return "; ".join(parts) if parts else None


def build_qsa_json(qsa):
    """QSA da BrasilAPI -> jsonb no formato da Lamão: {nome,papel,entrada,faixa_etaria}."""
    out = []
    for s in (qsa or []):
        out.append({
            "nome": (s.get("nome_socio") or "").strip(),
            "papel": (s.get("qualificacao_socio") or "").strip(),
            "entrada": s.get("data_entrada_sociedade"),
            "faixa_etaria": (s.get("faixa_etaria") or "").strip() or None,
        })
    return out


def build_decisores(qsa):
    """Lista 'Nome (Qualif)' só de pessoas físicas com qualificação de decisor."""
    decis = []
    for s in (qsa or []):
        nm = (s.get("nome_socio") or "").strip()
        ql = (s.get("qualificacao_socio") or "").strip()
        if nm and pessoa(nm) and any(q in ql for q in QUALS):
            decis.append(f"{nm} ({ql})")
    top = next((x for x in decis if "dminist" in x or "Presid" in x or "Diret" in x),
               decis[0] if decis else None)
    decis_str = " | ".join(decis) if decis else None
    top_nome = top.rsplit(" (", 1)[0] if top else None
    return decis_str, top_nome


def upsert_cnpj_rural(cur, d, cnpj14, cnae_fiscal):
    cnaes_sec = secundarios_text(d.get("cnaes_secundarios"))
    cap = d.get("capital_social")
    try:
        cap = float(cap) if cap is not None else None
    except (TypeError, ValueError):
        cap = None
    cur.execute("""
        INSERT INTO prospeccao.cnpj_rural
          (cnpj, razao_social, nome_fantasia, natureza_juridica, cnae_principal,
           cnae_secundarios, capital_social, porte, situacao, data_abertura,
           cep, logradouro, numero, complemento, bairro, municipio, uf,
           telefone, email, coletado_em)
        VALUES
          (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())
        ON CONFLICT (cnpj) DO UPDATE SET
           razao_social=EXCLUDED.razao_social,
           nome_fantasia=EXCLUDED.nome_fantasia,
           natureza_juridica=EXCLUDED.natureza_juridica,
           cnae_principal=EXCLUDED.cnae_principal,
           cnae_secundarios=EXCLUDED.cnae_secundarios,
           capital_social=EXCLUDED.capital_social,
           porte=EXCLUDED.porte,
           situacao=EXCLUDED.situacao,
           data_abertura=EXCLUDED.data_abertura,
           cep=EXCLUDED.cep, logradouro=EXCLUDED.logradouro, numero=EXCLUDED.numero,
           complemento=EXCLUDED.complemento, bairro=EXCLUDED.bairro,
           municipio=EXCLUDED.municipio, uf=EXCLUDED.uf,
           telefone=EXCLUDED.telefone, email=EXCLUDED.email,
           coletado_em=now()
    """, (
        cnpj14,
        (d.get("razao_social") or None),
        (d.get("nome_fantasia") or None) or None,
        # natureza_juridica é varchar(10): guarda CÓDIGO, não descrição
        (str(d.get("codigo_natureza_juridica")) if d.get("codigo_natureza_juridica") is not None else None),
        # cnae_principal varchar(10): código formatado 'NNNN-N/NN'
        (cnae_fmt(cnae_fiscal) or None),
        cnaes_sec,
        cap,
        # porte varchar(10): API devolve 'MICRO EMPRESA'(12)/'PEQUENO PORTE' etc -> trunca de fato
        ((d.get("porte") or None) and d["porte"][:10]) or None,
        # situacao varchar(20)
        ((d.get("descricao_situacao_cadastral") or None) and d["descricao_situacao_cadastral"][:20]) or None,
        (d.get("data_inicio_atividade") or None),
        (d.get("cep") or None),
        (d.get("logradouro") or None),
        (d.get("numero") or None),
        ((d.get("complemento") or "").strip() or None),
        (d.get("bairro") or None),
        (d.get("municipio") or None),
        (d.get("uf") or None),
        (d.get("ddd_telefone_1") or None),
        (d.get("email") or None),
    ))


def upsert_lead_decisor(cur, d, cnpj_basico, cnpj14):
    decis_str, top_nome = build_decisores(d.get("qsa"))
    qsa_json = build_qsa_json(d.get("qsa"))
    cur.execute("""
        INSERT INTO prospeccao.lead_decisor
          (cnpj_basico, cnpj14, razao, uf, municipio, tipo, decisores,
           decisor_top, situacao_viva, porte, qsa, enriched_at)
        VALUES
          (%s,%s,%s,%s,%s,'HOLDING/SOCIO',%s,%s,%s,%s,%s,now())
        ON CONFLICT (cnpj_basico) DO UPDATE SET
           cnpj14=EXCLUDED.cnpj14,
           razao=EXCLUDED.razao,
           uf=EXCLUDED.uf,
           municipio=EXCLUDED.municipio,
           tipo='HOLDING/SOCIO',
           decisores=EXCLUDED.decisores,
           decisor_top=EXCLUDED.decisor_top,
           situacao_viva=EXCLUDED.situacao_viva,
           porte=EXCLUDED.porte,
           qsa=EXCLUDED.qsa,
           enriched_at=now()
    """, (
        str(cnpj_basico),
        cnpj14,
        (d.get("razao_social") or None),
        (d.get("uf") or None),
        (d.get("municipio") or None),
        decis_str,
        top_nome,
        (d.get("descricao_situacao_cadastral") or None),
        (d.get("porte") or None),
        psycopg2.extras.Json(qsa_json),
    ))


def main():
    conn = psycopg2.connect(**DB)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # progresso resumível: colunas de marcação na própria holding_blind_spot
    cur.execute("ALTER TABLE prospeccao.holding_blind_spot "
                "ADD COLUMN IF NOT EXISTS classificacao varchar(12);")
    cur.execute("ALTER TABLE prospeccao.holding_blind_spot "
                "ADD COLUMN IF NOT EXISTS enriquecido_em timestamptz;")

    # 1) cnpj_basico ainda não enriquecidos (distinct: a tabela pode ter 1 linha por sócio)
    cur.execute("""
        SELECT DISTINCT cnpj_basico
          FROM prospeccao.holding_blind_spot
         WHERE enriquecido_em IS NULL
         ORDER BY cnpj_basico
    """)
    rows = cur.fetchall()
    print(f"[holdings blind-spot: {len(rows)} cnpj_basico p/ enriquecer]",
          file=sys.stderr, flush=True)

    stats = {"HOLDING": 0, "AGRO_OUTRO": 0, "OUTRO": 0, "erro": 0}
    with httpx.Client(headers={"User-Agent": "wins-agro/holdings"}) as cl:
        for i, r in enumerate(rows, 1):
            cb = re.sub(r'\D', '', str(r["cnpj_basico"])).zfill(8)
            cnpj14 = matriz_cnpj14(cb)
            d = fetch_cnpj(cl, cnpj14)
            time.sleep(0.7)  # rate limit educado (~1.4 req/s, < 3 req/s do plano grátis)

            if not d:
                cur.execute("""UPDATE prospeccao.holding_blind_spot
                                  SET classificacao='ERRO', enriquecido_em=now()
                                WHERE cnpj_basico=%s""", (r["cnpj_basico"],))
                stats["erro"] += 1
                continue

            cnae_fiscal = d.get("cnae_fiscal")
            klass = classify(cnae_fiscal)
            stats[klass] += 1

            # 3+4) só HOLDING e AGRO_OUTRO entram no cadastro/decisor
            if klass in ("HOLDING", "AGRO_OUTRO"):
                upsert_cnpj_rural(cur, d, cnpj14, cnae_fiscal)
                upsert_lead_decisor(cur, d, cb, cnpj14)

            cur.execute("""UPDATE prospeccao.holding_blind_spot
                              SET classificacao=%s, enriquecido_em=now()
                            WHERE cnpj_basico=%s""", (klass, r["cnpj_basico"]))

            if i % 25 == 0:
                print(f"  {i}/{len(rows)} | {stats}", file=sys.stderr, flush=True)

    print(f"\n[FIM] {len(rows)} processados | {stats}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
