#!/usr/bin/env python3
"""Cruza os prospects de corte (Receita) com o CATÁLOGO GENÉTICO (mercado.reprodutor.fazenda_origem):
quem JÁ produz touro registrado é, por definição, quem investe em genética de elite = cliente ideal
da Monte Sião. Sinal de compra mais forte do dado, e é só nosso (nenhum Apollo/Speedio tem).

Casamento por núcleo de nome normalizado, separando distintivo (alta) de genérico (baixa), e
marcando se a fazenda produz NELORE (raça 1) — o que mais importa p/ Monte Sião.
Roda: docker exec wins_agro_v1_api_1 python /app/match_genetica.py
"""
import os, re, sys, unicodedata
import psycopg2, psycopg2.extras

DB = dict(host=os.getenv("DB_HOST","db"), port=int(os.getenv("DB_PORT",5432)),
          dbname=os.getenv("POSTGRES_DB","wins_agro"), user=os.getenv("POSTGRES_USER","postgres"),
          password=os.getenv("POSTGRES_PASSWORD",""))

STOP = {"FAZENDA","FAZ","SITIO","CABANHA","HARAS","AGROPECUARIA","AGROPEC","AGRO","PECUARIA",
        "AGRONEGOCIOS","AGRONEGOCIO","LTDA","EIRELI","EPP","ME","SA","S","A","PARTICIPACOES",
        "PARTICIPACAO","EMPREENDIMENTOS","EMPREENDIMENTO","RURAL","GRUPO","CIA","COMPANHIA",
        "COMERCIO","COM","REPRESENTACOES","REPRES","ADMINISTRADORA","BENS","INVESTIMENTOS",
        "E","DA","DE","DO","DAS","DOS","DI","DEL","SERVICOS","CONFINAMENTO"}
# núcleos genéricos demais -> match de baixa confiança (santo/topônimo comum)
GENERIC = {"SAO JOSE","SANTA MARIA","BOA VISTA","SANTO ANTONIO","SAO SEBASTIAO","SANTA HELENA",
           "SAO GERALDO","SANTA MARTA","SAO LUIZ","SAO LUIS","SAO FRANCISCO","SANTA RITA",
           "SANTA FE","BELA VISTA","TERRA BOA","SANTA CRUZ","SAO PEDRO","SAO JOAO","SANTA LUZIA",
           "SANTA TEREZINHA","SANTA CLARA","SANTA ROSA","SAO MIGUEL","NOSSA SENHORA","SANTA INES",
           "ESPERANCA","NOVA ESPERANCA","PROGRESSO","SAO BENEDITO","SANTA ISABEL","SAO JORGE",
           "DOIS IRMAOS","SANTA LUCIA","SANTO ANTONIO DO","RANCHO ALEGRE","SANTA BARBARA",
           "AGUA LIMPA","SANTA TEREZA","TRES IRMAOS","SAO CARLOS","SAO PAULO","SANTA VITORIA",
           "VISTA ALEGRE","SANTA MONICA","CANAA","MUNDO NOVO","BURITI","PRIMAVERA"}

def norm(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii","ignore").decode().upper()
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    toks = [t for t in s.split() if t not in STOP and len(t) > 1]
    return " ".join(toks).strip()

def main():
    conn = psycopg2.connect(**DB); conn.autocommit = True
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # 1) índice: núcleo -> (touros, nelore?) a partir do catálogo genético
    cur.execute("""
        SELECT upper(trim(r.fazenda_origem)) AS faz, count(*) AS n,
               count(*) FILTER (WHERE r.raca_id=1) AS n_nelore
        FROM mercado.reprodutor r
        WHERE r.fazenda_origem IS NOT NULL AND trim(r.fazenda_origem)<>''
          AND upper(trim(r.fazenda_origem)) <> 'GENEALOGIA'
        GROUP BY 1""")
    idx = {}
    for row in cur.fetchall():
        k = norm(row["faz"])
        if len(k) < 5: continue          # núcleo curto demais = ruído
        d = idx.setdefault(k, {"touros":0,"nelore":0,"nomes":set()})
        d["touros"] += row["n"]; d["nelore"] += row["n_nelore"]; d["nomes"].add(row["faz"])
    print(f"[catálogo: {len(idx)} núcleos de fazenda distintos (>=5 chars)]", file=sys.stderr, flush=True)

    # 2) prospects: corte ativo (uma linha por empresa) com razão + nome_fantasia
    cur.execute("""
        SELECT DISTINCT ON (e.cnpj_basico) e.cnpj_basico,
               COALESCE(NULLIF(em.razao_social,''), e.nome_fantasia) AS razao,
               e.nome_fantasia, e.uf, e.municipio_nome AS municipio
        FROM cnpj.estabelecimento_rural e
        LEFT JOIN cnpj.empresa_rural em ON em.cnpj_basico=e.cnpj_basico
        WHERE e.cnae_fiscal_principal='0151201' AND e.situacao_cadastral='02'
        ORDER BY e.cnpj_basico""")
    prospects = cur.fetchall()
    print(f"[prospects corte: {len(prospects)}]", file=sys.stderr, flush=True)

    cur.execute("""CREATE TABLE IF NOT EXISTS prospeccao.prospect_genetica(
        cnpj_basico varchar(8) PRIMARY KEY, razao text, uf varchar(2), municipio text,
        match_fazenda text, nucleo text, touros int, touros_nelore int, confianca text);""")
    cur.execute("TRUNCATE prospeccao.prospect_genetica")

    matched = 0; by_conf = {}
    for p in prospects:
        cores = set()
        for fld in (p["razao"], p["nome_fantasia"]):
            k = norm(fld or "")
            if len(k) >= 5: cores.add(k)
        best = None
        for k in cores:
            if k in idx:
                if best is None or idx[k]["touros"] > idx[best]["touros"]:
                    best = k
        if not best: continue
        info = idx[best]
        conf = "baixa" if best in GENERIC else ("alta" if (len(best) >= 6 and " " in best) else "media")
        by_conf[conf] = by_conf.get(conf,0)+1; matched += 1
        cur.execute("""INSERT INTO prospeccao.prospect_genetica
            (cnpj_basico,razao,uf,municipio,match_fazenda,nucleo,touros,touros_nelore,confianca)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (cnpj_basico) DO NOTHING""",
            (p["cnpj_basico"], p["razao"], p["uf"], p["municipio"],
             sorted(info["nomes"])[0], best, info["touros"], info["nelore"], conf))
    print(f"\n[MATCH] {matched} prospects cruzam c/ o catálogo genético", file=sys.stderr)
    for c in ("alta","media","baixa"):
        print(f"  {c}: {by_conf.get(c,0)}", file=sys.stderr)

if __name__ == "__main__":
    main()
