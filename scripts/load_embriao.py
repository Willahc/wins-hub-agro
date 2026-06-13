#!/usr/bin/env python3
"""
load_embriao.py — Carrega o primeiro lote REAL de ofertas de embrião (CRV Brasil)
em mercado.doadora + mercado.oferta_embriao.

Fonte: /tmp/embrioes_crv.json (gerado por recon_embriao.py).
Roda no HOST (psql via docker exec). Idempotente (upsert por external_id / nome).

Parsing do nome CRV, ex:
  "DOADORA NELORE MARA MÓVEIS X KOCHI - (EMBRIÃO PREMIUM) P.O"
  -> doadora="MARA MÓVEIS", touro="KOCHI", raca=Nelore, categoria=PREMIUM
"""
import json, re, subprocess, unicodedata, sys

JSON_HOST = "/root/wins_agro_v1/scripts/embrioes_crv.json"
FONTE = "crv_loja"

# categoria CRV (do JSON) -> sigla de raça em catalogo.raca
RACA_BY_CAT = {
    "NELORE": "NEL",
    "HOLAND": "HOL",          # Holandês Preto e Branco
    "JERSEY": "JER",
    "GIR LEITEIRO": "GIRL",
    "GIROLANDO": "GIRO",
    "SENEPOL": "SEN",
}

PALAVRAS_DOADORA = ("DOADORA",)


def psql(sql):
    r = subprocess.run(
        ["docker", "exec", "-i", "wins_agro_v1_db_1", "psql", "-U", "postgres",
         "-d", "wins_agro", "-q", "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True,
    )
    if r.returncode:
        sys.stderr.write(r.stderr)
        raise SystemExit(f"psql falhou: {sql[:120]}")
    return r.stdout.strip()


def q(s):
    return "'" + (s or "").replace("'", "''") + "'" if s is not None else "NULL"


def norm(s):
    if not s:
        return None
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).upper().strip()


def raca_id_for(category):
    cu = (category or "").upper()
    for key, sig in RACA_BY_CAT.items():
        if key in cu:
            return RACA[sig]
    return None


def parse_name(nome):
    """Devolve (doadora, touro, categoria)."""
    n = nome.strip()
    # categoria entre parênteses: (EMBRIÃO PREMIUM) / (EMBRIÃO STANDART)
    catm = re.search(r"\(EMBRI[ÃA]O\s+([A-ZÀ-Ú]+)\)", n, re.I)
    categoria = norm(catm.group(1)) if catm else None
    if categoria in ("STANDART",):
        categoria = "STANDARD"
    # corta tudo a partir do "- (EMBRIÃO"
    core = re.split(r"\s*-\s*\(EMBRI[ÃA]O", n, flags=re.I)[0]
    # remove prefixo DOADORA e a sigla de raça inicial
    core = re.sub(r"^\s*DOADORA\s+", "", core, flags=re.I)
    # separa doadora X touro (X isolado, com ou sem 'TOURO')
    parts = re.split(r"\s+[xX]\s+", core, maxsplit=1)
    doadora_raw = parts[0].strip() if parts else core
    touro_raw = parts[1].strip() if len(parts) > 1 else None
    # tira sigla de raça do começo do nome da doadora (NELORE/HOLANDÊS/JERSEY/...)
    # norm() preserva comprimento (1:1 por char), então len(pref) bate no original.
    for pref in ("HOLANDES PRETO E BRANCO", "GIR LEITEIRO", "GIROLANDO",
                 "NELORE", "JERSEY", "SENEPOL", "HOLANDES"):
        if norm(doadora_raw).startswith(pref):
            doadora_raw = doadora_raw[len(pref):].strip()
            break
    # tira "TOURO " do começo do touro
    if touro_raw:
        touro_raw = re.sub(r"^\s*TOURO\s+", "", touro_raw, flags=re.I).strip()
    doadora_raw = doadora_raw or None
    return doadora_raw, touro_raw, categoria


def match_reprodutor(nome, raca_id, sexo):
    """Tenta achar reprodutor por nome normalizado + raça (+ sexo)."""
    if not nome or not raca_id:
        return None
    nn = norm(nome)
    sql = (
        "SELECT id FROM mercado.reprodutor "
        f"WHERE raca_id={raca_id} AND upper(translate(nome,"
        "'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ','AAAAAEEEEIIIIOOOOOUUUUC'))="
        f"{q(nn)} "
        + (f"AND sexo='{sexo}' " if sexo else "")
        + "LIMIT 1"
    )
    out = psql(sql)
    return int(out) if out else None


def upsert_doadora(nome, raca_id, url):
    nn = norm(nome)
    rep = match_reprodutor(nome, raca_id, "F")
    sql = (
        "INSERT INTO mercado.doadora (reprodutor_id,nome,nome_norm,raca_id,"
        "fonte_referencia,fonte_url) VALUES ("
        f"{rep if rep else 'NULL'},{q(nome)},{q(nn)},{raca_id if raca_id else 'NULL'},"
        f"{q(FONTE)},{q(url)}) "
        "ON CONFLICT (nome_norm,raca_id) WHERE nome_norm IS NOT NULL "
        "DO UPDATE SET fonte_url=EXCLUDED.fonte_url, "
        "reprodutor_id=COALESCE(mercado.doadora.reprodutor_id,EXCLUDED.reprodutor_id) "
        "RETURNING id"
    )
    return int(psql(sql).splitlines()[0])


def upsert_oferta(rec, doadora_id, rep_id, raca_id, doadora_nome, touro_nome, categoria):
    preco = rec.get("sell_price") or rec.get("price")
    sql = (
        "INSERT INTO mercado.oferta_embriao "
        "(doadora_id,doadora_nome,reprodutor_id,touro_nome,raca_id,tipo,"
        "categoria,preco_brl,preco_por,fonte_referencia,fonte_url,external_id) "
        "VALUES ("
        f"{doadora_id if doadora_id else 'NULL'},{q(doadora_nome)},"
        f"{rep_id if rep_id else 'NULL'},{q(touro_nome)},"
        f"{raca_id if raca_id else 'NULL'},'FIV',{q(categoria)},"
        f"{preco if preco else 'NULL'},'embriao',{q(FONTE)},"
        f"{q(rec.get('url'))},{q(str(rec.get('id_product')))}) "
        "ON CONFLICT (fonte_referencia,external_id) WHERE external_id IS NOT NULL "
        "DO UPDATE SET preco_brl=EXCLUDED.preco_brl, doadora_id=EXCLUDED.doadora_id, "
        "reprodutor_id=EXCLUDED.reprodutor_id, coletado_em=now() "
        "RETURNING id"
    )
    return int(psql(sql).splitlines()[0])


def main():
    global RACA
    # carrega siglas -> id
    RACA = {}
    for line in psql("SELECT sigla,id FROM catalogo.raca").splitlines():
        sig, i = line.split("\t")
        RACA[sig] = int(i)

    data = json.load(open(JSON_HOST, encoding="utf-8"))
    n_of = n_do = matched_touro = matched_doadora = 0
    for rec in data:
        raca_id = raca_id_for(rec.get("category"))
        doadora_raw, touro_raw, categoria = parse_name(rec["nome"])
        # doadora
        doadora_id = None
        if doadora_raw:
            doadora_id = upsert_doadora(doadora_raw, raca_id, rec.get("url"))
            n_do += 1
        # touro match
        rep_id = match_reprodutor(touro_raw, raca_id, "M") if touro_raw else None
        if rep_id:
            matched_touro += 1
        # doadora match (via reprodutor F)
        if doadora_raw and match_reprodutor(doadora_raw, raca_id, "F"):
            matched_doadora += 1
        upsert_oferta(rec, doadora_id, rep_id, raca_id,
                      doadora_raw, touro_raw, categoria)
        n_of += 1
    print(f"Ofertas upsertadas: {n_of}")
    print(f"Doadoras upsertadas (linhas processadas): {n_do}")
    print(f"Touros casados em reprodutor: {matched_touro}")
    print(f"Doadoras casadas em reprodutor(F): {matched_doadora}")


if __name__ == "__main__":
    main()
