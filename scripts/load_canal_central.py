#!/usr/bin/env python3
"""Carrega o CANAL MULTIPLICADOR da decisao de genetica em prospeccao.canal_central.

Objetivo: capturar as pessoas/empresas que tocam a decisao de genetica de uma
fazenda alem do dono -- (a) revendas/representantes/inseminadores das centrais de
IA; (b) tecnicos/avaliadores/julgadores das associacoes de raca.

REALIDADE DAS FONTES (apurada 2026-06-13, ver REPORT):
  - Centrais grandes (CRV, ABS/Pecplan, Alta, Tairana, Semex): NAO publicam diretorio
    publico estruturado de revendas/representantes. Semex tem /representantes mas o
    conteudo e renderizado por JS (mapa), nao raspavel estaticamente. CRV/ABS/Alta
    roteiam via formulario "fale conosco"/loja online. => BLOQUEADO (nao forcar lixo).
  - ABCZ publica DOIS diretorios livres e estruturados, que carregamos aqui:
      1. Colegio de Jurados (corte + leite): avaliadores/julgadores oficiais da
         raca zebu, com nome, profissao, telefone(s), email(s).
         papel='avaliador'
      2. PMGZ Leite - Relacao de Habilitados para Controle Leiteiro: tecnicos
         credenciados pela ABCZ por UF (endpoint AJAX JSON), com nome, cidade, uf,
         email, telefone.  papel='tecnico'
  - ANCP: nao publica lista publica de avaliadores/tecnicos (so PDF de normas CEIP).
    => sem dados.

Roda no container api (tem rede p/ o db e httpx):
  docker cp scripts/load_canal_central.py wins_agro_v1_api_1:/app/load_canal_central.py
  docker exec wins_agro_v1_api_1 python /app/load_canal_central.py
"""
import os, re, sys, time, html, datetime
import httpx
import psycopg2, psycopg2.extras

DB = dict(host=os.getenv("DB_HOST", "db"), port=int(os.getenv("DB_PORT", 5432)),
          dbname=os.getenv("POSTGRES_DB", "wins_agro"), user=os.getenv("POSTGRES_USER", "postgres"),
          password=os.getenv("POSTGRES_PASSWORD", ""))

UA = {"User-Agent": "Mozilla/5.0"}
NOW = datetime.datetime.now(datetime.timezone.utc)

UFS = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA",
       "PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"]

# email/profissao helpers ----------------------------------------------------
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\(?\d{2}\)?[\s.\-]?\d?[\s.\-]?\d{4,5}[\s.\-]?\d{4}")

def norm_phone(raw):
    """Mantem apenas digitos; descarta DDI 55 redundante p/ numeros BR longos."""
    if not raw:
        return None
    d = re.sub(r"\D", "", raw)
    if d.startswith("55") and len(d) >= 12:  # +55 (xx) 9xxxx-xxxx
        d = d[2:]
    return d or None

def fetch(url, method="GET", data=None, tries=4, timeout=90):
    last = None
    for _ in range(tries):
        try:
            if method == "POST":
                return httpx.post(url, data=data, verify=False, follow_redirects=True,
                                  headers={**UA, "X-Requested-With": "XMLHttpRequest"}, timeout=timeout)
            return httpx.get(url, verify=False, follow_redirects=True, headers=UA, timeout=timeout)
        except Exception as e:
            last = e
            time.sleep(2)
    raise last

# ---------------------------------------------------------------------------
# FONTE 1: ABCZ Colegio de Jurados (corte + leite) -> avaliadores
# ---------------------------------------------------------------------------
JURADO_PAGES = {
    "corte": "https://www.abcz.org.br/produtos-e-servicos/area-tecnica/colegio-de-jurados/listagem-dos-jurados/1/jurados-atualizados-corte",
    "leite": "https://www.abcz.org.br/produtos-e-servicos/area-tecnica/colegio-de-jurados/listagem-dos-jurados/5/jurados-atualizados-leite",
}
PROFISSOES = ("VETERIN", "ZOOTEC", "AGRONOM", "ENGENHEIR", "MEDICO", "MÉDICO", "TECNICO", "TÉCNICO")

def parse_jurados(htmltxt):
    i = htmltxt.find("coluna-conteudo")
    seg = htmltxt[i:]
    j = seg.find("coluna-lateral")
    if j > 0:
        seg = seg[:j]
    txt = html.unescape(re.sub(r"<[^>]+>", "\n", seg))
    txt = re.sub(r"[ \t]+", " ", txt)
    lines = [l.strip() for l in txt.split("\n") if l.strip()]
    # quebra por "Data de efetivacao"
    blocks, cur = [], []
    for l in lines:
        cur.append(l)
        if l.lower().startswith("data de efetiva"):
            blocks.append(cur)
            cur = []
    recs = []
    NOISE = {"INÍCIO", "PRODUTOS E SERVIÇOS", "ÁREA TÉCNICA", "COLÉGIO DE JURADOS",
             "LISTAGEM DOS JURADOS"}
    for b in blocks:
        # 1a linha util = nome (uppercase, sem @, sem (), sem breadcrumb)
        nome = None
        prof = None
        emails, phones = [], []
        for l in b:
            up = l.upper().strip()
            if nome is None:
                if (up in NOISE or "JURADOS ATUALIZADOS" in up or "DIV;" in up
                        or "DELAY" in up or "COLUNA-CONTEUDO" in up or "LISTAGEM" in up):
                    continue
                # nome = primeira linha "limpa": maiuscula predominante, sem digito/@
                if "@" not in l and not any(c.isdigit() for c in l) and len(l) > 4:
                    nome = re.sub(r"\s+", " ", l).strip()
                    continue
                else:
                    continue
            # ja temos nome; coletar profissao (1a ocorrencia), emails, phones
            if prof is None and any(p in up for p in PROFISSOES) and "@" not in l:
                prof = re.sub(r"\s+", " ", l).strip()
            emails += EMAIL_RE.findall(l)
            phones += PHONE_RE.findall(l)
        if not nome:
            continue
        recs.append(dict(nome=nome, profissao=prof,
                         email=emails[0].lower() if emails else None,
                         telefone=norm_phone(phones[0]) if phones else None))
    return recs

def load_jurados(cur):
    rows = []
    seen = set()
    for raca, url in JURADO_PAGES.items():
        r = fetch(url)
        if r.status_code != 200:
            print(f"  [jurados/{raca}] HTTP {r.status_code} - pulando")
            continue
        recs = parse_jurados(r.text)
        print(f"  [jurados/{raca}] {len(recs)} registros")
        for rec in recs:
            key = (rec["nome"].upper(), "ABCZ - Colegio de Jurados")
            if key in seen:
                continue
            seen.add(key)
            rows.append((
                rec["nome"], "ABCZ - Colegio de Jurados", "avaliador",
                None, None, rec["telefone"], rec["email"],
                "abcz", url, NOW, rec["profissao"],
            ))
    return rows

# ---------------------------------------------------------------------------
# FONTE 2: ABCZ PMGZ Leite - Controle Leiteiro habilitados (por UF) -> tecnicos
# ---------------------------------------------------------------------------
CL_AJAX = "https://www.abcz.org.br/pmgz/pmgz-leite/controle-leiteiro/relacao-de-habilitados-para-controle-leiteiro-ajax"
CL_PAGE = "https://www.abcz.org.br/pmgz/pmgz-leite/controle-leiteiro/relacao-de-habilitados-para-controle-leiteiro"

def load_controle_leiteiro(cur):
    rows = []
    seen = set()
    for uf in UFS:
        try:
            r = fetch(CL_AJAX, method="POST", data={"estado": uf}, timeout=45)
            d = r.json()
        except Exception as e:
            print(f"  [CL/{uf}] erro {repr(e)[:60]}")
            continue
        itens = d.get("itens", []) if isinstance(d, dict) else []
        for it in itens:
            nome = (it.get("nome") or "").strip()
            if not nome:
                continue
            key = (nome.upper(), it.get("uf"), it.get("cidade"))
            if key in seen:
                continue
            seen.add(key)
            rows.append((
                nome, "ABCZ - Controle Leiteiro PMGZ", "tecnico",
                (it.get("cidade") or "").strip().title() or None,
                (it.get("uf") or "").strip().upper() or None,
                norm_phone(it.get("telefone")),
                (it.get("email") or "").strip().lower() or None,
                "abcz", CL_PAGE, NOW, "Tecnico habilitado Controle Leiteiro",
            ))
        print(f"  [CL/{uf}] {len(itens)} tecnicos")
        time.sleep(0.3)
    return rows

# ---------------------------------------------------------------------------
DDL = """
CREATE TABLE IF NOT EXISTS prospeccao.canal_central (
    id          bigserial PRIMARY KEY,
    nome        text NOT NULL,
    empresa     text,                 -- central / associacao de origem
    papel       text NOT NULL,        -- revenda|representante|inseminador|avaliador|tecnico
    municipio   text,
    uf          text,
    telefone    text,                 -- somente digitos
    email       text,
    profissao   text,
    fonte       text NOT NULL,        -- crv|abs|alta|abcz|ancp|...
    fonte_url   text,
    coletado_em timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE prospeccao.canal_central IS
  'Canal multiplicador: revendas/representantes/inseminadores de centrais de IA e tecnicos/avaliadores de associacoes de raca.';
"""

INSERT = """
INSERT INTO prospeccao.canal_central
  (nome, empresa, papel, municipio, uf, telefone, email, fonte, fonte_url, coletado_em, profissao)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (nome, empresa, papel, COALESCE(uf,''), COALESCE(municipio,'')) DO UPDATE SET
  telefone    = COALESCE(EXCLUDED.telefone, prospeccao.canal_central.telefone),
  email       = COALESCE(EXCLUDED.email, prospeccao.canal_central.email),
  profissao   = COALESCE(EXCLUDED.profissao, prospeccao.canal_central.profissao),
  fonte_url   = EXCLUDED.fonte_url,
  coletado_em = EXCLUDED.coletado_em;
"""

def main():
    conn = psycopg2.connect(**DB); conn.autocommit = True
    cur = conn.cursor()
    cur.execute(DDL)
    # garante UNIQUE com COALESCE via indice (a constraint inline com COALESCE nao e valida)
    cur.execute("""
        DROP INDEX IF EXISTS prospeccao.canal_central_uq;
        CREATE UNIQUE INDEX IF NOT EXISTS canal_central_uq ON prospeccao.canal_central
          (nome, empresa, papel, (COALESCE(uf,'')), (COALESCE(municipio,'')));
    """)
    cur.execute("GRANT SELECT ON prospeccao.canal_central TO wins_app;")
    cur.execute("GRANT USAGE, SELECT ON SEQUENCE prospeccao.canal_central_id_seq TO wins_app;")

    print("== FONTE 1: ABCZ Colegio de Jurados (avaliadores) ==")
    jur = load_jurados(cur)
    print("== FONTE 2: ABCZ Controle Leiteiro PMGZ (tecnicos) ==")
    cl = load_controle_leiteiro(cur)

    all_rows = jur + cl
    print(f"\nInserindo {len(all_rows)} linhas ({len(jur)} avaliadores + {len(cl)} tecnicos)...")
    psycopg2.extras.execute_batch(cur, INSERT, all_rows, page_size=200)

    cur.execute("SELECT papel, fonte, count(*) FROM prospeccao.canal_central GROUP BY 1,2 ORDER BY 1,2;")
    print("\n== contagem por papel/fonte ==")
    for papel, fonte, n in cur.fetchall():
        print(f"  {papel:12s} {fonte:8s} {n}")
    cur.execute("SELECT count(*) FROM prospeccao.canal_central;")
    print("TOTAL:", cur.fetchone()[0])
    cur.execute("SELECT count(*) FILTER (WHERE telefone IS NOT NULL), count(*) FILTER (WHERE email IS NOT NULL) FROM prospeccao.canal_central;")
    tel, em = cur.fetchone()
    print(f"  com telefone: {tel}   com email: {em}")
    conn.close()

if __name__ == "__main__":
    main()
