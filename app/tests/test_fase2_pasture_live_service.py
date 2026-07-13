"""Testes de serviço de Pasto Vivo — mocks e lógica de negócio."""
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

from domain.pasture_live import (
    FORMULA_VERSION, PaddockStatus, EventType, MeasurementMethod,
    MeasurementResult, suggest_paddock_state,
)
from domain.foundation import RecordStatus


class MockPastureLiveRepository:
    def __init__(self):
        self.paddocks = []
        self.measurements = []
        self.events = []
        self._next_id = 1

    def find_farm(self, farm_public_id):
        return {"id": 100, "public_id": str(farm_public_id),
                "organization_id": 1, "name": "Fazenda Teste", "status": "active"}

    def find_membership(self, user_id, org_id):
        return {"id": 10, "public_id": str(uuid4()), "organization_id": org_id,
                "role": "manager", "status": "active"}

    def find_farm_access(self, membership_id, farm_id):
        return {"id": 200, "access_level": "manage", "status": "active"}

    def find_resource_scope(self, user_id, resource_type, resource_id):
        return None

    def create_paddock(self, data, user_id):
        self._next_id += 1
        paddock = {
            "id": self._next_id, "public_id": data["public_id"],
            "name": data["name"], "area_ha": data["area_ha"],
            "forage_species": data["forage_species"],
            "planned_rest_days": data.get("planned_rest_days", 0),
            "default_utilization_pct": data.get("default_utilization_pct", 50),
            "manual_status": data.get("manual_status", PaddockStatus.NO_MEASUREMENT.value),
            "active": data.get("active", True),
            "notes": data.get("notes", ""),
            "organization_id": data["organization_id"],
            "farm_id": data["farm_id"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        self.paddocks.append(paddock)
        return {"id": paddock["id"], "public_id": paddock["public_id"]}

    def get_paddock(self, public_id):
        for p in self.paddocks:
            if str(p["public_id"]) == str(public_id):
                return p
        return None

    def list_paddocks(self, farm_id, limit=25, offset=0):
        items = [p for p in self.paddocks if p["farm_id"] == farm_id]
        return items[offset:offset + limit]

    def count_paddocks(self, farm_id):
        return len([p for p in self.paddocks if p["farm_id"] == farm_id])

    def update_paddock(self, paddock_id, data, user_id):
        for p in self.paddocks:
            if p["id"] == paddock_id:
                p.update(data)
                p["updated_at"] = datetime.now(timezone.utc)
                return {"id": paddock_id, "public_id": data["public_id"]}
        return None

    def update_paddock_manual_status(self, paddock_id, new_status, user_id):
        for p in self.paddocks:
            if p["id"] == paddock_id:
                p["manual_status"] = new_status
                p["updated_at"] = datetime.now(timezone.utc)
                return

    def archive_paddock(self, paddock_id, user_id, org_id, farm_id, public_id, request_id=""):
        for p in self.paddocks:
            if p["id"] == paddock_id:
                p["active"] = False
                p["manual_status"] = PaddockStatus.INACTIVE.value
                return

    def create_measurement(self, data, user_id):
        self._next_id += 1
        measurement = {
            "id": self._next_id, "public_id": data["public_id"],
            "paddock_id": data["paddock_id"],
            "farm_id": data["farm_id"],
            "organization_id": data["organization_id"],
            "measurement_method": data["measurement_method"],
            "measured_at": data["measured_at"],
            "available_dm_kg_ha": data["available_dm_kg_ha"],
            "utilization_pct": data["utilization_pct"],
            "calculated_total_dm_kg": data["calculated_total_dm_kg"],
            "calculated_usable_dm_kg": data["calculated_usable_dm_kg"],
            "average_height_cm": data.get("average_height_cm"),
            "notes": data.get("notes", ""),
            "measured_by_user_id": data["measured_by_user_id"],
            "created_at": datetime.now(timezone.utc),
        }
        self.measurements.append(measurement)
        return {"id": measurement["id"], "public_id": measurement["public_id"]}

    def get_measurement(self, public_id):
        for m in self.measurements:
            if str(m["public_id"]) == str(public_id):
                return m
        return None

    def list_measurements(self, paddock_id, limit=50, offset=0):
        items = [m for m in self.measurements if m["paddock_id"] == paddock_id]
        return items[offset:offset + limit]

    def count_measurements(self, paddock_id):
        return len([m for m in self.measurements if m["paddock_id"] == paddock_id])

    def create_event(self, data, user_id):
        self._next_id += 1
        event = {
            "id": self._next_id, "public_id": data["public_id"],
            "paddock_id": data["paddock_id"],
            "farm_id": data["farm_id"],
            "organization_id": data["organization_id"],
            "event_type": data["event_type"],
            "notes": data.get("notes", ""),
            "created_at": datetime.now(timezone.utc),
        }
        self.events.append(event)
        return {"id": event["id"], "public_id": event["public_id"]}

    def list_events(self, paddock_id, limit=50, offset=0):
        items = [e for e in self.events if e["paddock_id"] == paddock_id]
        return items[offset:offset + limit]

    def count_events(self, paddock_id):
        return len([e for e in self.events if e["paddock_id"] == paddock_id])

    def get_open_grazing_event(self, paddock_id):
        for e in self.events:
            if (e["paddock_id"] == paddock_id
                    and e["event_type"] == EventType.GRAZING_STARTED.value):
                finish_events = [
                    ev for ev in self.events
                    if ev["paddock_id"] == paddock_id
                    and ev["event_type"] == EventType.GRAZING_FINISHED.value
                    and ev["created_at"] > e["created_at"]
                ]
                if not finish_events:
                    return e
        return None

    def get_dashboard(self, farm_id):
        paddocks = [p for p in self.paddocks if p["farm_id"] == farm_id]
        active = [p for p in paddocks if p.get("active", True)]
        return {
            "total_paddocks": len(paddocks),
            "active_paddocks": len(active),
            "grazing_count": sum(1 for p in active if p["manual_status"] == "grazing"),
            "resting_count": sum(1 for p in active if p["manual_status"] == "resting"),
            "ready_count": sum(1 for p in active if p["manual_status"] == "ready"),
            "attention_count": sum(1 for p in active if p["manual_status"] == "attention"),
            "total_area_ha": str(sum(p["area_ha"] for p in active)),
            "total_usable_dm_kg": "0",
            "measurements_total": len(self.measurements),
        }

    def get_autonomy_sources(self, farm_id):
        paddocks = [p for p in self.paddocks
                    if p["farm_id"] == farm_id and p.get("active", True)
                    and p["manual_status"] not in ("unavailable", "inactive")]
        sources = []
        for p in paddocks:
            latest = None
            for m in sorted(self.measurements,
                            key=lambda x: x["created_at"], reverse=True):
                if m["paddock_id"] == p["id"]:
                    latest = {
                        "available_dm_kg_ha": str(m["available_dm_kg_ha"]),
                        "calculated_usable_dm_kg": str(m["calculated_usable_dm_kg"]),
                        "utilization_pct": str(m["utilization_pct"]),
                        "measured_at": str(m["measured_at"]),
                    }
                    break
            sources.append({
                "paddock_public_id": str(p["public_id"]),
                "name": p["name"],
                "area_ha": str(p["area_ha"]),
                "forage_species": p["forage_species"],
                "manual_status": p["manual_status"],
                "latest_measurement": latest,
            })
        return sources


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


class TestPastureLiveService(unittest.TestCase):
    def setUp(self):
        self.repo = MockPastureLiveRepository()
        self.auth_repo = FakeAuthRepository()

    def _make_payload(self):
        return {
            "name": "P1",
            "area_ha": "10",
            "forage_species": "brachiaria_brizantha",
            "planned_rest_days": 30,
            "default_utilization_pct": "50",
            "manual_status": "ready",
            "active": True,
            "notes": "",
        }

    def test_service_instantiation(self):
        from services.pasture_live import PastureLiveService
        svc = PastureLiveService(self.repo, self.auth_repo)
        self.assertIsNotNone(svc)
        self.assertEqual(svc.repository, self.repo)

    def test_paddock_creation_validation(self):
        from services.pasture_live import PastureLiveService
        svc = PastureLiveService(self.repo, self.auth_repo)
        result = svc.create_paddock(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        self.assertIn("public_id", result)
        self.assertEqual(result["name"], "P1")
        self.assertEqual(result["forage_species"], "brachiaria_brizantha")
        self.assertEqual(result["status"], PaddockStatus.NO_MEASUREMENT.value)

    def test_measurement_calculation(self):
        from services.pasture_live import PastureLiveService
        svc = PastureLiveService(self.repo, self.auth_repo)
        paddock = svc.create_paddock(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        payload = {
            "measurement_method": "visual",
            "measured_at": "2026-07-01",
            "available_dm_kg_ha": "2000",
            "utilization_pct": "50",
            "notes": "",
        }
        result = svc.create_measurement(
            subject="testuser", farm_public_id=uuid4(),
            paddock_uuid=paddock["public_id"],
            payload=payload, request_id="req-2",
        )
        self.assertEqual(result["calculated_total_dm_kg"], "20000.00")
        self.assertEqual(result["calculated_usable_dm_kg"], "10000.00")
        self.assertEqual(result["formula_version"], FORMULA_VERSION)

    def test_double_grazing_prevention(self):
        from services.pasture_live import PastureLiveService
        from core.authorization import ForbiddenError
        svc = PastureLiveService(self.repo, self.auth_repo)
        paddock = svc.create_paddock(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        svc.start_grazing(
            subject="testuser", farm_public_id=uuid4(),
            paddock_uuid=paddock["public_id"],
            payload={"notes": ""}, request_id="req-2",
        )
        with self.assertRaises(ForbiddenError):
            svc.start_grazing(
                subject="testuser", farm_public_id=uuid4(),
                paddock_uuid=paddock["public_id"],
                payload={"notes": ""}, request_id="req-3",
            )

    def test_grazing_start_finish_flow(self):
        from services.pasture_live import PastureLiveService
        svc = PastureLiveService(self.repo, self.auth_repo)
        paddock = svc.create_paddock(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        start_result = svc.start_grazing(
            subject="testuser", farm_public_id=uuid4(),
            paddock_uuid=paddock["public_id"],
            payload={"notes": "inicio"}, request_id="req-2",
        )
        self.assertEqual(start_result["status"], PaddockStatus.GRAZING.value)

        finish_result = svc.finish_grazing(
            subject="testuser", farm_public_id=uuid4(),
            paddock_uuid=paddock["public_id"],
            payload={"notes": "fim"}, request_id="req-3",
        )
        self.assertEqual(finish_result["status"], PaddockStatus.RESTING.value)

    def test_dashboard_aggregation(self):
        from services.pasture_live import PastureLiveService
        svc = PastureLiveService(self.repo, self.auth_repo)
        svc.create_paddock(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        dashboard = svc.get_dashboard(
            subject="testuser", farm_public_id=uuid4(),
            request_id="req-2",
        )
        self.assertIn("total_paddocks", dashboard)
        self.assertIn("active_paddocks", dashboard)
        self.assertIn("grazing_count", dashboard)
        self.assertIn("resting_count", dashboard)
        self.assertEqual(dashboard["total_paddocks"], 1)
        self.assertEqual(dashboard["active_paddocks"], 1)

    def test_autonomy_sources_format(self):
        from services.pasture_live import PastureLiveService
        svc = PastureLiveService(self.repo, self.auth_repo)
        svc.create_paddock(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        sources = svc.get_autonomy_sources(
            subject="testuser", farm_public_id=uuid4(),
            request_id="req-2",
        )
        self.assertIsInstance(sources, list)
        self.assertEqual(len(sources), 1)
        self.assertIn("paddock_public_id", sources[0])
        self.assertIn("name", sources[0])
        self.assertIn("area_ha", sources[0])
        self.assertIn("forage_species", sources[0])
        self.assertIn("manual_status", sources[0])
        self.assertIn("latest_measurement", sources[0])

    def test_archive_paddock(self):
        from services.pasture_live import PastureLiveService
        svc = PastureLiveService(self.repo, self.auth_repo)
        paddock = svc.create_paddock(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        svc.archive_paddock(
            subject="testuser", farm_public_id=uuid4(),
            paddock_uuid=paddock["public_id"],
            request_id="req-2",
        )
        updated = self.repo.get_paddock(paddock["public_id"])
        self.assertFalse(updated["active"])

    def test_list_paddocks_with_filters(self):
        from services.pasture_live import PastureLiveService
        svc = PastureLiveService(self.repo, self.auth_repo)
        for i in range(3):
            svc.create_paddock(
                subject="testuser", farm_public_id=uuid4(),
                payload={**self._make_payload(), "name": f"P{i}"},
                request_id=f"req-{i}",
            )
        result = svc.list_paddocks(
            subject="testuser", farm_public_id=uuid4(),
            limit=2, offset=0, request_id="req-list",
        )
        self.assertIn("items", result)
        self.assertIn("pagination", result)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["pagination"]["total"], 3)
        self.assertTrue(result["pagination"]["has_more"])

    def test_event_creation(self):
        from services.pasture_live import PastureLiveService
        svc = PastureLiveService(self.repo, self.auth_repo)
        paddock = svc.create_paddock(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        result = svc.create_event(
            subject="testuser", farm_public_id=uuid4(),
            paddock_uuid=paddock["public_id"],
            payload={"event_type": "status_adjusted", "notes": "ajuste"},
            request_id="req-2",
        )
        self.assertIn("status", result)


if __name__ == "__main__":
    unittest.main()
