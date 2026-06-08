"""
Stage do catálogo PÚBLICO da Monte Sião Genética para o pitch (caminho aprovado pelo dono).

Cria a central 'Monte Sião Genética' (Porto Nacional/TO) e insere os 12 SKUs reais
com os preços públicos reais (R$190/290/390), ligando cada um à melhor linhagem
'Genética Aditiva' (programa da Monte Sião) já presente na base, por nome.

É DEMO/aproximado e 100% reversível:
  DELETE FROM mercado.touro_oferta WHERE fonte_referencia = 'Monte Sião (catálogo público)';
  DELETE FROM catalogo.central WHERE sigla = 'MSG';
Substituir pelo sumário/tabela REAL da Monte Sião quando o deal fechar.
"""
import os
import psycopg2

DB = {"host": os.getenv("DB_HOST", "db"), "port": int(os.getenv("DB_PORT", 5432)),
      "dbname": os.getenv("POSTGRES_DB", "wins_agro"), "user": os.getenv("POSTGRES_USER", "postgres"),
      "password": os.getenv("POSTGRES_PASSWORD", "")}

FONTE = "Monte Sião (catálogo público)"

# (SKU, raiz p/ casar nome, preço dose R$) — preços validados no site deles 2026-06-05
SKUS = [
    ("INQUESTIONÁVEL", "INQUESTION", 390.0),
    ("ABRAÃO", "ABRAAO", 290.0),
    ("CRONOS", "CRONOS", 290.0),
    ("INFINITO", "INFINITO", 190.0),
    ("INTENSO", "INTENSO", 190.0),
    ("HERMOSO", "HERMOSO", 190.0),
    ("GENERAL", "GENERAL", 190.0),
    ("ASTRO", "ASTRO", 190.0),
    ("HERON", "HERON", 190.0),
    ("SANSÃO", "SANSAO", 190.0),
    ("ALBATROZ", "ALBATROZ", 190.0),
    ("AQUILES", "AQUILES", 190.0),
]


def melhor_bull(cur, raiz, usados):
    """Melhor touro Nelore com DEP p/ a raiz: prioriza Genética Aditiva; evita repetir."""
    for cond in (
        "r.nome ILIKE %(p)s AND r.nome ILIKE '%%GENETICA ADITIVA%%'",
        "r.nome ILIKE %(p)s",
        "r.nome ILIKE '%%GENETICA ADITIVA%%'",   # fallback: top da linhagem ainda livre
    ):
        cur.execute(f"""
            SELECT r.id, r.nome,
                   (SELECT MAX(valor) FROM mercado.avaliacao a
                      WHERE a.reprodutor_id=r.id AND a.caracteristica_id=20) AS iqgg
            FROM mercado.reprodutor r
            WHERE r.raca_id=1 AND r.sexo='M' AND {cond}
            ORDER BY iqgg DESC NULLS LAST
            LIMIT 40
        """, {"p": f"%{raiz}%"})
        for rid, nome, iqgg in cur.fetchall():
            if rid not in usados and iqgg is not None:
                return rid, nome, iqgg
    return None, None, None


def main():
    conn = psycopg2.connect(**DB); conn.autocommit = False
    cur = conn.cursor()
    # central Monte Sião (id explícito; central não tem default)
    cur.execute("SELECT id FROM catalogo.central WHERE sigla='MSG'")
    row = cur.fetchone()
    if row:
        central_id = row[0]
    else:
        cur.execute("SELECT COALESCE(MAX(id),0)+1 FROM catalogo.central")
        central_id = cur.fetchone()[0]
        cur.execute("INSERT INTO catalogo.central (id, sigla, nome, site) VALUES (%s,'MSG',%s,%s)",
                    (central_id, "Monte Sião Genética", "montesiaogenetica.com.br"))
    usados, n = set(), 0
    for sku, raiz, preco in SKUS:
        rid, nome, iqgg = melhor_bull(cur, raiz, usados)
        if not rid:
            print(f"  [{sku}] sem touro disponível — pulado"); continue
        usados.add(rid)
        cur.execute("""
            INSERT INTO mercado.touro_oferta
              (reprodutor_id, central_id, nome_comercial, preco_dose_brl,
               bull_external_id, fonte_referencia, coletado_em)
            VALUES (%s,%s,%s,%s,%s,%s, now())
            ON CONFLICT (central_id, bull_external_id) WHERE bull_external_id IS NOT NULL
            DO UPDATE SET reprodutor_id=EXCLUDED.reprodutor_id, nome_comercial=EXCLUDED.nome_comercial,
                          preco_dose_brl=EXCLUDED.preco_dose_brl, fonte_referencia=EXCLUDED.fonte_referencia
        """, (rid, central_id, f"{sku} (Monte Sião)", preco, f"MS-{raiz}", FONTE))
        n += 1
        print(f"  {sku:16} R${preco:6.0f}  ->  {nome[:34]:34} (IQGg {iqgg:.1f})")
    print(f"central_id={central_id} | {n} SKUs Monte Sião staged")
    conn.commit()
    cur.close(); conn.close()


if __name__ == "__main__":
    main()
