#!/usr/bin/env python3
"""Exporta o top-3 por UF (tabela prospeccao.prospect_top3_uf, score ja calculado no banco)
para CSV + resumo MD. Enriquece cada fazenda com 1 busca Serper p/ detectar uso de
software de gestao/genetica (JetBov, Prodap, Ideagri, etc). Idempotente: sobrescreve os arquivos.

Roda no host: le .env (DB em 127.0.0.1:5432 + SERPER_API_KEY).
"""
import os, re, csv, sys, time, pathlib
import psycopg2, psycopg2.extras, httpx

ROOT = pathlib.Path(__file__).resolve().parent.parent
EXPORTS = ROOT / "exports"
EXPORTS.mkdir(exist_ok=True)

# ---- .env ----
env = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()

SERPER_KEY = env.get("SERPER_API_KEY", "").strip()
DB = dict(host="127.0.0.1", port=int(env.get("DB_PORT", 5432)),
          dbname=env.get("POSTGRES_DB", "wins_agro"),
          user=env.get("POSTGRES_USER", "postgres"),
          password=env.get("POSTGRES_PASSWORD", ""))

UF_NOME = {"MS":"Mato Grosso do Sul","GO":"Goiás","MT":"Mato Grosso","TO":"Tocantins",
           "PA":"Pará","BA":"Bahia","MG":"Minas Gerais","RO":"Rondônia","MA":"Maranhão",
           "PI":"Piauí","PR":"Paraná","SP":"São Paulo"}

# Softwares/programas de gestao de rebanho e genetica usados no agro BR
FERRAMENTAS = {
    "jetbov":"JetBov","prodap":"Prodap","ideagri":"Ideagri","multibov":"MultiBovinos",
    "multbov":"MultBovinos","geneplus":"Geneplus","conception":"Conception",
    "bovcontrol":"BovControl","bovexo":"BovExo","datagro":"Datagro","agriness":"Agriness",
    "aegro":"Aegro","ruralpro":"RuralPro","pecuaria web":"Pecuária Web","pecware":"Pecware",
    "smartfarmer":"SmartFarmer","conecta boi":"Conecta Boi","gestor rural":"GestorRural",
    "ancp":"ANCP (avaliação genética)","pmgrn":"PMGRN/Nelore Brasil","cdn genética":"CDN",
    "nelore brasil":"Nelore Brasil","precoce ms":"Precoce MS",
}


def norm_whats(raw):
    """Retorna os 11 digitos (DDD + 9 + numero) ou None."""
    d = re.sub(r"\D", "", raw or "")
    if d.startswith("55") and len(d) > 11:   # DDI Brasil
        d = d[2:]
    if len(d) == 10:                         # DDD + 8 digitos -> insere o 9
        d = d[:2] + "9" + d[2:]
    return d if len(d) == 11 else None


def fmt_whats(raw):
    d = norm_whats(raw)
    return f"({d[:2]}) {d[2:7]}-{d[7:]}" if d else (raw or "")


def wame(raw):
    """Numero p/ wa.me (55 + DDD + numero)."""
    d = norm_whats(raw)
    return ("55" + d) if d else ""


def split_decisor(decisor):
    """'NOME (Cargo)' -> (nome, cargo)"""
    if not decisor:
        return "", ""
    m = re.match(r"^(.*?)\s*\(([^)]*)\)\s*$", decisor.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return decisor.strip(), ""


def clean_operador(op, decisor_nome):
    if not op:
        return ""
    nome = re.sub(r"\s*\([^)]*\)\s*$", "", op).strip()   # tira faixa etaria "(31-40)"
    if nome.upper() == (decisor_nome or "").upper():
        return ""                                        # mesmo que o decisor -> nao repete
    return nome


def serper(q):
    r = httpx.post("https://google.serper.dev/search",
                   headers={"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"},
                   json={"q": q, "gl": "br", "hl": "pt", "num": 10}, timeout=25)
    r.raise_for_status()
    return r.json()


def detecta_ferramenta(razao, nome_fazenda, municipio, uf):
    """1 busca Serper. Retorna (rotulo, ferramenta_ou_None)."""
    if not SERPER_KEY:
        return "sem busca (sem chave Serper)", None
    nome = re.sub(r"\b(LTDA|S/?A|EIRELI|ME|EPP|AGROPECUARIA|FAZENDA)\b", "",
                  razao or nome_fazenda, flags=re.I).strip() or (nome_fazenda or razao)
    q = f'"{razao}" {municipio} {uf} software gestão rebanho genética IATF'
    try:
        data = serper(q)
    except Exception as e:
        return f"busca falhou ({type(e).__name__})", None
    blob = " ".join([
        " ".join(o.get("title", "") + " " + o.get("snippet", "") for o in data.get("organic", [])),
        str(data.get("knowledgeGraph", {})),
        " ".join(o.get("title", "") for o in data.get("relatedSearches", []) if isinstance(o, dict)),
    ]).lower()
    for chave, label in FERRAMENTAS.items():
        if chave in blob:
            return f"já usa ferramenta: {label}", label
    return "sem ferramenta identificada", None


def observacao(r, tech_label):
    sig = []
    matriz = r["matrizes_municipio"]
    if r["sinal_genetico"] == "alta":
        t = f"sinal genético ALTO" + (f" ({r['touros_nelore']} touros no município)" if r["touros_nelore"] else "")
        sig.append(t)
    elif r["sinal_genetico"] in ("media", "baixa"):
        sig.append(f"sinal genético {r['sinal_genetico']}")
    if r["deserto_vet"]:
        sig.append(f"deserto vet" + (f" com {matriz/1000:.0f}k matrizes" if matriz else ""))
    elif matriz and matriz >= 50000:
        sig.append(f"{matriz/1000:.0f}k matrizes no município")
    if r["operador_nome"]:
        sig.append(f"operador identificado: {r['operador_nome'].title()}")
    if r["capital_mi"] and r["capital_mi"] >= 20:
        sig.append(f"operação de porte (R$ {r['capital_mi']:.0f} mi capital)")
    if r["whats_alta_conf"] is True:
        sig.append("WhatsApp alta confiança")
    sig.append(tech_label)
    return "; ".join(sig)


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT uf, rank_uf, municipio, nome_fazenda, razao, cnpj_completo,
               decisor, operador_jovem, whatsapp, whats_alta_conf, email_hunter, email_verif,
               instagram, followers, capital_mi, sinal_genetico, touros_nelore,
               matrizes_municipio, deserto_vet, tem_canal, score_fit
        FROM prospeccao.prospect_top3_uf ORDER BY uf, rank_uf;
    """)
    rows = cur.fetchall()
    print(f"[{len(rows)} fazendas] enriquecendo via Serper (1 busca/fazenda)...", file=sys.stderr)

    out = []
    for i, r in enumerate(rows, 1):
        dec_nome, dec_cargo = split_decisor(r["decisor"])
        op_nome = clean_operador(r["operador_jovem"], dec_nome)
        r = dict(r)
        r["operador_nome"] = op_nome
        tech_label, tech_ferr = detecta_ferramenta(r["razao"], r["nome_fazenda"], r["municipio"], r["uf"])
        rec = {
            "uf": r["uf"],
            "municipio": r["municipio"],
            "fazenda": r["nome_fazenda"],
            "cnpj": r["cnpj_completo"],
            "decisor_nome": dec_nome,
            "decisor_cargo": dec_cargo,
            "operador_nome": op_nome,
            "whatsapp": fmt_whats(r["whatsapp"]),
            "email_hunter": r["email_hunter"] or "",
            "email_verif": r["email_verif"] or "",
            "instagram": r["instagram"] or "",
            "capital_social": int(round((r["capital_mi"] or 0) * 1_000_000)),
            "sinal_genetico": r["sinal_genetico"],
            "matrizes_municipio": r["matrizes_municipio"] or "",
            "deserto_vet": "sim" if r["deserto_vet"] else "não",
            "score_fit": r["score_fit"],
            "observacao": observacao(r, tech_label),
            "_rank": r["rank_uf"],
            "_uf_nome": UF_NOME.get(r["uf"], r["uf"]),
            "_whatsapp_raw": wame(r["whatsapp"]),
            "_ferramenta": tech_ferr or "",
            "_deserto_bool": bool(r["deserto_vet"]),
        }
        out.append(rec)
        print(f"  {i:>2}/{len(rows)} {r['uf']} {r['nome_fazenda'][:28]:<28} score={r['score_fit']} -> {tech_label}", file=sys.stderr)
        time.sleep(0.4)

    # ---- persiste no banco (fonte unica p/ o Hub) — idempotente ----
    cur.execute("DROP TABLE IF EXISTS prospeccao.prospect_top3_final;")
    cur.execute("""
        CREATE TABLE prospeccao.prospect_top3_final(
            uf varchar(2), uf_nome text, rank_uf int, municipio text, fazenda text, cnpj text,
            decisor_nome text, decisor_cargo text, operador_nome text,
            whatsapp text, whatsapp_wame text, email_hunter text, email_verif text, instagram text,
            capital_social bigint, sinal_genetico text, matrizes_municipio bigint,
            deserto_vet boolean, score_fit int, ferramenta text, observacao text,
            gerado_em timestamptz DEFAULT now()
        );""")
    for rec in out:
        cur.execute("""
            INSERT INTO prospeccao.prospect_top3_final
            (uf,uf_nome,rank_uf,municipio,fazenda,cnpj,decisor_nome,decisor_cargo,operador_nome,
             whatsapp,whatsapp_wame,email_hunter,email_verif,instagram,capital_social,sinal_genetico,
             matrizes_municipio,deserto_vet,score_fit,ferramenta,observacao)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (rec["uf"], rec["_uf_nome"], rec["_rank"], rec["municipio"], rec["fazenda"], rec["cnpj"],
             rec["decisor_nome"], rec["decisor_cargo"], rec["operador_nome"],
             rec["whatsapp"], rec["_whatsapp_raw"], rec["email_hunter"], rec["email_verif"], rec["instagram"],
             rec["capital_social"], rec["sinal_genetico"],
             (rec["matrizes_municipio"] or None), rec["_deserto_bool"], rec["score_fit"],
             rec["_ferramenta"], rec["observacao"]))
    conn.commit()
    print(f"[banco] prospeccao.prospect_top3_final <- {len(out)} linhas", file=sys.stderr)

    # ---- CSV ----
    cols = ["uf","municipio","fazenda","cnpj","decisor_nome","decisor_cargo","operador_nome",
            "whatsapp","email_hunter","instagram","capital_social","sinal_genetico",
            "matrizes_municipio","deserto_vet","score_fit","observacao"]
    csv_path = EXPORTS / "prospects_top3_por_uf.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for rec in out:
            w.writerow(rec)

    # ---- MD ----
    md = ["# Top 3 prospects por estado — WiNS Hub Agro",
          "",
          f"WhatsApp verificado no banco (filtro duro) · score de fit calculado no banco · {len(out)} contatos.",
          ""]
    for uf in ["MS","GO","MT","TO","PA","BA","MG","RO","MA","PI","PR","SP"]:
        grp = [r for r in out if r["uf"] == uf]
        if not grp:
            continue
        md.append(f"## {uf} — {UF_NOME.get(uf, uf)}")
        md.append("")
        for r in sorted(grp, key=lambda x: x["_rank"]):
            md.append(f"### {r['_rank']}. {r['fazenda']} — {r['municipio']}")
            cargo = f" ({r['decisor_cargo']})" if r["decisor_cargo"] else ""
            md.append(f"- **Decisor:** {r['decisor_nome']}{cargo}")
            if r["operador_nome"]:
                md.append(f"- **Operador:** {r['operador_nome'].title()}")
            md.append(f"- **WhatsApp:** {r['whatsapp']}")
            if r["email_hunter"]:
                md.append(f"- **E-mail (Hunter):** {r['email_hunter']}")
            if r["instagram"]:
                md.append(f"- **Instagram:** {r['instagram']}")
            md.append(f"- **CNPJ:** {r['cnpj']}")
            md.append(f"- **Score:** {r['score_fit']}/100")
            md.append(f"- **Por que é top:** {r['observacao']}")
            md.append("")
        md.append("")
    md_path = EXPORTS / "prospects_top3_por_uf_resumo.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(f"\nOK -> {csv_path}\nOK -> {md_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
