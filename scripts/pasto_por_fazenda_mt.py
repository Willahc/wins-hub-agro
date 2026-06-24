#!/usr/bin/env python3
"""
pasto_por_fazenda_mt.py — ESCALA o piloto p/ vários municípios de MT.

Para cada município (ordem = mais pasto primeiro, fronteira pecuária):
  1. busca TODOS os polígonos CAR no WFS SICAR (paginado), guardando a geometria
  2. lê a JANELA do bbox do município UMA vez do COG MapBiomas (/vsicurl) p/ memória
  3. zonal stats classe 15 (pastagem) em memória (rápido) -> area_pasto_ha/cobertura
  4. UPDATE imovel_rural por codigo_car
Resumível por município (.done). Cap --max-farms por município (loga truncação).

Uso:
    set -a && . ./.env && set +a
    /root/.venv-wins-tools/bin/python scripts/pasto_por_fazenda_mt.py \
        [--uf mt] [--top 10] [--max-farms 1500] [--ano 2024]
"""
import os, sys, json, argparse, subprocess, math
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                  VSI_CACHE="TRUE", CPL_VSIL_CURL_CACHE_SIZE="200000000",
                  GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="1")
import psycopg2
import rasterio
from rasterio.windows import from_bounds
from rasterstats import zonal_stats

WFS = "https://geoserver.car.gov.br/geoserver/sicar/ows"
COG = ("/vsicurl/https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
       "collection_10/lulc/coverage/brazil_coverage_{ano}.tif")
PASTAGEM = 15
PAGE = 1000
DONEDIR = "/tmp/pasto_mt"; os.makedirs(DONEDIR, exist_ok=True)

def fetch_all(uf, ibge, cap):
    feats, start = [], 0
    while len(feats) < cap:
        qs=(f"{WFS}?service=WFS&version=2.0.0&request=GetFeature"
            f"&typeName=sicar:sicar_imoveis_{uf}&outputFormat=application/json"
            f"&count={PAGE}&startIndex={start}&CQL_FILTER=cod_municipio_ibge={ibge}")
        try:
            r=subprocess.run(["curl","-sS","-m","240",qs],capture_output=True,timeout=260)
            page=json.loads(r.stdout).get("features",[])
        except Exception as e:
            print(f"    [warn] WFS falhou start={start}: {e}", flush=True); break
        if not page: break
        feats.extend(page)
        if len(page) < PAGE: break
        start += PAGE
    return feats[:cap], len(feats) >= cap

def bbox_and_lat(geom):
    pts=[]
    def walk(c):
        if isinstance(c[0],(int,float)): pts.append(c)
        else:
            for x in c: walk(x)
    walk(geom["coordinates"])
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys), sum(ys)/len(ys)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--uf", default="mt")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--max-farms", type=int, default=1500)
    ap.add_argument("--ano", type=int, default=2024)
    a=ap.parse_args()
    pw=os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    cn=psycopg2.connect(host="127.0.0.1",port=5432,dbname="wins_agro",user="postgres",password=pw)
    cur=cn.cursor()
    cur.execute("""SELECT m.codigo_ibge, m.nome, p.pasto_municipal_ha
                   FROM referencia.municipio m
                   JOIN prospeccao.pasto_municipal p ON p.codigo_ibge=m.codigo_ibge
                   WHERE upper(m.uf)=upper(%s)
                   ORDER BY p.pasto_municipal_ha DESC NULLS LAST LIMIT %s""",(a.uf,a.top))
    muns=cur.fetchall()
    print(f"== ESCALA pasto/fazenda — {a.uf.upper()} top {len(muns)} munic. por pasto — MapBiomas {a.ano} ==")
    ds=rasterio.open(COG.format(ano=a.ano))
    res_x=ds.res[0]; res_y=ds.res[1]
    grand_far=grand_pasto=0
    for ibge,nome,pmun in muns:
        done=f"{DONEDIR}/{ibge}.done"
        if os.path.exists(done):
            print(f"[{ibge}] {nome}: já feito, pulando", flush=True); continue
        feats,trunc=fetch_all(a.uf,ibge,a.max_farms)
        if not feats:
            print(f"[{ibge}] {nome}: 0 polígonos (WFS) — pulando", flush=True)
            open(done,"w").write("0"); continue
        # bbox global do município
        bb=[bbox_and_lat(f["geometry"]) for f in feats]
        minx=min(b[0] for b in bb); miny=min(b[1] for b in bb)
        maxx=max(b[2] for b in bb); maxy=max(b[3] for b in bb)
        win=from_bounds(minx,miny,maxx,maxy,ds.transform)
        arr=ds.read(1,window=win); wtr=ds.window_transform(win)
        geoms=[f["geometry"] for f in feats]
        stats=zonal_stats(geoms,arr,affine=wtr,categorical=True,nodata=0)
        upd=[]; mpasto=0
        for f,st,b in zip(feats,stats,bb):
            car=f["properties"].get("cod_imovel"); lat=b[4]
            ph=(res_x*111320*math.cos(math.radians(lat)))*(res_y*111320)/10000
            np_=st.get(PASTAGEM,0); ntot=sum(st.values()) or 1
            pasto_ha=np_*ph; mpasto+=pasto_ha
            upd.append((round(pasto_ha,2),round(np_/ntot,4),car))
        cur.executemany("""UPDATE prospeccao.imovel_rural
            SET area_pasto_ha=%s, cobertura_pasto_mapbiomas=%s, coletado_em=now()
            WHERE codigo_car=%s""", upd)
        cn.commit()
        grand_far+=len(feats); grand_pasto+=mpasto
        tag=" [TRUNCADO cap]" if trunc else ""
        print(f"[{ibge}] {nome}: {len(feats)} fazendas{tag} | pasto {mpasto:,.0f} ha "
              f"| {cur.rowcount} updates | ref municipal {pmun:,.0f} ha", flush=True)
        open(done,"w").write(str(len(feats)))
    ds.close(); cn.close()
    print(f"\n=== MT ESCALA done: {grand_far:,} fazendas, {grand_pasto:,.0f} ha pasto somado ===")

if __name__=="__main__":
    main()
