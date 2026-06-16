#!/usr/bin/env python3
"""
Viability test: geocode RFB address of rural CNPJs -> match to nearest CAR centroid
in same municipality. READ-ONLY DB + Nominatim calls. Does NOT write anything.
"""
import os, time, math, json, sys
import httpx
import psycopg2
import psycopg2.extras

DB = dict(host=os.environ["DB_HOST"], port=os.environ["DB_PORT"],
          dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
          password=os.environ["POSTGRES_PASSWORD"])

UA = "WiNS-Agro-GIS-viability-test/1.0 (williamvnvn@gmail.com)"
NOMINATIM = "https://nominatim.openstreetmap.org/search"

SN_TOKENS = ("", "S/N", "SN", "S N", "SEM NUMERO", "SEM NÚMERO", "S/Nº", "SNº", "0")

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dlmb/2)**2
    return 2*R*math.asin(math.sqrt(a))

def has_real_number(num):
    return (num or "").strip().upper() not in SN_TOKENS

def build_query(row):
    """Build a Nominatim query string from RFB address parts."""
    parts = []
    tl = (row["tipo_logradouro"] or "").strip()
    log = (row["logradouro"] or "").strip()
    num = (row["numero"] or "").strip()
    street = f"{tl} {log}".strip()
    if has_real_number(row["numero"]):
        street = f"{street}, {num}".strip()
    if street:
        parts.append(street)
    if row["bairro"]:
        parts.append(row["bairro"].strip())
    if row["municipio_nome"]:
        parts.append(row["municipio_nome"].strip())
    if row["uf"]:
        parts.append(row["uf"].strip())
    return ", ".join(parts)

def _one(client, q):
    params = {"format": "jsonv2", "q": q, "countrycodes": "br", "limit": 1,
              "addressdetails": 1}
    r = client.get(NOMINATIM, params=params, headers={"User-Agent": UA}, timeout=30)
    if r.status_code != 200:
        return None, f"http_{r.status_code}"
    js = r.json()
    if not js:
        return None, "no_result"
    return js[0], None

def build_queries(row):
    """Return ordered list of (tier, query) to try, most specific first."""
    tl = (row["tipo_logradouro"] or "").strip()
    log = (row["logradouro"] or "").strip()
    num = (row["numero"] or "").strip()
    bairro = (row["bairro"] or "").strip()
    mun = (row["municipio_nome"] or "").strip()
    uf = (row["uf"] or "").strip()
    street = f"{tl} {log}".strip()
    street_num = f"{street}, {num}".strip() if has_real_number(num) else street
    out = []
    if street and bairro:
        out.append(("full", f"{street_num}, {bairro}, {mun}, {uf}"))
    if street:
        out.append(("street_city", f"{street_num}, {mun}, {uf}"))
    if bairro and bairro.upper() not in ("ZONA RURAL","AREA RURAL","RURAL","ÁREA RURAL"):
        out.append(("bairro_city", f"{bairro}, {mun}, {uf}"))
    # dedupe preserving order
    seen=set(); res=[]
    for t,q in out:
        if q not in seen: seen.add(q); res.append((t,q))
    return res

def geocode(client, row):
    """Try tiers; return (result, tier, err)."""
    last_err = "no_query"
    for tier, q in build_queries(row):
        res, err = _one(client, q)
        time.sleep(1.1)
        if res:
            return res, tier, q, None
        last_err = err
    return None, None, None, last_err

def classify_plausibility(result):
    """A result is 'city-center' if Nominatim resolved only to an administrative
    place (city/municipality/state) rather than a road/house/locality."""
    cat = result.get("category") or result.get("class")
    typ = result.get("type")
    addrtype = result.get("addresstype")
    # place=city/town/municipality/administrative -> city centroid (vague)
    city_like = {"city", "town", "municipality", "administrative", "state",
                 "county", "village", "suburb", "region"}
    if addrtype in city_like or typ in city_like or cat == "boundary":
        return "city_center"
    # road / house_number / hamlet / isolated_dwelling / farm -> plausible specific
    specific = {"road", "house", "residential", "farm", "hamlet",
                "isolated_dwelling", "neighbourhood", "locality", "house_number",
                "tertiary", "secondary", "primary", "track", "unclassified",
                "construction", "yes"}
    if cat in ("highway", "place", "building", "amenity") or typ in specific:
        return "plausible"
    return "other"

def main():
    conn = psycopg2.connect(**DB)
    conn.set_session(readonly=True, autocommit=True)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Stratified sample: leads (fazenda_nacional) joined to RFB address.
    # Stratum A: real street number. Stratum B: s/n. Vary UF.
    sample = []
    # Stratum A — real number, spread across UFs
    cur.execute("""
        WITH base AS (
          SELECT e.cnpj_basico, e.tipo_logradouro, e.logradouro, e.numero,
                 e.bairro, e.cep, e.municipio_nome, e.uf,
                 e.municipio AS cod_mun_rfb,
                 row_number() OVER (PARTITION BY e.uf ORDER BY md5(e.cnpj_basico||'a')) rn
          FROM prospeccao.fazenda_nacional f
          JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico=f.cnpj_basico
          WHERE e.cnae_fiscal_principal IN ('0151201','0151202')
            AND upper(coalesce(e.numero,'')) NOT IN ('','S/N','SN','S N','SEM NUMERO','SEM NÚMERO','S/Nº','SNº','0')
            AND e.logradouro IS NOT NULL
        )
        SELECT * FROM base WHERE rn<=8 ORDER BY uf, rn LIMIT 60;
    """)
    rows_a = cur.fetchall()
    for r in rows_a: r["stratum"]="A_com_numero"
    sample += rows_a

    # Stratum B — s/n (the common case)
    cur.execute("""
        WITH base AS (
          SELECT e.cnpj_basico, e.tipo_logradouro, e.logradouro, e.numero,
                 e.bairro, e.cep, e.municipio_nome, e.uf,
                 e.municipio AS cod_mun_rfb,
                 row_number() OVER (PARTITION BY e.uf ORDER BY md5(e.cnpj_basico||'b')) rn
          FROM prospeccao.fazenda_nacional f
          JOIN cnpj.estabelecimento_rural e ON e.cnpj_basico=f.cnpj_basico
          WHERE e.cnae_fiscal_principal IN ('0151201','0151202')
            AND upper(coalesce(e.numero,'')) IN ('','S/N','SN','S N','SEM NUMERO','SEM NÚMERO','S/Nº','SNº','0')
            AND e.logradouro IS NOT NULL
        )
        SELECT * FROM base WHERE rn<=8 ORDER BY uf, rn LIMIT 60;
    """)
    rows_b = cur.fetchall()
    for r in rows_b: r["stratum"]="B_sem_numero"
    sample += rows_b

    print(f"# Amostra total: {len(sample)} (A com_numero={len(rows_a)}, B sem_numero={len(rows_b)})", file=sys.stderr)

    # municipio code in RFB is 4-digit TOM code, NOT IBGE. We need IBGE to join CAR.
    # We'll resolve nearest CAR by querying imovel_rural using the IBGE code derived
    # from the geocoded result's municipality if needed; but simpler: use a mapping
    # from RFB municipio TOM -> IBGE. Check if such mapping exists; else use UF+name.
    results = []
    client = httpx.Client()
    for i, r in enumerate(sample):
        try:
            res, tier, q, err = geocode(client, r)
        except Exception as e:
            res, tier, q, err = None, None, None, f"exc_{type(e).__name__}"
        rec = {"cnpj_basico": r["cnpj_basico"], "uf": r["uf"],
               "municipio": r["municipio_nome"], "stratum": r["stratum"],
               "query": q, "tier": tier, "cep": r["cep"]}
        if res:
            lat = float(res["lat"]); lon = float(res["lon"])
            cls = classify_plausibility(res)
            rec.update(geocoded=True, lat=lat, lon=lon,
                       osm_type=res.get("type"), osm_cat=res.get("category") or res.get("class"),
                       addrtype=res.get("addresstype"), plausibility=cls)
        else:
            rec.update(geocoded=False, err=err, plausibility="failed")
        results.append(rec)
        if (i+1) % 20 == 0:
            print(f"  ...{i+1}/{len(sample)} processed", file=sys.stderr)

    # Now nearest-CAR for plausible/city ones. Need IBGE municipality code.
    # Resolve nearest CAR centroid by UF + municipio name match to codigo_ibge_mun
    # via a municipio lookup. We'll match on the CAR table's own municipio/uf text.
    for rec in results:
        if not rec.get("geocoded"):
            continue
        lat, lon = rec["lat"], rec["lon"]
        # find nearest CAR centroid within same municipio (uf + name), bounding box first
        cur.execute("""
            SELECT codigo_car, latitude, longitude, area_total_ha,
                   codigo_ibge_mun
            FROM prospeccao.imovel_rural
            WHERE fonte_principal='SICAR'
              AND uf=%s
              AND latitude BETWEEN %s-0.45 AND %s+0.45
              AND longitude BETWEEN %s-0.45 AND %s+0.45
            ORDER BY (latitude-%s)^2 + (longitude-%s)^2
            LIMIT 1;
        """, (rec["uf"], lat, lat, lon, lon, lat, lon))
        car = cur.fetchone()
        if car and car["latitude"] is not None:
            d = haversine_km(lat, lon, float(car["latitude"]), float(car["longitude"]))
            rec["nearest_car_km"] = round(d, 3)
            rec["nearest_car_area_ha"] = float(car["area_total_ha"]) if car["area_total_ha"] else None
            rec["nearest_car_codigo"] = car["codigo_car"]
        else:
            rec["nearest_car_km"] = None

    with open("/tmp/geomatch_results.json", "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    print("WROTE /tmp/geomatch_results.json", file=sys.stderr)

    # ---- Summary ----
    def summarize(rs, label):
        n = len(rs)
        if n == 0:
            print(f"\n## {label}: 0"); return
        geo = [r for r in rs if r.get("geocoded")]
        plaus = [r for r in geo if r["plausibility"]=="plausible"]
        city = [r for r in geo if r["plausibility"]=="city_center"]
        oth = [r for r in geo if r["plausibility"]=="other"]
        print(f"\n## {label} (n={n})")
        print(f"  geocodou:        {len(geo)}/{n} = {100*len(geo)/n:.0f}%")
        print(f"  plausível(rua/casa/fazenda): {len(plaus)}/{n} = {100*len(plaus)/n:.0f}%")
        print(f"  city_center(centro cidade):  {len(city)}/{n} = {100*len(city)/n:.0f}%")
        print(f"  outro:           {len(oth)}/{n} = {100*len(oth)/n:.0f}%")
        # distance distribution for PLAUSIBLE ones
        dists = sorted([r["nearest_car_km"] for r in plaus if r.get("nearest_car_km") is not None])
        if dists:
            med = dists[len(dists)//2]
            p25 = dists[len(dists)//4]
            p75 = dists[(3*len(dists))//4]
            close = [d for d in dists if d <= 1.0]
            print(f"  dist plausível->CAR (km): p25={p25:.2f} med={med:.2f} p75={p75:.2f} min={dists[0]:.2f} max={dists[-1]:.2f}")
            print(f"  plausível com CAR <=1km: {len(close)}/{len(plaus)}")
        # distance for city_center (to show they land far / random)
        cdists = sorted([r["nearest_car_km"] for r in city if r.get("nearest_car_km") is not None])
        if cdists:
            print(f"  dist city_center->CAR (km): med={cdists[len(cdists)//2]:.2f}")

    summarize(results, "TOTAL")
    summarize([r for r in results if r["stratum"]=="A_com_numero"], "A — com número")
    summarize([r for r in results if r["stratum"]=="B_sem_numero"], "B — sem número (s/n)")

if __name__ == "__main__":
    main()
