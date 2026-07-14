import sys
import time
import requests

BASE_URL = "http://127.0.0.1:18080"
session = requests.Session()

# Login
login_res = session.post(f"{BASE_URL}/login", data={"email": "mari@winshubagro.cloud", "password": "test"})
token = session.cookies.get("access_token")
if not token:
    print("Failed to login")
    sys.exit(1)

headers = {"Cookie": f"access_token={token}"}
farm_uuid = "f0000000-0000-4000-8000-000000000001"

# Get a lot_uuid to use in Histórico endpoint
lots_res = session.get(f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/lots", headers=headers)
lots = lots_res.json().get("items", [])
if not lots:
    print("No lots found to run performance tests!")
    sys.exit(1)
lot_uuid = lots[0]["public_id"]

def run_performance_for_endpoint(name, url):
    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        res = session.get(url, headers=headers)
        t1 = time.perf_counter()
        if res.status_code != 200:
            print(f"Request to {url} failed with {res.status_code}: {res.text}")
            sys.exit(1)
        latencies.append((t1 - t0) * 1000)
    
    latencies.sort()
    n = len(latencies)
    median = latencies[n // 2]
    p95 = latencies[int(n * 0.95)]
    print(f"{name}: Mediana = {median:.2f} ms, p95 = {p95:.2f} ms")
    return median, p95

print("=== Performance Test (50 iterations per endpoint) ===")
run_performance_for_endpoint("Dashboard", f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/dashboard")
run_performance_for_endpoint("Listagens (Lotes)", f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/lots")
run_performance_for_endpoint("Autonomy Sources", f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/autonomy-sources")
run_performance_for_endpoint("Histórico", f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/lots/{lot_uuid}/movements")
