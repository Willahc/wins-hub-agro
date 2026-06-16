"""Backbone de rebanho/MATRIZES por municipio -> prospeccao.rebanho_municipio.

Junta o autoritativo do IBGE em duas camadas:
- Censo Agropecuario 2017 (tab 6910): total de bovinos (var 2057) e, sobretudo,
  VACAS REPRODUTORAS = matrizes (var 9741) por municipio. O Censo da a matriz DIRETO,
  nao por estimativa. Classificacoes pinadas em "Total" (829[46302]).
- PPM 2024 (ja no banco, prospeccao.ppm_municipio): total de bovinos atual por municipio.

Como o Censo de matriz e de 2017, projeto para 2024 mantendo a PROPORCAO de matriz do Censo
e reescalando pelo total atual do PPM:
    matrizes_estim_2024 = bovinos_ppm_2024 * (matrizes_censo_2017 / bovinos_censo_2017)

Matriz = unidade endereçavel de genetica (1 vaca apta = ~1 dose/ano). Este e o denominador
de demanda que alimenta score de prospeccao, TAM por territorio e o mapa CPF.

Roda dentro do container api:  docker exec -i wins_agro_v1-api-1 python3 - < scripts/build_rebanho_municipio.py
Idempotente: upsert por codigo_ibge.
"""
import os
import httpx
import psycopg2
import psycopg2.extras

SIDRA = "https://servicodados.ibge.gov.br/api/v3/agregados/6910/periodos/2017/variaveis/{var}?localidades=N6[all]&classificacao=829[46302]"
SUPRESSO = {"-", "..", "...", "X", "x", "", None}

DB = dict(host=os.getenv("DB_HOST", "db"), port=int(os.getenv("DB_PORT", 5432)),
          dbname=os.getenv("POSTGRES_DB", "wins_agro"), user=os.getenv("POSTGRES_USER", "postgres"),
          password=os.getenv("POSTGRES_PASSWORD", ""))


def pull(var):
    """codigo_ibge(int) -> valor(int|None) para a variavel do Censo 6910."""
    url = SIDRA.format(var=var)
    r = httpx.get(url, timeout=120)
    r.raise_for_status()
    out = {}
    for bloco in r.json():
        for res in bloco["resultados"]:
            for s in res["series"]:
                ibge = int(s["localidade"]["id"])
                val = list(s["serie"].values())[0]
                out[ibge] = None if val in SUPRESSO else int(val)
    return out


def main():
    print("Censo 6910: puxando total (2057) e matrizes/vacas reprodutoras (9741)...", flush=True)
    total_censo = pull("2057")
    matriz_censo = pull("9741")
    print(f"  censo: {len(total_censo)} munis total, {len(matriz_censo)} munis matriz", flush=True)

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    # PPM 2024 total por municipio
    cur.execute("""
        SELECT codigo_ibge_mun::int, max(efetivo_cabecas)
        FROM prospeccao.ppm_municipio
        WHERE especie_codigo='BOV' AND ano_referencia=2024
        GROUP BY 1""")
    ppm2024 = dict(cur.fetchall())
    # nome/uf
    cur.execute("SELECT codigo_ibge, nome, uf FROM referencia.municipio")
    ref = {r[0]: (r[1], r[2]) for r in cur.fetchall()}
    print(f"  ppm2024: {len(ppm2024)} munis | referencia: {len(ref)} munis", flush=True)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS prospeccao.rebanho_municipio (
            codigo_ibge        integer PRIMARY KEY,
            municipio          text,
            uf                 char(2),
            bovinos_censo2017  bigint,
            matrizes_censo2017 bigint,
            matriz_pct         numeric(5,3),
            bovinos_ppm2024    bigint,
            matrizes_estim2024 bigint,
            fonte              text DEFAULT 'IBGE Censo 2017 tab.6910 (var 2057/9741) + PPM 2024',
            updated_at         timestamptz DEFAULT now())""")
    conn.commit()

    linhas = []
    todos = set(total_censo) | set(matriz_censo) | set(ppm2024) | set(ref)
    for ibge in todos:
        nome, uf = ref.get(ibge, (None, None))
        tc = total_censo.get(ibge)
        mc = matriz_censo.get(ibge)
        ppm = ppm2024.get(ibge)
        pct = round(mc / tc, 3) if (tc and mc is not None and tc > 0) else None
        estim = int(round(ppm * pct)) if (ppm and pct is not None) else None
        linhas.append((ibge, nome, uf, tc, mc, pct, ppm, estim))

    psycopg2.extras.execute_values(cur, """
        INSERT INTO prospeccao.rebanho_municipio
            (codigo_ibge, municipio, uf, bovinos_censo2017, matrizes_censo2017,
             matriz_pct, bovinos_ppm2024, matrizes_estim2024)
        VALUES %s
        ON CONFLICT (codigo_ibge) DO UPDATE SET
            municipio=EXCLUDED.municipio, uf=EXCLUDED.uf,
            bovinos_censo2017=EXCLUDED.bovinos_censo2017, matrizes_censo2017=EXCLUDED.matrizes_censo2017,
            matriz_pct=EXCLUDED.matriz_pct, bovinos_ppm2024=EXCLUDED.bovinos_ppm2024,
            matrizes_estim2024=EXCLUDED.matrizes_estim2024, updated_at=now()
    """, linhas, page_size=2000)
    conn.commit()

    cur.execute("""SELECT count(*), count(matrizes_censo2017),
        to_char(sum(matrizes_censo2017)/1e6,'FM990D0'), to_char(sum(matrizes_estim2024)/1e6,'FM990D0'),
        to_char(sum(bovinos_ppm2024)/1e6,'FM990D0')
        FROM prospeccao.rebanho_municipio""")
    n, nm, mat_c, mat_e, ppm_t = cur.fetchone()
    print(f"OK | {n} munis | {nm} com matriz censo", flush=True)
    print(f"  MATRIZES Brasil: {mat_c}M (censo 2017) -> {mat_e}M (estim 2024) | rebanho PPM 2024: {ppm_t}M", flush=True)
    cur.execute("""SELECT uf, to_char(sum(matrizes_estim2024)/1e6,'FM990D0') FROM prospeccao.rebanho_municipio
        WHERE matrizes_estim2024 IS NOT NULL GROUP BY uf ORDER BY sum(matrizes_estim2024) DESC LIMIT 8""")
    print("  top UFs por matrizes estim 2024 (M):", "; ".join(f"{u} {v}" for u, v in cur.fetchall()), flush=True)
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
