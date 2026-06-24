#!/usr/bin/env python3
"""
lavoura_por_fazenda_br.py — área de LAVOURA por fazenda, SEM re-bater no WFS.

Prova do reuso da geometria persistida: lê os polígonos CAR já salvos em
data/car_geom/<ibge>.geojsonl.gz (pasto_full_br.py) — NÃO busca no SICAR de novo —
e roda zonal stats das classes de agricultura do MapBiomas (cobertura col.10 2024)
sobre eles. Preenche imovel_rural.area_lavoura_ha. Sinal ILP por fazenda
(pasto vs lavoura) p/ a tese BASF/inputs.

Resumível (/tmp/lavoura). Guarda de RAM (--win-mp). Roda no host (venv).
Uso: set -a && . ./.env && set +a
     nohup /root/.venv-wins-tools/bin/python scripts/lavoura_por_fazenda_br.py [--workers 4] &
"""
import os, sys, json, gzip, glob, argparse, math, threading, warnings, time
warnings.filterwarnings("ignore")
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                  VSI_CACHE="TRUE", CPL_VSIL_CURL_CACHE_SIZE="100000000", GDAL_CACHEMAX="200",
                  GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="2")
import psycopg2, rasterio
from rasterio.windows import from_bounds
from rasterstats import zonal_stats
from concurrent.futures import ThreadPoolExecutor, as_completed

COG = ("/vsicurl/https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
       "collection_10/lulc/coverage/brazil_coverage_2024.tif")
# MapBiomas col.10 — Agricultura (3.2): temporárias (soja 39, cana 20, arroz 40, algodão 62,
# outras temp 41, lavoura temp 19) + perenes (café 46, citrus 47, dendê 35, outras 48, perene 36) + agri genérica 18.
LAVOURA = {18,19,39,20,40,62,41,36,46,47,35,48,21}  # 21 = mosaico agri+pasto (conta como uso agrícola)
GEODIR = "data/car_geom"; DONEDIR = "/tmp/lavoura"; os.makedirs(DONEDIR, exist_ok=True)
_tl = threading.local(); _lock = threading.Lock(); _st = {"mun":0,"far":0,"lav":0.0,"err":0}

def db():
    if not hasattr(_tl,"cn"):
        pw=os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
        _tl.cn=psycopg2.connect(host="127.0.0.1",port=5432,dbname="wins_agro",user="postgres",password=pw)
    return _tl.cn

def cog():
    if not hasattr(_tl,"ds"): _tl.ds=rasterio.open(COG)
    return _tl.ds

def bbox_lat(geom):
    pts=[]
    def walk(c):
        if isinstance(c[0],(int,float)): pts.append(c)
        else:
            for x in c: walk(x)
    walk(geom["coordinates"])
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys), sum(ys)/len(ys)

def proc(path, win_mp):
    ibge=os.path.basename(path).split(".")[0]
    done=f"{DONEDIR}/{ibge}.done"
    if os.path.exists(done): return None
    feats=[]
    with gzip.open(path,"rt") as gz:
        for line in gz:
            try:
                o=json.loads(line); feats.append((o["car"], o["g"]))
            except Exception: pass
    if not feats:
        open(done,"w").write("0"); return (ibge,0,0.0)
    bb=[bbox_lat(g) for _,g in feats]; geoms=[g for _,g in feats]
    minx=min(b[0] for b in bb); miny=min(b[1] for b in bb)
    maxx=max(b[2] for b in bb); maxy=max(b[3] for b in bb)
    d=cog(); rx,ry=d.res[0],d.res[1]
    win=from_bounds(minx,miny,maxx,maxy,d.transform)
    if (win.width*win.height)/1e6 <= win_mp:
        arr=d.read(1,window=win); wtr=d.window_transform(win)
        stats=zonal_stats(geoms,arr,affine=wtr,categorical=True,nodata=0); del arr
    else:
        stats=zonal_stats(geoms,COG,categorical=True,nodata=0)
    upd=[]; mlav=0.0
    for (car,_),st,b in zip(feats,stats,bb):
        lat=b[4]; ph=(rx*111320*math.cos(math.radians(lat)))*(ry*111320)/10000
        npx=sum(st.get(k,0) for k in LAVOURA); lav=npx*ph; mlav+=lav
        upd.append((round(lav,2),car))
    cn=db(); cur=cn.cursor()
    cur.executemany("UPDATE prospeccao.imovel_rural SET area_lavoura_ha=%s WHERE codigo_car=%s", upd)
    cn.commit(); open(done,"w").write(str(len(feats)))
    return (ibge,len(feats),mlav)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--workers",type=int,default=4); ap.add_argument("--win-mp",type=float,default=50.0)
    a=ap.parse_args()
    files=sorted(glob.glob(f"{GEODIR}/*.geojsonl.gz"))
    pend=[f for f in files if not os.path.exists(f"{DONEDIR}/{os.path.basename(f).split('.')[0]}.done")]
    print(f"== LAVOURA por fazenda (geometria salva, SEM WFS) — {len(files)} munic ({len(pend)} pend) | {a.workers}w ==",flush=True)
    t0=time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs={ex.submit(proc,f,a.win_mp):f for f in pend}
        for fu in as_completed(futs):
            try:
                r=fu.result()
                if r is None: continue
                ib,nf,ml=r
                with _lock: _st["mun"]+=1; _st["far"]+=nf; _st["lav"]+=ml; n=_st["mun"]
                if n%50==0:
                    el=time.time()-t0
                    print(f"[{n}/{len(pend)}] acum {_st['far']:,} faz, {_st['lav']/1e6:.1f} Mha lavoura · {_st['far']/el:.0f} faz/s",flush=True)
            except Exception as e:
                with _lock: _st["err"]+=1
                print(f"[ERR] {futs[fu]}: {type(e).__name__}: {str(e)[:100]}",flush=True)
    print(f"\n=== LAVOURA done: {_st['mun']} munic, {_st['far']:,} faz, {_st['lav']/1e6:.1f} Mha lavoura, {_st['err']} erros ===",flush=True)

if __name__=="__main__": main()
