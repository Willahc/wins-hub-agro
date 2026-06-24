#!/usr/bin/env python3
"""
pasto_full_br.py — NACIONAL "tudo de uma vez": uma única passada no WFS SICAR
extrai do MapBiomas (COGs públicos, sem EE) por fazenda:
  - area_pasto_ha            (cobertura col.10, classe 15 = pasto plantado)
  - area_campo_ha            (classe 12 = campo nativo — corrige RS/Pampa)
  - area_vegetacao_nativa_ha (classe 3 = floresta)
  - cobertura_pasto_mapbiomas(fração de pasto)
  - qualidade_pasto_mapbiomas(vigor col.8 2022: classe modal 1/2/3 ->
        1='degradada' / 2='intermediaria' / 3='vigorosa')
E GUARDA A GEOMETRIA (GeoJSONL gzip por município em data/car_geom/) p/ nunca
mais re-buscar o WFS em futuros layers.

Por município (pool de workers): fetch CAR -> lê janela do bbox UMA vez de cada
COG (cobertura 2024 + vigor 2022) -> zonal stats em memória -> UPDATE + dump geom.
Guarda de RAM (--win-mp) e de coordenada-corrompida. Resumível (/tmp/pasto_full).

Uso:
    set -a && . ./.env && set +a
    nohup /root/.venv-wins-tools/bin/python scripts/pasto_full_br.py \
        [--workers 4] [--win-mp 50] [--ufs ...] &
"""
import os, sys, json, gzip, argparse, subprocess, math, threading, warnings, time
warnings.filterwarnings("ignore")
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                  VSI_CACHE="TRUE", CPL_VSIL_CURL_CACHE_SIZE="100000000",
                  GDAL_CACHEMAX="200", GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="2")
import psycopg2
import rasterio
from rasterio.windows import from_bounds
from rasterstats import zonal_stats
from concurrent.futures import ThreadPoolExecutor, as_completed

WFS = "https://geoserver.car.gov.br/geoserver/sicar/ows"
COG_COB = ("/vsicurl/https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
           "collection_10/lulc/coverage/brazil_coverage_2024.tif")
COG_VIG = ("/vsicurl/https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
           "collection_8/pasture-quality/pasture_quality_2022.tif")
PASTO, CAMPO, FLOR = 15, 12, 3
VIG = {1: "degradada", 2: "intermediaria", 3: "vigorosa"}
PAGE = 1000
DONEDIR = "/tmp/pasto_full"; GEODIR = "data/car_geom"
os.makedirs(DONEDIR, exist_ok=True); os.makedirs(GEODIR, exist_ok=True)
_tl = threading.local(); _lock = threading.Lock()
_st = {"mun": 0, "far": 0, "pasto": 0.0, "campo": 0.0, "err": 0}

def db():
    if not hasattr(_tl, "cn"):
        pw=os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
        _tl.cn=psycopg2.connect(host="127.0.0.1",port=5432,dbname="wins_agro",user="postgres",password=pw)
    return _tl.cn

def cog(which):
    a="ds_"+which
    if not hasattr(_tl,a):
        setattr(_tl,a, rasterio.open(COG_COB if which=="cob" else COG_VIG))
    return getattr(_tl,a)

def fetch_all(uf, ibge):
    feats, start = [], 0
    while True:
        qs=(f"{WFS}?service=WFS&version=2.0.0&request=GetFeature"
            f"&typeName=sicar:sicar_imoveis_{uf}&outputFormat=application/json"
            f"&count={PAGE}&startIndex={start}&CQL_FILTER=cod_municipio_ibge={ibge}")
        for att in range(4):
            try:
                r=subprocess.run(["curl","-sS","-m","240",qs],capture_output=True,timeout=260)
                page=json.loads(r.stdout).get("features",[]); break
            except Exception:
                if att==3: raise
                time.sleep(3)
        if not page: break
        feats.extend(page)
        if len(page)<PAGE: break
        start+=PAGE
    return feats

def bbox_lat(geom):
    pts=[]
    def walk(c):
        if isinstance(c[0],(int,float)): pts.append(c)
        else:
            for x in c: walk(x)
    walk(geom["coordinates"])
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys), sum(ys)/len(ys)

def proc(ibge, uf, nome, win_mp):
    done=f"{DONEDIR}/{ibge}.done"
    if os.path.exists(done): return None
    feats=fetch_all(uf, ibge)
    if not feats:
        open(done,"w").write("0"); return (ibge,nome,0,0.0)
    keep=[]
    for f in feats:
        b=bbox_lat(f["geometry"])
        if -74<=b[0]<=-28 and -74<=b[2]<=-28 and -34<=b[1]<=6 and -34<=b[3]<=6:
            keep.append((f,b))
    if not keep:
        open(done,"w").write("0"); return (ibge,nome,0,0.0)
    feats=[k[0] for k in keep]; bb=[k[1] for k in keep]
    geoms=[f["geometry"] for f in feats]
    minx=min(b[0] for b in bb); miny=min(b[1] for b in bb)
    maxx=max(b[2] for b in bb); maxy=max(b[3] for b in bb)

    def stats_for(which):
        d=cog(which)
        win=from_bounds(minx,miny,maxx,maxy,d.transform)
        if (win.width*win.height)/1e6 <= win_mp:
            arr=d.read(1,window=win); wtr=d.window_transform(win)
            s=zonal_stats(geoms,arr,affine=wtr,categorical=True,nodata=0); del arr
        else:
            s=zonal_stats(geoms,(COG_COB if which=="cob" else COG_VIG),categorical=True,nodata=0)
        return s
    scob=stats_for("cob"); svig=stats_for("vig")

    d=cog("cob"); rx,ry=d.res[0],d.res[1]
    upd=[]; mpasto=mcampo=0.0
    for f,sc,sv,b in zip(feats,scob,svig,bb):
        car=f["properties"].get("cod_imovel"); lat=b[4]
        ph=(rx*111320*math.cos(math.radians(lat)))*(ry*111320)/10000
        pasto=sc.get(PASTO,0)*ph; campo=sc.get(CAMPO,0)*ph; flor=sc.get(FLOR,0)*ph
        ntot=sum(sc.values()) or 1
        cob=round(sc.get(PASTO,0)/ntot,4)
        mpasto+=pasto; mcampo+=campo
        qual=None
        vg={k:sv.get(k,0) for k in (1,2,3)}
        if sum(vg.values())>0:
            qual=VIG[max(vg,key=vg.get)]
        upd.append((round(pasto,2),round(campo,2),round(flor,2),cob,qual,car))
    cn=db(); cur=cn.cursor()
    cur.executemany("""UPDATE prospeccao.imovel_rural
        SET area_pasto_ha=%s, area_campo_ha=%s, area_vegetacao_nativa_ha=%s,
            cobertura_pasto_mapbiomas=%s, qualidade_pasto_mapbiomas=%s, coletado_em=now()
        WHERE codigo_car=%s""", upd)
    cn.commit()
    # dump geometria (GeoJSONL gzip) — futuro-prova contra re-fetch
    gp=f"{GEODIR}/{ibge}.geojsonl.gz"
    with gzip.open(gp,"wt") as gz:
        for f in feats:
            gz.write(json.dumps({"car":f["properties"].get("cod_imovel"),
                                 "g":f["geometry"]},separators=(",",":"))+"\n")
    open(done,"w").write(str(len(feats)))
    return (ibge,nome,len(feats),mpasto)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--workers",type=int,default=4)
    ap.add_argument("--win-mp",type=float,default=50.0)
    ap.add_argument("--ufs",default="")
    a=ap.parse_args()
    pw=os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    cn=psycopg2.connect(host="127.0.0.1",port=5432,dbname="wins_agro",user="postgres",password=pw)
    cur=cn.cursor()
    cur.execute("ALTER TABLE prospeccao.imovel_rural ADD COLUMN IF NOT EXISTS area_campo_ha numeric")
    cn.commit()
    where=""
    if a.ufs:
        ufs=",".join("'%s'"%u.strip().upper() for u in a.ufs.split(","))
        where=f"WHERE upper(i.uf) IN ({ufs})"
    cur.execute(f"""SELECT DISTINCT i.codigo_ibge_mun, lower(i.uf),
                 (SELECT nome FROM referencia.municipio m WHERE m.codigo_ibge=i.codigo_ibge_mun::integer)
                FROM prospeccao.imovel_rural i {where} ORDER BY 1""")
    muns=[r for r in cur.fetchall() if r[0]]; cn.close()
    pend=[m for m in muns if not os.path.exists(f"{DONEDIR}/{m[0]}.done")]
    print(f"== NACIONAL FULL — {len(muns)} munic ({len(pend)} pend) | {a.workers}w | "
          f"cob2024+vig2022+geom ==", flush=True)
    t0=time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs={ex.submit(proc,ib,uf,nm,a.win_mp):(ib,nm) for ib,uf,nm in pend}
        for fu in as_completed(futs):
            ib,nm=futs[fu]
            try:
                r=fu.result()
                if r is None: continue
                _,_,nf,mp=r
                with _lock:
                    _st["mun"]+=1; _st["far"]+=nf; _st["pasto"]+=mp; n=_st["mun"]
                if n%20==0 or nf>3000:
                    el=time.time()-t0
                    print(f"[{n}/{len(pend)}] {nm}/{ib}: {nf} faz · acum {_st['far']:,} faz, "
                          f"{_st['pasto']/1e6:.1f} Mha pasto · {_st['far']/el:.0f} faz/s",flush=True)
            except Exception as e:
                with _lock: _st["err"]+=1
                print(f"[ERR] {nm}/{ib}: {type(e).__name__}: {str(e)[:120]}",flush=True)
    print(f"\n=== FULL done: {_st['mun']} munic, {_st['far']:,} faz, "
          f"{_st['pasto']/1e6:.1f} Mha pasto, {_st['err']} erros ===",flush=True)

if __name__=="__main__":
    main()
