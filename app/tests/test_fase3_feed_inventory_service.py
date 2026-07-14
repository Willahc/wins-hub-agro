"""Testes de serviço de Estoque de Ração — mocks e lógica de negócio."""
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from domain.feed_inventory import (
    FORMULA_VERSION, LotStatus, MovementType, FacilityType, FeedType,
    calculate_physical_dm, calculate_usable_dm, reconcile_balance,
)
from domain.foundation import RecordStatus


class MockFeedInventoryRepository:
    def __init__(self):
        self.facilities = []
        self.lots = []
        self.movements = []
        self._next_id = 1
        self._seen_request_ids = set()

    def find_farm(self, farm_public_id):
        if str(farm_public_id) == "00000000-0000-0000-0000-000000000002":
            return {"id": 102, "public_id": str(farm_public_id),
                    "organization_id": 2, "name": "Outro Tenant", "status": "active"}
        return {"id": 100, "public_id": str(farm_public_id),
                "organization_id": 1, "name": "Fazenda Teste", "status": "active"}

    def find_membership(self, user_id, org_id):
        return {"id": 10, "public_id": str(uuid4()), "organization_id": org_id,
                "role": "manager", "status": "active"}

    def find_farm_access(self, membership_id, farm_id):
        return {"id": 200, "access_level": "manage", "status": "active"}

    def find_resource_scope(self, user_id, resource_type, resource_id):
        return None

    def create_facility(self, data, user_id):
        req_id = data.get("request_id", "")
        if req_id and req_id in self._seen_request_ids:
            raise ValueError("duplicate_request_id")
        if req_id:
            self._seen_request_ids.add(req_id)
        self._next_id += 1
        facility = {
            "id": self._next_id, "public_id": data["public_id"],
            "organization_id": data["organization_id"],
            "farm_id": data["farm_id"],
            "name": data["name"],
            "code": data.get("code", ""),
            "facility_type": data["facility_type"],
            "capacity_natural_kg": data["capacity_natural_kg"],
            "preferred_display_unit": data.get("preferred_display_unit", "kg"),
            "location_description": data.get("location_description", ""),
            "active": data.get("active", True),
            "notes": data.get("notes", ""),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self.facilities.append(facility)
        return {"id": facility["id"], "public_id": facility["public_id"]}

    def get_facility(self, public_id):
        for f in self.facilities:
            if str(f["public_id"]) == str(public_id):
                return f
        return None

    def list_facilities(self, farm_id, limit=25, offset=0):
        items = [f for f in self.facilities if f["farm_id"] == farm_id]
        return items[offset:offset + limit]

    def count_facilities(self, farm_id):
        return len([f for f in self.facilities if f["farm_id"] == farm_id])

    def update_facility(self, facility_id, data, user_id):
        for f in self.facilities:
            if f["id"] == facility_id:
                f.update(data)
                f["updated_at"] = datetime.now(timezone.utc)
                return {"id": facility_id, "public_id": data["public_id"]}
        return None

    def archive_facility(self, facility_id, user_id, org_id, farm_id, public_id, request_id=""):
        for f in self.facilities:
            if f["id"] == facility_id:
                f["active"] = False
                return

    def count_active_lots_for_facility(self, facility_id):
        return len([l for l in self.lots
                    if l.get("facility_id") == facility_id
                    and l.get("status") in ("available", "reserved", "opened")])

    def create_lot(self, data, movement_data, user_id):
        self._next_id += 1
        lot = {
            "id": self._next_id, "public_id": data["public_id"],
            "organization_id": data["organization_id"],
            "farm_id": data["farm_id"],
            "facility_id": data["facility_id"],
            "name": data["name"],
            "feed_type": data["feed_type"],
            "status": data["status"],
            "initial_quantity_natural_kg": data["initial_quantity_natural_kg"],
            "initial_total_cost": data.get("initial_total_cost"),
            "dry_matter_pct": data["dry_matter_pct"],
            "utilization_pct": data["utilization_pct"],
            "balance_natural_kg": data["balance_natural_kg"],
            "planned_daily_use_dm_kg": data.get("planned_daily_use_dm_kg"),
            "entry_date": data.get("entry_date", date.today()),
            "notes": data.get("notes", ""),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self.lots.append(lot)

        if movement_data:
            self._next_id += 1
            movement = {
                "id": self._next_id, "public_id": movement_data["public_id"],
                "lot_id": lot["id"],
                "lot_public_id": str(lot["public_id"]),
                "organization_id": movement_data["organization_id"],
                "farm_id": movement_data["farm_id"],
                "movement_type": movement_data["movement_type"],
                "quantity_natural_kg": movement_data["quantity_natural_kg"],
                "dry_matter_pct": movement_data.get("dry_matter_pct"),
                "quantity_dm_kg": movement_data.get("quantity_dm_kg"),
                "unit_cost": movement_data.get("unit_cost"),
                "total_cost": movement_data.get("total_cost"),
                "loss_reason": movement_data.get("loss_reason"),
                "balance_after_natural_kg": movement_data.get("balance_after_natural_kg"),
                "reference_date": movement_data.get("reference_date"),
                "notes": movement_data.get("notes", ""),
                "created_by_user_id": movement_data.get("created_by_user_id"),
                "created_at": datetime.now(timezone.utc),
            }
            self.movements.append(movement)

        return {"id": lot["id"], "public_id": lot["public_id"]}

    def get_lot(self, public_id):
        for l in self.lots:
            if str(l["public_id"]) == str(public_id):
                return l
        return None

    def list_lots(self, farm_id, limit=25, offset=0, filters=None):
        items = [l for l in self.lots if l["farm_id"] == farm_id]
        if filters:
            if filters.get("facility_id"):
                items = [l for l in items
                         if str(l.get("facility_id")) == str(filters["facility_id"])]
            if filters.get("feed_type"):
                items = [l for l in items
                         if l.get("feed_type") == filters["feed_type"]]
            if filters.get("status"):
                items = [l for l in items
                         if l.get("status") == filters["status"]]
            if filters.get("search"):
                items = [l for l in items
                         if filters["search"].lower() in l.get("name", "").lower()]
        return items[offset:offset + limit]

    def list_active_lots(self, farm_id):
        return [l for l in self.lots if l["farm_id"] == farm_id
                and l.get("status") in ("available", "reserved", "opened")]

    def count_lots(self, farm_id, filters=None):
        return len(self.list_lots(farm_id, limit=9999, offset=0,
                                  filters=filters))

    def update_lot(self, lot_id, data, user_id, request_id=""):
        for l in self.lots:
            if l["id"] == lot_id:
                l.update(data)
                l["updated_at"] = datetime.now(timezone.utc)
                return {"id": lot_id, "public_id": l["public_id"]}
        return None

    def archive_lot(self, lot_id, user_id, org_id, farm_id, public_id, request_id=""):
        for l in self.lots:
            if l["id"] == lot_id:
                l["status"] = LotStatus.ARCHIVED.value
                return

    def get_lot_for_update(self, lot_id):
        for l in self.lots:
            if l["id"] == lot_id:
                return l
        return None

    def update_lot_balance(self, lot_id, **kwargs):
        for l in self.lots:
            if l["id"] == lot_id:
                for k, v in kwargs.items():
                    if k in l:
                        l[k] = v
                return

    def create_movement(self, data, lot_update, lot_id, user_id):
        self._next_id += 1
        lot = None
        for l in self.lots:
            if l["id"] == lot_id:
                lot = l
                break
        util_pct = lot["utilization_pct"] if lot else 100
        phys_dm = data.get("quantity_dm_kg") or 0
        movement = {
            "id": self._next_id, "public_id": data["public_id"],
            "lot_id": lot_id,
            "lot_public_id": str(data.get("lot_public_id", "")),
            "organization_id": data["organization_id"],
            "farm_id": data["farm_id"],
            "movement_type": data["movement_type"],
            "quantity_natural_kg": data["quantity_natural_kg"],
            "dry_matter_pct": data.get("dry_matter_pct"),
            "dry_matter_pct_snapshot": data.get("dry_matter_pct"),
            "utilization_pct_snapshot": util_pct,
            "quantity_dm_kg": phys_dm,
            "physical_dm_kg": phys_dm,
            "usable_dm_kg": calculate_usable_dm(phys_dm, util_pct),
            "unit_cost": data.get("unit_cost"),
            "unit_cost_snapshot": data.get("unit_cost"),
            "total_cost": data.get("total_cost"),
            "loss_reason": data.get("loss_reason"),
            "balance_after_natural_kg": data.get("balance_after_natural_kg"),
            "reference_date": data.get("reference_date"),
            "reason": data.get("reason", ""),
            "notes": data.get("notes", ""),
            "created_by_user_id": data.get("created_by_user_id"),
            "request_id": data.get("request_id", ""),
            "created_at": datetime.now(timezone.utc),
        }
        self.movements.append(movement)

        if lot_update:
            for l in self.lots:
                if l["id"] == lot_id:
                    for k, v in lot_update.items():
                        l[k] = v
                    break

        return {"id": movement["id"], "public_id": movement["public_id"]}

    def list_movements(self, lot_id, limit=50, offset=0):
        items = [m for m in self.movements if m["lot_id"] == lot_id]
        return items[offset:offset + limit]

    def count_movements(self, lot_id):
        return len([m for m in self.movements if m["lot_id"] == lot_id])

    def get_movement(self, public_id):
        for m in self.movements:
            if str(m["public_id"]) == str(public_id):
                return m
        return None

    def find_movement_by_request_id(self, lot_id, request_id):
        if not request_id:
            return None
        for m in self.movements:
            if m["lot_id"] == lot_id and m.get("request_id") == request_id:
                return m
        return None

    def get_movements_for_reconciliation(self, lot_id):
        return [m for m in self.movements if m["lot_id"] == lot_id]

    def get_all_movements_for_lot(self, lot_id):
        return [m for m in self.movements if m["lot_id"] == lot_id]

    def get_facility_by_id(self, facility_id):
        for f in self.facilities:
            if f["id"] == facility_id:
                return f
        return None

    def get_dashboard(self, farm_id):
        lots = [l for l in self.lots if l["farm_id"] == farm_id]
        return {
            "total_lots": len(lots),
            "total_facilities": len([f for f in self.facilities if f["farm_id"] == farm_id]),
            "total_natural_kg": sum(float(l.get("balance_natural_kg", 0)) for l in lots),
            "total_physical_dm_kg": 0.0,
            "total_usable_dm_kg": 0.0,
            "total_inventory_value": 0.0,
            "available_count": sum(1 for l in lots if l["status"] == "available"),
            "opened_count": sum(1 for l in lots if l["status"] == "opened"),
            "reserved_count": 0,
            "depleted_count": 0,
            "quarantined_count": 0,
            "feed_types_summary": {},
            "recent_movements": [],
        }

    def get_autonomy_sources(self, farm_id):
        lots = [l for l in self.lots if l["farm_id"] == farm_id
                and l.get("status") in ("available", "opened", "reserved")]
        results = []
        for l in lots:
            results.append({
                "lot_public_id": str(l["public_id"]),
                "name": l["name"],
                "feed_type": l["feed_type"],
                "status": l["status"],
                "facility_id": l.get("facility_id"),
                "facility_name": "",
                "current_quantity_natural_kg": str(l.get("balance_natural_kg", 0)),
                "current_usable_dm_kg": "0",
                "dry_matter_pct": str(l.get("dry_matter_pct", 0)),
                "utilization_pct": str(l.get("utilization_pct", 100)),
                "current_inventory_value": "0",
                "cost_per_usable_dm_kg": None,
            })
        return results


class FakeAuthRepository:
    def __init__(self):
        self._users = {}
        self._memberships = {}

    def find_user_by_subject(self, subject):
        if subject in self._users:
            return self._users[subject]
        user = MagicMock()
        user.id = 1
        user.public_id = uuid4()
        user.status = RecordStatus.ACTIVE
        self._users[subject] = user
        return user

    def find_membership(self, user_id, org_id):
        return MagicMock(
            id=10, public_id=str(uuid4()),
            organization_id=org_id,
            role=MagicMock(value="manager"),
            status=RecordStatus.ACTIVE,
            is_active=lambda now: True,
        )

    def find_farm(self, farm_public_id):
        return MagicMock(
            id=100, public_id=farm_public_id,
            organization_id=1, name="Fazenda Teste",
            status=RecordStatus.ACTIVE,
        )

    def find_farm_access(self, membership_id, farm_id):
        return MagicMock(
            id=200, access_level=MagicMock(value="manage"),
            status=RecordStatus.ACTIVE,
            is_active=lambda now: True,
        )

    def find_resource_scope(self, resource_type, resource_public_id):
        return None


class TestFeedInventoryService(unittest.TestCase):
    def setUp(self):
        self.repo = MockFeedInventoryRepository()
        self.auth_repo = FakeAuthRepository()

    def test_service_instantiation(self):
        from services.feed_inventory import FeedInventoryService
        svc = FeedInventoryService(self.repo, self.auth_repo)
        self.assertIsNotNone(svc)
        self.assertEqual(svc.repository, self.repo)


class TestFacilityCRUD(unittest.TestCase):
    def setUp(self):
        self.repo = MockFeedInventoryRepository()
        self.auth_repo = FakeAuthRepository()

    def _make_facility_payload(self):
        return {
            "name": "Silo A",
            "facility_type": "silo_trincheira",
            "capacity_natural_kg": "50000",
            "notes": "",
        }

    def test_create_facility(self):
        from services.feed_inventory import FeedInventoryService
        svc = FeedInventoryService(self.repo, self.auth_repo)
        result = svc.create_facility(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_facility_payload(), request_id="req-1",
        )
        self.assertIn("public_id", result)
        self.assertEqual(result["name"], "Silo A")
        self.assertEqual(result["facility_type"], "silo_trincheira")

    def test_list_facilities(self):
        from services.feed_inventory import FeedInventoryService
        svc = FeedInventoryService(self.repo, self.auth_repo)
        for i in range(3):
            svc.create_facility(
                subject="testuser", farm_public_id=uuid4(),
                payload={**self._make_facility_payload(), "name": f"Silo {i}"},
                request_id=f"req-{i}",
            )
        result = svc.list_facilities(
            subject="testuser", farm_public_id=uuid4(),
            limit=2, offset=0, request_id="req-list",
        )
        self.assertIn("items", result)
        self.assertIn("pagination", result)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["pagination"]["total"], 3)
        self.assertTrue(result["pagination"]["has_more"])

    def test_get_facility(self):
        from services.feed_inventory import FeedInventoryService
        svc = FeedInventoryService(self.repo, self.auth_repo)
        created = svc.create_facility(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_facility_payload(), request_id="req-1",
        )
        result = svc.get_facility(
            subject="testuser", farm_public_id=uuid4(),
            facility_uuid=created["public_id"], request_id="req-2",
        )
        self.assertEqual(result["public_id"], created["public_id"])
        self.assertEqual(result["name"], "Silo A")

    def test_update_facility(self):
        from services.feed_inventory import FeedInventoryService
        svc = FeedInventoryService(self.repo, self.auth_repo)
        created = svc.create_facility(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_facility_payload(), request_id="req-1",
        )
        result = svc.update_facility(
            subject="testuser", farm_public_id=uuid4(),
            facility_uuid=created["public_id"],
            payload={"name": "Silo B", "facility_type": "galpao",
                     "capacity_natural_kg": "60000"},
            request_id="req-2",
        )
        self.assertEqual(result["name"], "Silo B")
        self.assertEqual(result["facility_type"], "galpao")

    def test_archive_facility(self):
        from services.feed_inventory import FeedInventoryService
        svc = FeedInventoryService(self.repo, self.auth_repo)
        created = svc.create_facility(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_facility_payload(), request_id="req-1",
        )
        svc.archive_facility(
            subject="testuser", farm_public_id=uuid4(),
            facility_uuid=created["public_id"], request_id="req-2",
        )
        updated = self.repo.get_facility(created["public_id"])
        self.assertFalse(updated["active"])


class TestLotCRUD(unittest.TestCase):
    def setUp(self):
        self.repo = MockFeedInventoryRepository()
        self.auth_repo = FakeAuthRepository()
        from services.feed_inventory import FeedInventoryService
        self.svc = FeedInventoryService(self.repo, self.auth_repo)
        self.farm_id = uuid4()
        self.facility = self.svc.create_facility(
            subject="testuser", farm_public_id=self.farm_id,
            payload={"name": "Silo A", "facility_type": "silo_trincheira",
                     "capacity_natural_kg": "50000"},
            request_id="req-fac",
        )

    def _make_lot_payload(self):
        return {
            "name": "Lote 1",
            "feed_type": "silagem_milho",
            "facility_id": self.facility["public_id"],
            "initial_quantity_natural_kg": "10000",
            "dry_matter_pct": "35",
            "utilization_pct": "90",
            "initial_total_cost": "12000",
            "notes": "",
        }

    def test_create_lot_with_initial_balance(self):
        result = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload=self._make_lot_payload(), request_id="req-1",
        )
        self.assertIn("public_id", result)
        self.assertEqual(result["name"], "Lote 1")
        self.assertEqual(result["feed_type"], "silagem_milho")
        movements = self.repo.list_movements(
            self.repo.get_lot(result["public_id"])["id"]
        )
        self.assertEqual(len(movements), 1)
        self.assertEqual(movements[0]["movement_type"], MovementType.INITIAL_BALANCE.value)

    def test_list_lots(self):
        self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload=self._make_lot_payload(), request_id="req-1",
        )
        result = self.svc.list_lots(
            subject="testuser", farm_public_id=self.farm_id,
            limit=25, offset=0, request_id="req-list",
        )
        self.assertIn("items", result)
        self.assertEqual(len(result["items"]), 1)

    def test_list_lots_with_filters(self):
        self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload=self._make_lot_payload(), request_id="req-1",
        )
        self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload={
                "name": "Lote 2", "feed_type": "feno",
                "facility_id": self.facility["public_id"],
                "initial_quantity_natural_kg": "5000",
                "dry_matter_pct": "85", "utilization_pct": "95",
                "initial_total_cost": "8000", "notes": "",
            }, request_id="req-2",
        )
        result_all = self.svc.list_lots(
            subject="testuser", farm_public_id=self.farm_id,
            limit=25, offset=0, request_id="req-list-all",
        )
        self.assertEqual(len(result_all["items"]), 2)
        self.assertEqual(result_all["pagination"]["total"], 2)

        result_silagem = self.svc.list_lots(
            subject="testuser", farm_public_id=self.farm_id,
            limit=25, offset=0, feed_type="silagem_milho",
            request_id="req-list-silagem",
        )
        self.assertEqual(len(result_silagem["items"]), 1)
        self.assertEqual(result_silagem["items"][0]["feed_type"], "silagem_milho")
        self.assertEqual(result_silagem["pagination"]["total"], 1)

        result_facility = self.svc.list_lots(
            subject="testuser", farm_public_id=self.farm_id,
            limit=25, offset=0,
            facility_uuid=self.facility["public_id"],
            request_id="req-list-fac",
        )
        self.assertEqual(len(result_facility["items"]), 2)
        self.assertEqual(result_facility["pagination"]["total"], 2)

        result_feno = self.svc.list_lots(
            subject="testuser", farm_public_id=self.farm_id,
            limit=25, offset=0, feed_type="feno",
            request_id="req-list-feno",
        )
        self.assertEqual(len(result_feno["items"]), 1)
        self.assertEqual(result_feno["items"][0]["feed_type"], "feno")

        result_pagination = self.svc.list_lots(
            subject="testuser", farm_public_id=self.farm_id,
            limit=1, offset=0, feed_type="silagem_milho",
            request_id="req-list-page",
        )
        self.assertEqual(len(result_pagination["items"]), 1)
        self.assertEqual(result_pagination["pagination"]["total"], 1)
        self.assertFalse(result_pagination["pagination"]["has_more"])

        farm_id = self.repo.get_facility(self.facility["public_id"])["farm_id"]
        total_with_filter = self.repo.count_lots(
            farm_id, filters={"feed_type": "silagem_milho"},
        )
        self.assertEqual(total_with_filter, 1)
        total_no_filter = self.repo.count_lots(farm_id, filters=None)
        self.assertEqual(total_no_filter, 2)

    def test_get_lot(self):
        created = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload=self._make_lot_payload(), request_id="req-1",
        )
        result = self.svc.get_lot(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=created["public_id"], request_id="req-2",
        )
        self.assertEqual(result["public_id"], created["public_id"])

    def test_update_lot_metadata(self):
        created = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload=self._make_lot_payload(), request_id="req-1",
        )
        result = self.svc.update_lot(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=created["public_id"],
            payload={"name": "Lote Atualizado", "notes": "atualizado"},
            request_id="req-2",
        )
        self.assertEqual(result["name"], "Lote Atualizado")

    def test_archive_lot(self):
        created = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload=self._make_lot_payload(), request_id="req-1",
        )
        self.svc.archive_lot(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=created["public_id"], request_id="req-2",
        )
        updated = self.repo.get_lot(created["public_id"])
        self.assertEqual(updated["status"], LotStatus.ARCHIVED.value)


class TestMovements(unittest.TestCase):
    def setUp(self):
        self.repo = MockFeedInventoryRepository()
        self.auth_repo = FakeAuthRepository()
        from services.feed_inventory import FeedInventoryService
        self.svc = FeedInventoryService(self.repo, self.auth_repo)
        self.farm_id = uuid4()
        self.facility = self.svc.create_facility(
            subject="testuser", farm_public_id=self.farm_id,
            payload={"name": "Silo A", "facility_type": "silo_trincheira",
                     "capacity_natural_kg": "50000"},
            request_id="req-fac",
        )
        self.lot = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload={
                "name": "Lote 1", "feed_type": "silagem_milho",
                "facility_id": self.facility["public_id"],
                "initial_quantity_natural_kg": "10000",
                "dry_matter_pct": "35", "utilization_pct": "90",
                "initial_total_cost": "12000",
            },
            request_id="req-lot",
        )

    def test_entry(self):
        result = self.svc.create_movement(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=self.lot["public_id"],
            payload={"movement_type": "entry", "quantity_natural_kg": "5000"},
            request_id="req-1",
        )
        self.assertEqual(result["movement_type"], MovementType.ENTRY.value)
        self.assertEqual(Decimal(result["quantity_natural_kg"]), Decimal("5000"))

    def test_withdrawal(self):
        result = self.svc.withdraw(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=self.lot["public_id"],
            payload={"quantity_natural_kg": "1000"},
            request_id="req-1",
        )
        self.assertEqual(result["movement_type"], MovementType.WITHDRAWAL.value)

    def test_loss(self):
        result = self.svc.record_loss(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=self.lot["public_id"],
            payload={"quantity_natural_kg": "200", "loss_reason": "chuva"},
            request_id="req-1",
        )
        self.assertEqual(result["movement_type"], MovementType.LOSS.value)

    def test_adjustment_positive(self):
        result = self.svc.adjust(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=self.lot["public_id"],
            payload={"quantity_natural_kg": "500", "reason": "ajuste"},
            request_id="req-1",
        )
        self.assertEqual(result["movement_type"], MovementType.ADJUSTMENT_POSITIVE.value)

    def test_adjustment_negative(self):
        result = self.svc.adjust(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=self.lot["public_id"],
            payload={"quantity_natural_kg": "-500", "reason": "ajuste"},
            request_id="req-1",
        )
        self.assertEqual(result["movement_type"], MovementType.ADJUSTMENT_NEGATIVE.value)


class TestBalanceInvariants(unittest.TestCase):
    def setUp(self):
        self.repo = MockFeedInventoryRepository()
        self.auth_repo = FakeAuthRepository()
        from services.feed_inventory import FeedInventoryService
        from core.authorization import ForbiddenError
        self.svc = FeedInventoryService(self.repo, self.auth_repo)
        self.ForbiddenError = ForbiddenError
        self.farm_id = uuid4()
        self.facility = self.svc.create_facility(
            subject="testuser", farm_public_id=self.farm_id,
            payload={"name": "Silo A", "facility_type": "silo_trincheira",
                     "capacity_natural_kg": "50000"},
            request_id="req-fac",
        )

    def test_insufficient_balance_blocked(self):
        lot = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload={
                "name": "Lote 1", "feed_type": "silagem_milho",
                "facility_id": self.facility["public_id"],
                "initial_quantity_natural_kg": "1000",
                "dry_matter_pct": "35", "utilization_pct": "90",
            },
            request_id="req-lot",
        )
        with self.assertRaises(self.ForbiddenError) as ctx:
            self.svc.withdraw(
                subject="testuser", farm_public_id=self.farm_id,
                lot_uuid=lot["public_id"],
                payload={"quantity_natural_kg": "2000"},
                request_id="req-1",
            )
        self.assertEqual(ctx.exception.code, "insufficient_balance")

    def test_depleted_lot_blocked(self):
        lot = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload={
                "name": "Lote 1", "feed_type": "silagem_milho",
                "facility_id": self.facility["public_id"],
                "initial_quantity_natural_kg": "1000",
                "dry_matter_pct": "35", "utilization_pct": "90",
            },
            request_id="req-lot",
        )
        self.svc.withdraw(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=lot["public_id"],
            payload={"quantity_natural_kg": "1000"},
            request_id="req-1",
        )
        updated_lot = self.repo.get_lot(lot["public_id"])
        self.assertEqual(updated_lot["status"], LotStatus.DEPLETED.value)

    def test_archived_lot_blocked(self):
        lot = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload={
                "name": "Lote 1", "feed_type": "silagem_milho",
                "facility_id": self.facility["public_id"],
                "initial_quantity_natural_kg": "1000",
                "dry_matter_pct": "35", "utilization_pct": "90",
            },
            request_id="req-lot",
        )
        self.svc.archive_lot(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=lot["public_id"], request_id="req-archive",
        )
        with self.assertRaises(self.ForbiddenError) as ctx:
            self.svc.withdraw(
                subject="testuser", farm_public_id=self.farm_id,
                lot_uuid=lot["public_id"],
                payload={"quantity_natural_kg": "100"},
                request_id="req-1",
            )
        self.assertEqual(ctx.exception.code, "lot_archived")


class TestIdempotency(unittest.TestCase):
    def setUp(self):
        self.repo = MockFeedInventoryRepository()
        self.auth_repo = FakeAuthRepository()

    def test_duplicate_request_id_raises(self):
        from services.feed_inventory import FeedInventoryService
        from core.authorization import ForbiddenError
        svc = FeedInventoryService(self.repo, self.auth_repo)
        payload = {"name": "Silo A", "facility_type": "silo_trincheira",
                   "capacity_natural_kg": "50000"}
        svc.create_facility(
            subject="testuser", farm_public_id=uuid4(),
            payload=payload, request_id="duplicate-req",
        )
        with self.assertRaises(ForbiddenError) as ctx:
            svc.create_facility(
                subject="testuser", farm_public_id=uuid4(),
                payload=payload, request_id="duplicate-req",
            )
        self.assertEqual(ctx.exception.code, "duplicate_request_id")


class TestReconciliation(unittest.TestCase):
    def setUp(self):
        self.repo = MockFeedInventoryRepository()
        self.auth_repo = FakeAuthRepository()
        from services.feed_inventory import FeedInventoryService
        self.svc = FeedInventoryService(self.repo, self.auth_repo)
        self.farm_id = uuid4()
        self.facility = self.svc.create_facility(
            subject="testuser", farm_public_id=self.farm_id,
            payload={"name": "Silo A", "facility_type": "silo_trincheira",
                     "capacity_natural_kg": "50000"},
            request_id="req-fac",
        )

    def test_reconciled_state(self):
        lot = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload={
                "name": "Lote 1", "feed_type": "silagem_milho",
                "facility_id": self.facility["public_id"],
                "initial_quantity_natural_kg": "10000",
                "dry_matter_pct": "35", "utilization_pct": "90",
            },
            request_id="req-lot",
        )
        lot_data = self.repo.get_lot(lot["public_id"])
        lot_id = lot_data["id"]
        self.repo.movements = [m for m in self.repo.movements if m["lot_id"] != lot_id]
        result = self.svc.get_reconciliation(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=lot["public_id"], request_id="req-1",
        )
        self.assertTrue(result["is_reconciled"])
        self.assertEqual(result["difference_natural_kg"], "0.00")

    def test_divergent_state(self):
        lot = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload={
                "name": "Lote 1", "feed_type": "silagem_milho",
                "facility_id": self.facility["public_id"],
                "initial_quantity_natural_kg": "10000",
                "dry_matter_pct": "35", "utilization_pct": "90",
            },
            request_id="req-lot",
        )
        lot_data = self.repo.get_lot(lot["public_id"])
        lot_data["balance_natural_kg"] = Decimal("5000")
        result = self.svc.get_reconciliation(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=lot["public_id"], request_id="req-1",
        )
        self.assertFalse(result["is_reconciled"])


class TestDashboard(unittest.TestCase):
    def setUp(self):
        self.repo = MockFeedInventoryRepository()
        self.auth_repo = FakeAuthRepository()

    def test_dashboard_returns_all_kpi_fields(self):
        from services.feed_inventory import FeedInventoryService
        svc = FeedInventoryService(self.repo, self.auth_repo)
        dashboard = svc.get_dashboard(
            subject="testuser", farm_public_id=uuid4(),
            request_id="req-1",
        )
        expected_keys = [
            "total_facilities", "total_active_lots",
            "total_capacity_natural_kg", "total_balance_natural_kg",
            "total_physical_dm_kg", "total_usable_dm_kg",
            "total_inventory_value", "lots_by_status",
            "lots_by_feed_type", "low_stock_lots", "depleted_lots",
        ]
        for key in expected_keys:
            self.assertIn(key, dashboard)


class TestAutonomySources(unittest.TestCase):
    def setUp(self):
        self.repo = MockFeedInventoryRepository()
        self.auth_repo = FakeAuthRepository()

    def test_returns_valid_lots(self):
        from services.feed_inventory import FeedInventoryService
        svc = FeedInventoryService(self.repo, self.auth_repo)
        sources = svc.get_autonomy_sources(
            subject="testuser", farm_public_id=uuid4(),
            request_id="req-1",
        )
        self.assertIsInstance(sources, list)


class TestIdempotency(unittest.TestCase):
    def setUp(self):
        self.repo = MockFeedInventoryRepository()
        self.auth_repo = FakeAuthRepository()
        from services.feed_inventory import FeedInventoryService
        self.svc = FeedInventoryService(self.repo, self.auth_repo)
        self.farm_id = uuid4()
        self.facility = self.svc.create_facility(
            subject="testuser", farm_public_id=self.farm_id,
            payload={"name": "Silo A", "facility_type": "silo_trincheira",
                     "capacity_natural_kg": "50000"},
            request_id="req-fac",
        )
        self.lot = self.svc.create_lot(
            subject="testuser", farm_public_id=self.farm_id,
            payload={
                "name": "Lote 1",
                "feed_type": "silagem_milho",
                "facility_id": self.facility["public_id"],
                "initial_quantity_natural_kg": "10000",
                "dry_matter_pct": "35",
                "utilization_pct": "90",
            },
            request_id="req-lot",
        )

    def test_identical_replay_idempotency(self):
        payload = {
            "movement_type": "entry",
            "quantity_natural_kg": "2000",
            "dry_matter_pct": "35",
            "utilization_pct": "90",
            "reason": "Replay test",
        }
        res1 = self.svc.create_movement(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=self.lot["public_id"], payload=payload,
            request_id="req-idem-1",
        )
        self.assertEqual(float(res1["quantity_natural_kg"]), 2000.0)

        res2 = self.svc.create_movement(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=self.lot["public_id"], payload=payload,
            request_id="req-idem-1",
        )

        self.assertEqual(self.repo.count_movements(self.repo.lots[0]["id"]), 2)
        self.assertEqual(res1["public_id"], res2["public_id"])
        self.assertEqual(res1["balance_after_natural_kg"], res2["balance_after_natural_kg"])

    def test_different_payload_same_request_id_raises(self):
        from core.authorization import ForbiddenError
        payload1 = {
            "movement_type": "entry",
            "quantity_natural_kg": "2000",
            "dry_matter_pct": "35",
            "utilization_pct": "90",
            "reason": "Replay test 1",
        }
        payload2 = {
            "movement_type": "entry",
            "quantity_natural_kg": "3000",
            "dry_matter_pct": "35",
            "utilization_pct": "90",
            "reason": "Replay test 1",
        }
        self.svc.create_movement(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=self.lot["public_id"], payload=payload1,
            request_id="req-idem-2",
        )

        with self.assertRaises(ForbiddenError) as ctx:
            self.svc.create_movement(
                subject="testuser", farm_public_id=self.farm_id,
                lot_uuid=self.lot["public_id"], payload=payload2,
                request_id="req-idem-2",
            )
        self.assertEqual(ctx.exception.code, "duplicate_request_id")

    def test_other_tenant_cannot_consult_or_reuse_request_id(self):
        from core.authorization import HiddenResourceError
        payload = {
            "movement_type": "entry",
            "quantity_natural_kg": "2000",
            "dry_matter_pct": "35",
            "utilization_pct": "90",
            "reason": "Replay test",
        }
        self.svc.create_movement(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=self.lot["public_id"], payload=payload,
            request_id="req-idem-3",
        )

        from uuid import UUID
        other_farm = UUID("00000000-0000-0000-0000-000000000002")
        with self.assertRaises(HiddenResourceError):
            self.svc.create_movement(
                subject="otheruser", farm_public_id=other_farm,
                lot_uuid=self.lot["public_id"], payload=payload,
                request_id="req-idem-3",
            )

    def test_loss_reason_sanitization_html_rejection(self):
        from core.authorization import ForbiddenError
        payload_html = {
            "movement_type": "loss",
            "quantity_natural_kg": "200",
            "loss_reason": "<b>deterioracao</b>",
        }
        with self.assertRaises(ForbiddenError) as ctx:
            self.svc.create_movement(
                subject="testuser", farm_public_id=self.farm_id,
                lot_uuid=self.lot["public_id"], payload=payload_html,
                request_id="req-loss-html",
            )
        self.assertEqual(ctx.exception.code, "invalid_loss_reason")

        payload_too_long = {
            "movement_type": "loss",
            "quantity_natural_kg": "200",
            "loss_reason": "a" * 201,
        }
        with self.assertRaises(ForbiddenError) as ctx:
            self.svc.create_movement(
                subject="testuser", farm_public_id=self.farm_id,
                lot_uuid=self.lot["public_id"], payload=payload_too_long,
                request_id="req-loss-long",
            )
        self.assertEqual(ctx.exception.code, "invalid_loss_reason")

        payload_clean = {
            "movement_type": "loss",
            "quantity_natural_kg": "200",
            "loss_reason": "deterioracao",
        }
        res = self.svc.create_movement(
            subject="testuser", farm_public_id=self.farm_id,
            lot_uuid=self.lot["public_id"], payload=payload_clean,
            request_id="req-loss-clean",
        )
        self.assertEqual(res["loss_reason"], "deterioracao")


if __name__ == "__main__":
    unittest.main()
