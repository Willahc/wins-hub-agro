#!/usr/bin/env python3
"""
pasto_por_fazenda_br.py — NACIONAL: área de pasto por fazenda via MapBiomas (sem EE).

Cobre TODOS os municípios com CAR no banco (imovel_rural), todas as UFs, SEM cap.
Por município (pool de workers, I/O-bound):
  1. busca todos os polígonos CAR no WFS SICAR (paginado, guardando geometria)
  2. lê a janela do bbox do município UMA vez do COG MapBiomas (/vsicurl) -> memória
     - GUARDA DE RAM: se a janela passar de --win-mp megapixels (município gigante
       da Amazônia), cai p/ zonal stats por-polígono (/vsicurl, RAM-safe, + lento)
  3. zonal stats classe 15 (pastagem) -> area_pasto_ha + cobertura_pasto_mapbiomas
  4. UPDATE imovel_rural por codigo_car
Resumível por município (/tmp/pasto_br/<ibge>.done). Só marca .done em sucesso.

Uso:
    set -a && . ./.env && set +a
    nohup /root/.venv-wins-tools/bin/python scripts/pasto_por_fazenda_br.py \
        [--workers 4] [--ano 2024] [--win-mp 60] [--ufs mt,go,...] &
"""
import os, sys, json, argparse, subprocess, math, threading, warnings, time
warnings.filterwarnings("ignore")
os.environ.update(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
                  CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                  VSI_CACHE="TRUE", CPL_VSIL_CURL_CACHE_SIZE="100000000",
                  GDAL_CACHEMAX="256", GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="2")
import psycopg2
import rasterio
from rasterio.windows import from_bounds
from rasterstats import zonal_stats
from concurrent.futures import ThreadPoolExecutor, as_completed

WFS = "https://geoserver.car.gov.br/geoserver/sicar/ows"
COG = ("/vsicurl/https://storage.googleapis.com/mapbiomas-public/initiatives/brasil/"
       "collection_10/lulc/coverage/brazil_coverage_{ano}.tif")
PASTAGEM = 15; PAGE = 1000; DONEDIR = "/tmp/pasto_br"
os.makedirs(DONEDIR, exist_ok=True)
_tl = threading.local()
_lock = threading.Lock()
_stats = {"mun": 0, "far": 0, "pasto": 0.0, "err": 0}

def db():
    if not hasattr(_tl, "cn"):
        pw = os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
        _tl.cn = psycopg2.connect(host="127.0.0.1", port=5432, dbname="wins_agro",
                                  user="postgres", password=pw)
    return _tl.cn

def ds(ano):
    if not hasattr(_tl, "ds"):
        _tl.ds = rasterio.open(COG.format(ano=ano))
    return _tl.ds

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
        if len(page) < PAGE: break
        start += PAGE
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

def proc_mun(ibge, uf, nome, ano, win_mp):
    done=f"{DONEDIR}/{ibge}.done"
    if os.path.exists(done): return None
    feats=fetch_all(uf, ibge)
    if not feats:
        open(done,"w").write("0"); return (ibge, nome, 0, 0.0)
    # guarda anti-coordenada-corrompida: descarta polígono cujo bbox cai fora do Brasil
    # (lon -74..-28, lat -34..6) — senão um ponto ruim estoura o tamanho da janela.
    keep=[]
    for f in feats:
        b=bbox_lat(f["geometry"])
        if -74<=b[0]<=-28 and -74<=b[2]<=-28 and -34<=b[1]<=6 and -34<=b[3]<=6:
            keep.append((f,b))
    if not keep:
        open(done,"w").write("0"); return (ibge, nome, 0, 0.0)
    feats=[k[0] for k in keep]; bb=[k[1] for k in keep]
    geoms=[f["geometry"] for f in feats]
    minx=min(b[0] for b in bb); miny=min(b[1] for b in bb)
    maxx=max(b[2] for b in bb); maxy=max(b[3] for b in bb)
    d=ds(ano); res_x,res_y=d.res[0],d.res[1]
    win=from_bounds(minx,miny,maxx,maxy,d.transform)
    mp=(win.width*win.height)/1e6
    if mp <= win_mp:
        arr=d.read(1,window=win); wtr=d.window_transform(win)
        stats=zonal_stats(geoms,arr,affine=wtr,categorical=True,nodata=0)
        del arr
    else:                                   # gigante -> por-polígono RAM-safe
        stats=zonal_stats(geoms,COG.format(ano=ano),categorical=True,nodata=0)
    upd=[]; mpasto=0.0
    for f,st,b in zip(feats,stats,bb):
        car=f["properties"].get("cod_imovel"); lat=b[4]
        ph=(res_x*111320*math.cos(math.radians(lat)))*(res_y*111320)/10000
        np_=st.get(PASTAGEM,0); ntot=sum(st.values()) or 1
        pasto=np_*ph; mpasto+=pasto
        upd.append((round(pasto,2),round(np_/ntot,4),car))
    cn=db(); cur=cn.cursor()
    cur.executemany("""UPDATE prospeccao.imovel_rural
        SET area_pasto_ha=%s, cobertura_pasto_mapbiomas=%s, coletado_em=now()
        WHERE codigo_car=%s""", upd)
    cn.commit()
    open(done,"w").write(str(len(feats)))
    return (ibge, nome, len(feats), mpasto)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ano", type=int, default=2024)
    ap.add_argument("--win-mp", type=float, default=60.0)
    ap.add_argument("--ufs", default="")
    a=ap.parse_args()
    pw=os.environ.get("PGPASSWORD") or os.environ.get("POSTGRES_PASSWORD")
    cn=psycopg2.connect(host="127.0.0.1",port=5432,dbname="wins_agro",user="postgres",password=pw)
    cur=cn.cursor()
    where=""
    if a.ufs:
        ufs=",".join("'%s'"%u.strip().upper() for u in a.ufs.split(","))
        where=f"WHERE upper(uf) IN ({ufs})"
    cur.execute(f"""SELECT DISTINCT i.codigo_ibge_mun, lower(i.uf),
                     (SELECT nome FROM referencia.municipio m WHERE m.codigo_ibge=i.codigo_ibge_mun::integer)
                    FROM prospeccao.imovel_rural i {where}
                    ORDER BY 1""")
    muns=[r for r in cur.fetchall() if r[0]]
    cn.close()
    pend=[m for m in muns if not os.path.exists(f"{DONEDIR}/{m[0]}.done")]
    print(f"== NACIONAL pasto/fazenda — {len(muns)} municípios ({len(pend)} pendentes) "
          f"| {a.workers} workers | MapBiomas {a.ano} ==", flush=True)
    t0=time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        futs={ex.submit(proc_mun,ib,uf,nm,a.ano,a.win_mp):(ib,nm) for ib,uf,nm in pend}
        for fu in as_completed(futs):
            ib,nm=futs[fu]
            try:
                r=fu.result()
                if r is None: continue
                _,_,nf,mp=r
                with _lock:
                    _stats["mun"]+=1; _stats["far"]+=nf; _stats["pasto"]+=mp
                    n=_stats["mun"]
                if n%20==0 or nf>3000:
                    el=time.time()-t0; rate=_stats["far"]/el if el else 0
                    print(f"[{n}/{len(pend)}] {nm}/{ib}: {nf} faz · "
                          f"acum {_stats['far']:,} faz, {_stats['pasto']/1e6:.2f} Mha pasto "
                          f"· {rate:.0f} faz/s", flush=True)
            except Exception as e:
                with _lock: _stats["err"]+=1
                print(f"[ERR] {nm}/{ib}: {type(e).__name__}: {str(e)[:120]}", flush=True)
    print(f"\n=== NACIONAL done: {_stats['mun']} munic, {_stats['far']:,} fazendas, "
          f"{_stats['pasto']/1e6:.2f} Mha pasto, {_stats['err']} erros ===", flush=True)

if __name__=="__main__":
    main()
