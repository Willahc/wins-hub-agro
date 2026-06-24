#!/usr/bin/env python3
"""
pasto_por_fazenda_pilot.py — PILOTO MT: área de pasto por fazenda SEM Earth Engine.

Caminho: polígono CAR (WFS SICAR, guardando a geometria) × raster MapBiomas
(COG público, lido por janela via /vsicurl) -> zonal stats classe 15 (pastagem).
Prova que substitui o EE p/ preencher imovel_rural.area_pasto_ha / cobertura.

Uso:
    set -a && . ./.env && set +a
    /root/.venv-wins-tools/bin/python scripts/pasto_por_fazenda_pilot.py \
        [--ibge 5106240] [--n 40] [--ano 2024] [--gravar]
"""
import os, sys, json, argparse, subprocess, math
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                  VSI_CACHE="TRUE", GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="1")
import psycopg2
from rasterstats import zonal_stats

WFS = "https://geoserver.car.gov.br/geoserver/sicar/ows"
COG = ("/vsicurl/https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
       "collection_10/lulc/coverage/brazil_coverage_{ano}.tif")
PASTAGEM = 15  # classe MapBiomas

def fetch_car(uf, ibge, n):
    qs = (f"{WFS}?service=WFS&version=2.0.0&request=GetFeature"
          f"&typeName=sicar:sicar_imoveis_{uf}&outputFormat=application/json"
          f"&count={n}&CQL_FILTER=cod_municipio_ibge={ibge}")
    r = subprocess.run(["curl","-sS","-m","240",qs], capture_output=True, timeout=260)
    return json.loads(r.stdout).get("features", [])

def centroid_lat(geom):
    pts=[]
    def walk(c):
        if isinstance(c[0],(int,float)): pts.append(c)
        else:
            for x in c: walk(x)
    walk(geom["coordinates"])
    return sum(p[1] for p in pts)/len(pts)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--ibge", default="5106240")   # Nova Ubiratã/MT (fronteira pecuária)
    ap.add_argument("--uf", default="mt")
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--ano", type=int, default=2024)
    ap.add_argument("--gravar", action="store_true")
    a=ap.parse_args()

    pw=os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    cn=psycopg2.connect(host="127.0.0.1",port=5432,dbname="wins_agro",user="postgres",password=pw)
    cur=cn.cursor()
    cur.execute("SELECT nome, uf FROM referencia.municipio WHERE codigo_ibge=%s",(a.ibge,))
    row=cur.fetchone()
    mun = f"{row[0]}/{row[1]}" if row else f"IBGE {a.ibge}"
    cur.execute("SELECT pasto_municipal_ha FROM prospeccao.pasto_municipal WHERE codigo_ibge=%s",(a.ibge,))
    pm=cur.fetchone()
    print(f"== PILOTO pasto/fazenda — {mun} (IBGE {a.ibge}) — MapBiomas {a.ano} ==")
    if pm: print(f"   pasto municipal (referência MapBiomas): {pm[0]:,.0f} ha")

    print(f"[1] buscando até {a.n} polígonos CAR no WFS SICAR...", flush=True)
    feats=fetch_car(a.uf, a.ibge, a.n)
    print(f"    {len(feats)} polígonos recebidos")
    if not feats: sys.exit("WFS não retornou polígonos (CQL/UF?).")

    geoms=[f["geometry"] for f in feats]
    print(f"[2] zonal stats classe {PASTAGEM} no COG via /vsicurl (janela por polígono)...", flush=True)
    stats=zonal_stats(geoms, COG.format(ano=a.ano), categorical=True, all_touched=False, nodata=0)

    res=[]
    for f,st in zip(feats,stats):
        p=f["properties"]; car=p.get("cod_imovel"); area_car=p.get("area") or 0
        lat=centroid_lat(f["geometry"])
        # área/pixel corrigida pela latitude (30m, EPSG:4326)
        ph=(0.00026949*111320*math.cos(math.radians(lat)))*(0.00026949*111320)/10000
        npasto=st.get(PASTAGEM,0); ntot=sum(st.values()) or 1
        pasto_ha=npasto*ph
        res.append((car,float(area_car),pasto_ha,100*npasto/ntot))

    res.sort(key=lambda x:-x[2])
    print(f"\n{'CAR (cod_imovel)':<44}{'area_CAR':>10}{'pasto_ha':>10}{'%pasto':>8}")
    for car,acar,ph,pct in res[:15]:
        print(f"{car:<44}{acar:>10.1f}{ph:>10.1f}{pct:>7.0f}%")
    tot_car=sum(r[1] for r in res); tot_pasto=sum(r[2] for r in res)
    print(f"\n[ok] {len(res)} fazendas | área CAR total {tot_car:,.0f} ha | "
          f"pasto total {tot_pasto:,.0f} ha ({100*tot_pasto/tot_car:.0f}% da área)")

    if a.gravar:
        cur.executemany("""UPDATE prospeccao.imovel_rural
            SET area_pasto_ha=%s, cobertura_pasto_mapbiomas=%s,
                fonte_principal=COALESCE(fonte_principal,'SICAR'), coletado_em=now()
            WHERE codigo_car=%s""",
            [(round(ph,2), round(pct/100,4), car) for car,_,ph,pct in res])
        cn.commit()
        print(f"[grava] {cur.rowcount if cur.rowcount>=0 else len(res)} linhas atualizadas em imovel_rural")
    cn.close()

if __name__=="__main__":
    main()
