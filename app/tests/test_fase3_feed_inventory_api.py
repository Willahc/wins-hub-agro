"""Testes de API de Estoque de Ração — contratos HTTP e validações."""
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
class TestSchemas(unittest.TestCase):
    def test_facility_create_request_valid(self):
        from schemas.feed_inventory import FacilityCreateRequest
        f = FacilityCreateRequest(name="Silo A", facility_type="silo_trincheira",
                                  capacity_natural_kg="50000")
        self.assertEqual(f.name, "Silo A")
        self.assertEqual(f.facility_type, "silo_trincheira")
        self.assertEqual(f.capacity_natural_kg, "50000")

    def test_facility_create_request_empty_name_rejected(self):
        from schemas.feed_inventory import FacilityCreateRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            FacilityCreateRequest(name="", facility_type="silo_trincheira")

    def test_facility_create_request_defaults(self):
        from schemas.feed_inventory import FacilityCreateRequest
        f = FacilityCreateRequest(name="Silo A")
        self.assertEqual(f.facility_type, "storage")
        self.assertEqual(f.notes, "")

    def test_lot_create_request_valid(self):
        from schemas.feed_inventory import LotCreateRequest
        l = LotCreateRequest(
            facility_uuid="550e8400-e29b-41d4-a716-446655440000",
            name="Lote 1", feed_type="silagem_milho",
            initial_quantity_natural_kg="10000",
            dry_matter_pct="35",
        )
        self.assertEqual(l.name, "Lote 1")
        self.assertEqual(l.feed_type, "silagem_milho")
        self.assertEqual(l.initial_quantity_natural_kg, "10000")

    def test_lot_create_request_empty_name_rejected(self):
        from schemas.feed_inventory import LotCreateRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            LotCreateRequest(
                facility_uuid="550e8400-e29b-41d4-a716-446655440000",
                name="",
                initial_quantity_natural_kg="10000",
                dry_matter_pct="35",
            )

    def test_lot_create_request_defaults(self):
        from schemas.feed_inventory import LotCreateRequest
        l = LotCreateRequest(
            facility_uuid="550e8400-e29b-41d4-a716-446655440000",
            name="Lote 1",
            initial_quantity_natural_kg="10000",
            dry_matter_pct="35",
        )
        self.assertEqual(l.utilization_pct, "100")
        self.assertEqual(l.notes, "")

    def test_movement_create_request_valid(self):
        from schemas.feed_inventory import MovementCreateRequest
        m = MovementCreateRequest(movement_type="entry",
                                  quantity_natural_kg="5000")
        self.assertEqual(m.movement_type, "entry")
        self.assertEqual(m.quantity_natural_kg, "5000")

    def test_movement_create_request_defaults(self):
        from schemas.feed_inventory import MovementCreateRequest
        m = MovementCreateRequest(movement_type="entry",
                                  quantity_natural_kg="5000")
        self.assertEqual(m.notes, "")
        self.assertEqual(m.loss_reason, "")


@unittest.skipUnless(HAS_FASTAPI, "FastAPI/Pydantic não disponível")
class TestRouter(unittest.TestCase):
    def test_router_prefix(self):
        from routers.feed_inventory import router
        self.assertEqual(router.prefix, "/api/v2/farms")
        self.assertIn("feed_inventory", router.tags)

    def test_endpoints_exist(self):
        from routers.feed_inventory import router
        routes = {r.path for r in router.routes}
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/dashboard") for r in routes))
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/facilities") for r in routes))
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/lots") for r in routes))

    def test_facility_endpoints_exist(self):
        from routers.feed_inventory import router
        routes = {r.path for r in router.routes}
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/facilities/{facility_uuid}") for r in routes))

    def test_lot_endpoints_exist(self):
        from routers.feed_inventory import router
        routes = {r.path for r in router.routes}
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/lots/{lot_uuid}") for r in routes))

    def test_movement_endpoints_exist(self):
        from routers.feed_inventory import router
        routes = {r.path for r in router.routes}
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/lots/{lot_uuid}/movements") for r in routes))

    def test_withdraw_endpoint_exists(self):
        from routers.feed_inventory import router
        routes = {r.path for r in router.routes}
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/lots/{lot_uuid}/withdraw") for r in routes))

    def test_record_loss_endpoint_exists(self):
        from routers.feed_inventory import router
        routes = {r.path for r in router.routes}
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/lots/{lot_uuid}/record-loss") for r in routes))

    def test_adjust_endpoint_exists(self):
        from routers.feed_inventory import router
        routes = {r.path for r in router.routes}
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/lots/{lot_uuid}/adjust") for r in routes))

    def test_reconciliation_endpoint_exists(self):
        from routers.feed_inventory import router
        routes = {r.path for r in router.routes}
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/lots/{lot_uuid}/reconciliation") for r in routes))

    def test_autonomy_sources_endpoint_exists(self):
        from routers.feed_inventory import router
        routes = {r.path for r in router.routes}
        self.assertTrue(any(r.endswith("/{farm_uuid}/feed-inventory/autonomy-sources") for r in routes))

    def test_cache_headers_set(self):
        from routers.feed_inventory import _cache_headers
        from unittest.mock import MagicMock
        response = MagicMock()
        response.headers = {}
        _cache_headers(response)
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_request_id_valid(self):
        from routers.feed_inventory import _REQUEST_ID
        self.assertTrue(_REQUEST_ID.fullmatch("test-123"))
        self.assertTrue(_REQUEST_ID.fullmatch("abc:def"))
        self.assertIsNone(_REQUEST_ID.fullmatch("invalid space"))
        self.assertIsNone(_REQUEST_ID.fullmatch("a" * 101))


@unittest.skipUnless(HAS_FASTAPI, "FastAPI/Pydantic não disponível")
class TestDecimalFields(unittest.TestCase):
    def test_decimal_fields_stay_as_strings_in_facility_response(self):
        from schemas.feed_inventory import FacilityResponse
        r = FacilityResponse(
            public_id="abc", name="Silo A", code="",
            facility_type="silo_trincheira", capacity_natural_kg="50000",
            preferred_display_unit="kg", location_description="",
            active=True, notes="", created_at="2026-07-01", updated_at="2026-07-01",
        )
        self.assertIsInstance(r.capacity_natural_kg, str)

    def test_decimal_fields_stay_as_strings_in_lot_response(self):
        from schemas.feed_inventory import LotResponse
        r = LotResponse(
            public_id="abc", facility_uuid="def", facility_name="Silo A",
            name="Lote 1", feed_type="silagem_milho", custom_feed_type="",
            production_date="", ensiling_date="", source_description="",
            initial_quantity_natural_kg="10000",
            current_quantity_natural_kg="10000",
            dry_matter_pct="35", utilization_pct="90",
            initial_total_dm_kg="3500", current_total_dm_kg="3500",
            initial_total_cost="12000", cost_per_dm_kg="3.43",
            planned_daily_use_dm_kg="", days_of_stock="",
            status="available", opened_at="", closed_at="", notes="",
            created_at="2026-07-01", updated_at="2026-07-01",
        )
        self.assertIsInstance(r.initial_quantity_natural_kg, str)
        self.assertIsInstance(r.dry_matter_pct, str)
        self.assertIsInstance(r.utilization_pct, str)

    def test_decimal_fields_stay_as_strings_in_movement_response(self):
        from schemas.feed_inventory import MovementResponse
        r = MovementResponse(
            public_id="abc", lot_uuid="def",
            movement_type="entry", quantity_natural_kg="5000",
            dry_matter_pct_snapshot="35", utilization_pct_snapshot="90",
            physical_dm_kg="1750", usable_dm_kg="1575",
            unit_cost_snapshot="2.4", total_cost="12000",
            loss_reason="", reason="", notes="", movement_at="2026-07-01",
            created_at="2026-07-01",
        )
        self.assertIsInstance(r.quantity_natural_kg, str)
        self.assertIsInstance(r.physical_dm_kg, str)


class TestFeatureFlag(unittest.TestCase):
    def test_feature_flag_variable_exists(self):
        try:
            import importlib
            mod = importlib.import_module("routers.feed_inventory")
            self.assertTrue(hasattr(mod, "ENABLE_FEED_INVENTORY"))
        except (ImportError, ModuleNotFoundError):
            self.skipTest("FastAPI não disponível")

    def test_feature_flag_default_false(self):
        import os
        old_val = os.environ.get("ENABLE_FEED_INVENTORY")
        try:
            if "ENABLE_FEED_INVENTORY" in os.environ:
                del os.environ["ENABLE_FEED_INVENTORY"]
            val = os.getenv("ENABLE_FEED_INVENTORY", "false")
            self.assertNotIn(val.lower(), {"1", "true", "yes"})
        finally:
            if old_val is not None:
                os.environ["ENABLE_FEED_INVENTORY"] = old_val


if __name__ == "__main__":
    unittest.main()
