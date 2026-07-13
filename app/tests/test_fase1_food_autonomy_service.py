"""Testes de serviço de Autonomia Alimentar — mocks e lógica de negócio."""
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from domain.food_autonomy import (
    FORMULA_VERSION, HerdItem, PastureItem, FeedItem,
    SimulationInput, ScenarioStatus, calculate_autonomy,
)
from domain.foundation import RecordStatus


def _make_user():
    u = MagicMock()
    u.id = 1
    u.public_id = uuid4()
    u.status = RecordStatus.ACTIVE
    return u


def _make_membership(org_id=1):
    m = MagicMock()
    m.id = 10
    m.public_id = str(uuid4())
    m.organization_id = org_id
    m.role = MagicMock(value="manager")
    m.status = RecordStatus.ACTIVE
    m.is_active = lambda now: True
    return m


def _make_farm(org_id=1):
    f = MagicMock()
    f.id = 100
    f.public_id = uuid4()
    f.organization_id = org_id
    f.name = "Fazenda Teste"
    f.status = MagicMock(value="active")
    return f


def _make_farm_access():
    a = MagicMock()
    a.id = 200
    a.access_level = MagicMock(value="manage")
    a.status = RecordStatus.ACTIVE
    a.is_active = lambda now: True
    return a


class FakeFoodAutonomyRepository:
    def __init__(self):
        self.scenarios = []
        self._next_id = 1

    def find_farm(self, farm_public_id):
        return {"id": 100, "public_id": str(farm_public_id),
                "organization_id": 1, "name": "Fazenda Teste", "status": "active"}

    def find_membership(self, user_id, org_id):
        return {"id": 10, "public_id": str(uuid4()), "organization_id": org_id,
                "role": "manager", "status": "active"}

    def find_farm_access(self, membership_id, farm_id):
        return {"id": 200, "access_level": "manage", "status": "active"}

    def list_scenarios(self, farm_id, limit=25, offset=0, status_filter=None):
        return self.scenarios[offset:offset+limit]

    def count_scenarios(self, farm_id, include_archived=False):
        return len(self.scenarios)

    def get_scenario(self, scenario_public_id):
        for s in self.scenarios:
            if str(s["public_id"]) == str(scenario_public_id):
                return s
        return None

    def create_scenario(self, data, herd, pastures, feeds, user_id):
        self._next_id += 1
        scenario = {
            "id": self._next_id, "public_id": data["public_id"],
            "name": data["name"], "reference_date": data["reference_date"],
            "target_days": data["target_days"], "status": data["status"],
            "safety_margin_pct": data["safety_margin_pct"],
            "total_daily_demand_dm_kg": data["total_daily_demand_dm_kg"],
            "total_pasture_dm_kg": data["total_pasture_dm_kg"],
            "total_stored_feed_dm_kg": data["total_stored_feed_dm_kg"],
            "total_physical_dm_kg": data["total_physical_dm_kg"],
            "reserve_dm_kg": data["reserve_dm_kg"],
            "planning_available_dm_kg": data["planning_available_dm_kg"],
            "autonomy_days": data["autonomy_days"],
            "target_required_dm_kg": data["target_required_dm_kg"],
            "balance_dm_kg": data["balance_dm_kg"],
            "balance_days": data["balance_days"],
            "estimated_end_date": data.get("estimated_end_date"),
            "formula_version": data["formula_version"],
            "notes": data.get("notes", ""),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "herd_items": herd,
            "pasture_items": pastures,
            "feed_items": feeds,
        }
        self.scenarios.append(scenario)
        return {"id": self._next_id, "public_id": data["public_id"]}

    def update_scenario(self, scenario_id, data, herd, pastures, feeds, user_id):
        return {"id": scenario_id, "public_id": data["public_id"]}

    def archive_scenario(self, scenario_id, user_id, org_id, farm_id, public_id):
        pass


class TestFoodAutonomyService(unittest.TestCase):
    def setUp(self):
        self.repo = FakeFoodAutonomyRepository()
        self.auth_repo = MagicMock()
        user = _make_user()
        user.status = RecordStatus.ACTIVE
        self.auth_repo.find_user_by_subject.return_value = user
        membership = _make_membership()
        membership.status = RecordStatus.ACTIVE
        self.auth_repo.find_membership.return_value = membership
        farm = _make_farm()
        farm.status = RecordStatus.ACTIVE
        self.auth_repo.find_farm.return_value = farm
        access = _make_farm_access()
        access.status = RecordStatus.ACTIVE
        self.auth_repo.find_farm_access.return_value = access
        self.auth_repo.find_resource_scope.return_value = None

    def _make_payload(self):
        return {
            "name": "Cenário Teste",
            "reference_date": "2026-07-01",
            "target_days": 90,
            "safety_margin_pct": "0",
            "herd": [{"category": "lactating_cows", "head_count": 20,
                       "average_weight_kg": "450", "intake_pct_body_weight": "2.5"}],
            "pastures": [{"name": "P1", "area_ha": "10", "available_dm_kg_ha": "2000",
                          "utilization_pct": "50"}],
            "feeds": [{"feed_type": "silage", "name": "S1",
                       "quantity_natural_kg": "10000", "dry_matter_pct": "35",
                       "utilization_pct": "90"}],
            "notes": "",
        }

    def test_simulate_returns_result(self):
        from services.food_autonomy import FoodAutonomyService
        svc = FoodAutonomyService(self.repo, self.auth_repo)
        result = svc.simulate(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        self.assertEqual(result["formula_version"], FORMULA_VERSION)
        self.assertEqual(result["daily_demand_dm_kg"], "225.00")
        self.assertIn("status", result)

    def test_simulate_calculation_matches_domain(self):
        from services.food_autonomy import FoodAutonomyService
        svc = FoodAutonomyService(self.repo, self.auth_repo)
        result = svc.simulate(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        self.assertEqual(result["pasture_usable_dm_kg"], "10000.00")
        self.assertEqual(result["stored_feed_usable_dm_kg"], "3150.00")

    def test_create_scenario_persists(self):
        from services.food_autonomy import FoodAutonomyService
        svc = FoodAutonomyService(self.repo, self.auth_repo)
        result = svc.create_scenario(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        self.assertIn("public_id", result)

    def test_list_scenarios(self):
        from services.food_autonomy import FoodAutonomyService
        svc = FoodAutonomyService(self.repo, self.auth_repo)
        result = svc.list_scenarios(
            subject="testuser", farm_public_id=uuid4(),
            limit=25, offset=0, status_filter=None, request_id="req-1",
        )
        self.assertIn("items", result)
        self.assertIn("pagination", result)

    def test_result_decimal_strings(self):
        from services.food_autonomy import FoodAutonomyService
        svc = FoodAutonomyService(self.repo, self.auth_repo)
        result = svc.simulate(
            subject="testuser", farm_public_id=uuid4(),
            payload=self._make_payload(), request_id="req-1",
        )
        for key in ["daily_demand_dm_kg", "pasture_usable_dm_kg",
                     "stored_feed_usable_dm_kg", "physical_total_dm_kg",
                     "reserve_dm_kg", "planning_available_dm_kg",
                     "autonomy_days", "balance_dm_kg", "balance_days"]:
            self.assertIsInstance(result[key], str)
            float(result[key])

    def test_empty_herd_rejected(self):
        from services.food_autonomy import FoodAutonomyService
        svc = FoodAutonomyService(self.repo, self.auth_repo)
        payload = self._make_payload()
        payload["herd"] = []
        with self.assertRaises(ValueError):
            svc.simulate(subject="testuser", farm_public_id=uuid4(),
                         payload=payload, request_id="req-1")

    def test_no_food_source_rejected(self):
        from services.food_autonomy import FoodAutonomyService
        svc = FoodAutonomyService(self.repo, self.auth_repo)
        payload = self._make_payload()
        payload["pastures"] = []
        payload["feeds"] = []
        with self.assertRaises(ValueError):
            svc.simulate(subject="testuser", farm_public_id=uuid4(),
                         payload=payload, request_id="req-1")


class TestFoodAutonomyRepository(unittest.TestCase):
    def test_find_farm_returns_none_for_unknown(self):
        from repositories.food_autonomy import FoodAutonomyRepository
        repo = FoodAutonomyRepository()
        with patch("repositories.food_autonomy.query", return_value=[]):
            result = repo.find_farm(uuid4())
            self.assertIsNone(result)

    def test_list_scenarios_empty(self):
        from repositories.food_autonomy import FoodAutonomyRepository
        repo = FoodAutonomyRepository()
        with patch("repositories.food_autonomy.query", return_value=[]):
            result = repo.list_scenarios(farm_id=1)
            self.assertEqual(result, [])

    def test_count_scenarios_zero(self):
        from repositories.food_autonomy import FoodAutonomyRepository
        repo = FoodAutonomyRepository()
        with patch("repositories.food_autonomy.query", return_value=[{"n": 0}]):
            result = repo.count_scenarios(farm_id=1)
            self.assertEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
