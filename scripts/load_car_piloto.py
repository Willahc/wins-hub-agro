#!/usr/bin/env python3
"""PILOTO Camada 4: baixa imóveis CAR de 1 município via WFS GeoServer SICAR,
calcula centroide do polígono (sem PostGIS/GDAL) e grava CSV p/ carga em prospeccao.imovel_rural.
Uso: python load_car_piloto.py <uf_lower> <cod_ibge> <saida.csv>"""
import sys, json, csv, subprocess

UF, IBGE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
BASE = "https://geoserver.car.gov.br/geoserver/sicar/ows"
TYPE = f"sicar:sicar_imoveis_{UF}"
PAGE = 1000


def fetch(start):
    qs = (f"{BASE}?service=WFS&version=2.0.0&request=GetFeature&typeName={TYPE}"
          f"&outputFormat=application/json&count={PAGE}&startIndex={start}"
          f"&CQL_FILTER=cod_municipio_ibge={IBGE}")
    out = subprocess.run(["curl", "-sS", "-m", "180", qs], capture_output=True, timeout=200)
    return json.loads(out.stdout)


def centroid(geom):
    """média de todos os vértices (aprox. p/ escala de fazenda). Retorna (lon,lat)."""
    pts = []
    def walk(c):
        if isinstance(c[0], (int, float)):
            pts.append(c)
        else:
            for x in c:
                walk(x)
    walk(geom["coordinates"])
    n = len(pts)
    return (sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n)


rows, start = [], 0
while True:
    d = fetch(start)
    feats = d.get("features", [])
    if not feats:
        break
    for f in feats:
        p = f["properties"]
        lon, lat = centroid(f["geometry"])
        rows.append({
            "codigo_car": p.get("cod_imovel"),
            "uf": p.get("uf"), "municipio": p.get("municipio"),
            "codigo_ibge_mun": p.get("cod_municipio_ibge"),
            "latitude": round(lat, 6), "longitude": round(lon, 6),
            "area_total_ha": p.get("area"),
            "tipo_imovel": p.get("tipo_imovel"), "status": p.get("status_imovel"),
        })
    print(f"  ...{len(rows)} imóveis", flush=True)
    if len(feats) < PAGE:
        break
    start += PAGE

with open(OUT, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
# sanity: bbox dos centroides
lats = [r["latitude"] for r in rows]; lons = [r["longitude"] for r in rows]
print(f"TOTAL {len(rows)} | lat [{min(lats):.3f},{max(lats):.3f}] lon [{min(lons):.3f},{max(lons):.3f}]")
