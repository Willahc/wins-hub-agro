#!/usr/bin/env python3
"""Camada 4 NACIONAL: baixa todos os imóveis CAR do Brasil via WFS GeoServer SICAR,
calcula centroide (sem PostGIS/GDAL) e carrega em prospeccao.imovel_rural.
Estratégia: por UF -> por município (offsets pequenos), 6 workers, resumível por UF (.done),
carga incremental no banco ao fim de cada UF. Fetch via curl (host) p/ contornar SSL do container.
"""
import os, json, csv, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE = "https://geoserver.car.gov.br/geoserver/sicar/ows"
PAGE = 1000
WORKERS = 6
OUTDIR = "/tmp/car_nacional"
DB = "wins_agro_v1_db_1"
UFS = ["ac","al","am","ap","ba","ce","df","es","go","ma","mg","ms","mt","pa","pb",
       "pe","pi","pr","rj","rn","ro","rr","rs","sc","se","sp","to"]
os.makedirs(OUTDIR, exist_ok=True)


def municipios_da_uf(uf):
    """lista de codigo_ibge dos municípios da UF, da referencia.municipio."""
    out = subprocess.run(
        ["docker","exec","-i",DB,"psql","-U","postgres","-d","wins_agro","-tAc",
         f"SELECT codigo_ibge FROM referencia.municipio WHERE upper(uf)='{uf.upper()}' ORDER BY codigo_ibge"],
        capture_output=True, text=True)
    return [l.strip() for l in out.stdout.splitlines() if l.strip()]


def centroid(geom):
    pts = []
    def walk(c):
        if isinstance(c[0], (int, float)): pts.append(c)
        else:
            for x in c: walk(x)
    walk(geom["coordinates"])
    n = len(pts)
    return (sum(p[0] for p in pts)/n, sum(p[1] for p in pts)/n)


def fetch(uf, ibge, start):
    qs = (f"{BASE}?service=WFS&version=2.0.0&request=GetFeature&typeName=sicar:sicar_imoveis_{uf}"
          f"&outputFormat=application/json&count={PAGE}&startIndex={start}"
          f"&CQL_FILTER=cod_municipio_ibge={ibge}")
    for attempt in range(3):
        try:
            r = subprocess.run(["curl","-sS","-m","200",qs], capture_output=True, timeout=230)
            return json.loads(r.stdout)
        except Exception:
            if attempt == 2: raise
    return {"features": []}


def coleta_municipio(uf, ibge):
    rows, start = [], 0
    while True:
        d = fetch(uf, ibge, start)
        feats = d.get("features", [])
        if not feats: break
        for f in feats:
            try:
                lon, lat = centroid(f["geometry"]); p = f["properties"]
                rows.append((p.get("cod_imovel"), p.get("uf"), p.get("municipio"),
                             p.get("cod_municipio_ibge"), round(lat,6), round(lon,6),
                             p.get("area"), p.get("tipo_imovel"), p.get("status_imovel")))
            except Exception:
                pass
        if len(feats) < PAGE: break
        start += PAGE
    return rows


def carrega_uf(uf, csv_path):
    subprocess.run(["docker","cp",csv_path,f"{DB}:/tmp/_caruf.csv"], check=True)
    sql = """CREATE TEMP TABLE _s (codigo_car text,uf text,municipio text,codigo_ibge_mun text,
        latitude numeric,longitude numeric,area_total_ha numeric,tipo_imovel text,status text);
        \\copy _s FROM '/tmp/_caruf.csv' WITH CSV
        INSERT INTO prospeccao.imovel_rural
          (codigo_car,uf,municipio,codigo_ibge_mun,latitude,longitude,area_total_ha,fonte_principal,obs)
        SELECT codigo_car,uf,municipio,codigo_ibge_mun,latitude,longitude,area_total_ha,'SICAR',
          'tipo='||tipo_imovel||' status='||status FROM _s ON CONFLICT (codigo_car) DO NOTHING;"""
    subprocess.run(["docker","exec","-i",DB,"psql","-U","postgres","-d","wins_agro"],
                   input=sql, text=True, check=True)


def main():
    only = sys.argv[1].split(",") if len(sys.argv) > 1 else UFS
    for uf in only:
        done = f"{OUTDIR}/{uf}.done"
        if os.path.exists(done):
            print(f"[{uf}] já feito, pulando", flush=True); continue
        muns = municipios_da_uf(uf)
        print(f"[{uf}] {len(muns)} municípios — coletando…", flush=True)
        csv_path = f"{OUTDIR}/{uf}.csv"; total = 0
        with open(csv_path, "w", newline="") as fh:
            w = csv.writer(fh)
            with ThreadPoolExecutor(max_workers=WORKERS) as ex:
                futs = {ex.submit(coleta_municipio, uf, m): m for m in muns}
                for i, fu in enumerate(as_completed(futs), 1):
                    rows = fu.result()
                    if rows: w.writerows(rows); total += len(rows)
                    if i % 50 == 0:
                        print(f"  [{uf}] {i}/{len(muns)} mun · {total} imóveis", flush=True)
        print(f"[{uf}] coleta done: {total} imóveis — carregando no banco…", flush=True)
        if total: carrega_uf(uf, csv_path)
        open(done, "w").write(str(total))
        print(f"[{uf}] ✓ {total} carregados", flush=True)
    print("=== NACIONAL CONCLUÍDO ===", flush=True)


if __name__ == "__main__":
    main()
