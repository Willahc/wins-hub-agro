"""Mede endpoints read-only no staging; requer cookie em HARVEST_COOKIE."""
import json, os, statistics, time, urllib.request

base = os.getenv("STAGING_URL", "http://127.0.0.1:18080")
farm = os.getenv("FARM_UUID", "f0000000-0000-4000-8000-000000000001")
cookie = os.environ["HARVEST_COOKIE"]
cases = {"dashboard":("dashboard", None, 50), "listagem":("plans?limit=25", None, 50),
         "capacidade":("dashboard", None, 20),
         "simulação":("simulate", {"name":"Performance","main_crop":"milho","purpose":"silagem",
            "expected_start_date":"2026-07-20","expected_end_date":"2026-07-22",
            "expected_field_loss_pct":"5","expected_ensiling_loss_pct":"8","notes":"",
            "areas":[{"name":"A","crop":"milho","area_ha":"20","expected_yield_t_ha":"40","expected_dm_pct":"35"}],
            "allocations":[]}, 50)}
for label, (suffix, payload, count) in cases.items():
    values=[]
    for _ in range(count):
        data=json.dumps(payload).encode() if payload else None
        req=urllib.request.Request(f"{base}/api/v2/farms/{farm}/harvest-silos/{suffix}", data=data,
            headers={"Cookie":cookie, "Content-Type":"application/json"})
        start=time.perf_counter(); urllib.request.urlopen(req, timeout=5).read(); values.append((time.perf_counter()-start)*1000)
    values.sort(); p95=values[max(0, int(len(values)*.95)-1)]
    print(f"{label}: mediana={statistics.median(values):.2f}ms p95={p95:.2f}ms n={len(values)}")
