"""Testes de API de Autonomia Alimentar — contratos HTTP e validações."""
import unittest
import os


HAS_FASTAPI = False
try:
    import fastapi  # noqa: F401
    import pydantic  # noqa: F401
    HAS_FASTAPI = True
except ImportError:
    pass


@unittest.skipUnless(HAS_FASTAPI, "FastAPI/Pydantic não disponível")
class TestFoodAutonomyAPI(unittest.TestCase):
    def test_simulate_endpoint_exists(self):
        from routers.food_autonomy import router
        routes = {r.path for r in router.routes}
        self.assertIn("/{farm_uuid}/food-autonomy/simulate", routes)

    def test_scenarios_crud_endpoints_exist(self):
        from routers.food_autonomy import router
        routes = {r.path for r in router.routes}
        self.assertIn("/{farm_uuid}/food-autonomy/scenarios", routes)
        self.assertIn("/{farm_uuid}/food-autonomy/scenarios/{scenario_uuid}", routes)

    def test_router_prefix(self):
        from routers.food_autonomy import router
        self.assertEqual(router.prefix, "/api/v2/farms")
        self.assertIn("food_autonomy", router.tags)

    def test_cache_headers_set(self):
        from routers.food_autonomy import _cache_headers
        from unittest.mock import MagicMock
        response = MagicMock()
        _cache_headers(response)
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_request_id_valid(self):
        from routers.food_autonomy import _REQUEST_ID
        self.assertTrue(_REQUEST_ID.fullmatch("test-123"))
        self.assertTrue(_REQUEST_ID.fullmatch("abc:def"))
        self.assertIsNone(_REQUEST_ID.fullmatch("invalid space"))
        self.assertIsNone(_REQUEST_ID.fullmatch("a" * 101))


@unittest.skipUnless(HAS_FASTAPI, "FastAPI/Pydantic não disponível")
class TestFoodAutonomySchemas(unittest.TestCase):
    def test_herd_item_schema_valid(self):
        from schemas.food_autonomy import HerdItemSchema
        h = HerdItemSchema(category="lactating_cows", head_count=20,
                           average_weight_kg="450", intake_pct_body_weight="2.5")
        self.assertEqual(h.category, "lactating_cows")

    def test_herd_item_negative_head_count_rejected(self):
        from schemas.food_autonomy import HerdItemSchema
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            HerdItemSchema(category="lactating_cows", head_count=-1,
                           average_weight_kg="450", intake_pct_body_weight="2.5")

    def test_pasture_item_schema_valid(self):
        from schemas.food_autonomy import PastureItemSchema
        p = PastureItemSchema(name="P1", area_ha="10",
                              available_dm_kg_ha="2000", utilization_pct="50")
        self.assertEqual(p.name, "P1")

    def test_feed_item_schema_valid(self):
        from schemas.food_autonomy import FeedItemSchema
        f = FeedItemSchema(feed_type="silage", name="S1",
                           quantity_natural_kg="10000", dry_matter_pct="35",
                           utilization_pct="90")
        self.assertEqual(f.feed_type, "silage")

    def test_feed_item_invalid_type_rejected(self):
        from schemas.food_autonomy import FeedItemSchema
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            FeedItemSchema(feed_type="invalid", name="X",
                           quantity_natural_kg="100", dry_matter_pct="90",
                           utilization_pct="100")

    def test_simulation_request_defaults(self):
        from schemas.food_autonomy import SimulationRequest
        from datetime import date
        req = SimulationRequest(
            reference_date=date(2026, 7, 1),
            herd=[{"category": "lactating_cows", "head_count": 20,
                   "average_weight_kg": "450", "intake_pct_body_weight": "2.5"}],
        )
        self.assertEqual(req.target_days, 90)
        self.assertEqual(req.safety_margin_pct, "0")

    def test_simulation_request_no_food_rejected(self):
        from schemas.food_autonomy import SimulationRequest
        from pydantic import ValidationError
        from datetime import date
        with self.assertRaises(ValidationError):
            SimulationRequest(
                reference_date=date(2026, 7, 1),
                herd=[{"category": "lactating_cows", "head_count": 20,
                       "average_weight_kg": "450", "intake_pct_body_weight": "2.5"}],
                pastures=[], feeds=[],
            )

    def test_simulation_response_fields(self):
        from schemas.food_autonomy import SimulationResponse
        r = SimulationResponse(
            formula_version="food_autonomy.v1",
            daily_demand_dm_kg="225.00",
            pasture_usable_dm_kg="10000.00",
            stored_feed_usable_dm_kg="3150.00",
            physical_total_dm_kg="13150.00",
            reserve_dm_kg="0",
            planning_available_dm_kg="13150.00",
            autonomy_days="58.44",
            target_days=90,
            target_required_dm_kg="20250.00",
            balance_dm_kg="-7100.00",
            balance_days="-31.56",
            status="warning",
            estimated_end_date="2026-09-03",
            warnings=["Teste"],
        )
        self.assertEqual(r.status, "warning")
        self.assertEqual(r.autonomy_days, "58.44")

    def test_decimal_strings_not_float(self):
        from schemas.food_autonomy import SimulationResponse
        r = SimulationResponse(
            formula_version="v1", daily_demand_dm_kg="100.00",
            pasture_usable_dm_kg="0", stored_feed_usable_dm_kg="0",
            physical_total_dm_kg="0", reserve_dm_kg="0",
            planning_available_dm_kg="0", autonomy_days="0",
            target_days=90, target_required_dm_kg="9000",
            balance_dm_kg="-9000", balance_days="-90",
            status="critical", estimated_end_date=None, warnings=[],
        )
        self.assertIsInstance(r.daily_demand_dm_kg, str)
        self.assertNotIn("e", r.daily_demand_dm_kg)


class TestFoodAutonomySecurity(unittest.TestCase):
    def test_feature_flag_default_false(self):
        val = os.getenv("ENABLE_FOOD_AUTONOMY", "")
        self.assertNotIn(val.lower(), {"1", "true", "yes"})

    def test_no_internal_ids_in_response_schema(self):
        """Verifica que o schema de resposta não expõe IDs internos."""
        with open(os.path.join(os.path.dirname(__file__), "..", "schemas", "food_autonomy.py")) as f:
            content = f.read()
        self.assertNotIn("organization_id", content.split("class SimulationResponse")[1]
                         if "class SimulationResponse" in content else "")
        self.assertNotIn("farm_id", content.split("class SimulationResponse")[1]
                         if "class SimulationResponse" in content else "")

    def test_no_float_in_domain(self):
        from domain.food_autonomy import calculate_autonomy, HerdItem, PastureItem, SimulationInput
        from decimal import Decimal
        from datetime import date
        inp = SimulationInput(
            name="T", reference_date=date(2026, 1, 1),
            target_days=90, safety_margin_pct=Decimal("0"),
            herd=(HerdItem(category="other", head_count=10,
                           average_weight_kg=Decimal("400"),
                           intake_pct_body_weight=Decimal("2.5")),),
            pastures=(PastureItem(name="P", area_ha=Decimal("5"),
                                  available_dm_kg_ha=Decimal("2000"),
                                  utilization_pct=Decimal("50")),),
            feeds=(),
        )
        r = calculate_autonomy(inp)
        for attr in ["daily_demand_dm_kg", "pasture_usable_dm_kg",
                     "autonomy_days", "balance_dm_kg", "balance_days"]:
            self.assertIsInstance(getattr(r, attr), Decimal)


if __name__ == "__main__":
    unittest.main()
