import sys
import requests

BASE_URL = "http://127.0.0.1:18080"
session = requests.Session()

# 1. Login
print("1. Logging in...")
login_res = session.post(f"{BASE_URL}/login", data={"email": "mari@winshubagro.cloud", "password": "test"})
token = session.cookies.get("access_token")
if not token:
    print("Failed to login, no token set!")
    sys.exit(1)

headers = {"Cookie": f"access_token={token}"}
farm_uuid = "f0000000-0000-4000-8000-000000000001"

# 2. Get facilities
print("2. Fetching facilities...")
fac_res = session.get(f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/facilities", headers=headers)
facilities = fac_res.json()["items"]
if not facilities:
    print("No facilities found!")
    sys.exit(1)
fac_uuid = facilities[0]["public_id"]

# 3. Create a lot with 5000 kg, MS 35%, utilization 90%
print("3. Creating lot with 5000 kg, MS 35%, utilization 90%...")
lot_payload = {
    "name": "Lote Autonomia Teste",
    "feed_type": "silagem_milho",
    "facility_uuid": fac_uuid,
    "initial_quantity_natural_kg": "5000",
    "dry_matter_pct": "35",
    "utilization_pct": "90",
}
create_lot_res = session.post(f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/lots", json=lot_payload, headers=headers)
if create_lot_res.status_code not in (200, 201):
    print("Failed to create lot:", create_lot_res.json())
    sys.exit(1)

lot = create_lot_res.json()
lot_uuid = lot["public_id"]
print(f"✓ Created lot {lot_uuid}")

# 4. Verify lot usable DM
print("4. Verifying lot usable DM is 1575.0 kg...")
lot_detail_res = session.get(f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/lots/{lot_uuid}", headers=headers)
lot_details = lot_detail_res.json()
print("   Usable DM (recalculated by backend):", lot_details.get("current_usable_dm_kg"))
assert float(lot_details.get("current_usable_dm_kg")) == 1575.0, "Usable DM is not 1575 kg!"
print("✓ Usable DM is correct (1575.0 kg)")

# 5. Fetch autonomy sources
print("5. Verifying lot is present in autonomy-sources...")
sources_res = session.get(f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/autonomy-sources", headers=headers)
sources = sources_res.json()
source_item = next((s for s in sources if s["source_public_id"] == lot_uuid), None)
if not source_item:
    print("Lot not found in autonomy-sources!")
    sys.exit(1)

print("   Autonomy source item usable DM:", source_item.get("usable_dm_kg"))
assert float(source_item.get("usable_dm_kg")) == 1575.0, "Source item usable DM is not 1575 kg!"
print("✓ Autonomy source item usable DM is correct (1575.0 kg)")

# 6. Import to Autonomia Alimentar (POST to food-autonomy feeds endpoint)
print("6. Importing to Autonomia Alimentar...")
feed_payload = {
    "feed_type": source_item["feed_type"],
    "name": source_item["name"],
    "quantity_natural_kg": "5000",
    "dry_matter_pct": source_item["dry_matter_pct"],
    "utilization_pct": source_item["utilization_pct"],
    "notes": "Importado manualmente"
}
import_res = session.post(f"{BASE_URL}/api/v2/farms/{farm_uuid}/food-autonomy/feeds", json=feed_payload, headers=headers)
if import_res.status_code not in (200, 201):
    print("Failed to import to Autonomia:", import_res.json())
    sys.exit(1)

imported_feed = import_res.json()
print(f"✓ Imported feed successfully: {imported_feed['public_id']}")
print("   Imported feed usable DM (recalculated by backend):", imported_feed.get("usable_dm_kg"))
assert float(imported_feed.get("usable_dm_kg")) == 1575.0, "Imported feed usable DM is not 1575 kg!"
print("✓ Imported feed usable DM is correct (1575.0 kg)")

# 7. Confirm that the lot's actual balance in silagem-estoques was NOT reduced
print("7. Checking that the original lot balance was NOT reduced...")
lot_detail_res2 = session.get(f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/lots/{lot_uuid}", headers=headers)
lot_details2 = lot_detail_res2.json()
print("   Lot current balance:", lot_details2.get("current_quantity_natural_kg"))
assert float(lot_details2.get("current_quantity_natural_kg")) == 5000.0, "Lot balance was reduced!"
print("✓ Lot balance remains exactly 5000.0 kg")

# Clean up
session.delete(f"{BASE_URL}/api/v2/farms/{farm_uuid}/feed-inventory/lots/{lot_uuid}", headers=headers)
print("Cleaned up created lot.")
print("\n=== Validation Successful ===")
