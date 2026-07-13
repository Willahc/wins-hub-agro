"""Testes de API de Pasto Vivo — contratos HTTP e validações."""
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
class TestPastureLiveSchemas(unittest.TestCase):
    def test_paddock_create_request_valid(self):
        from schemas.pasture_live import PaddockCreateRequest
        p = PaddockCreateRequest(name="P1", area_ha="10",
                                 forage_species="brachiaria", rest_days=30)
        self.assertEqual(p.name, "P1")
        self.assertEqual(p.area_ha, "10")
        self.assertEqual(p.forage_species, "brachiaria")
        self.assertEqual(p.rest_days, 30)

    def test_paddock_create_request_defaults(self):
        from schemas.pasture_live import PaddockCreateRequest
        p = PaddockCreateRequest(name="P1", area_ha="10")
        self.assertEqual(p.forage_species, "mixed")
        self.assertEqual(p.rest_days, 30)
        self.assertEqual(p.notes, "")

    def test_paddock_create_request_empty_name_rejected(self):
        from schemas.pasture_live import PaddockCreateRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            PaddockCreateRequest(name="", area_ha="10")

    def test_measurement_create_request_valid(self):
        from schemas.pasture_live import MeasurementCreateRequest
        m = MeasurementCreateRequest(method="visual", available_dm_kg_ha="2000",
                                     utilization_pct="50")
        self.assertEqual(m.method, "visual")
        self.assertEqual(m.available_dm_kg_ha, "2000")
        self.assertEqual(m.utilization_pct, "50")

    def test_measurement_create_request_defaults(self):
        from schemas.pasture_live import MeasurementCreateRequest
        m = MeasurementCreateRequest(available_dm_kg_ha="1500")
        self.assertEqual(m.method, "visual")
        self.assertEqual(m.utilization_pct, "100")
        self.assertEqual(m.notes, "")
        self.assertIsNone(m.estimated_height_cm)

    def test_event_create_request_valid(self):
        from schemas.pasture_live import EventCreateRequest
        e = EventCreateRequest(event_type="grazing_started", notes="início")
        self.assertEqual(e.event_type, "grazing_started")
        self.assertEqual(e.notes, "início")

    def test_start_grazing_request_valid(self):
        from schemas.pasture_live import StartGrazingRequest
        r = StartGrazingRequest(notes="teste")
        self.assertEqual(r.notes, "teste")

    def test_start_grazing_request_defaults(self):
        from schemas.pasture_live import StartGrazingRequest
        r = StartGrazingRequest()
        self.assertEqual(r.notes, "")

    def test_finish_grazing_request_valid(self):
        from schemas.pasture_live import FinishGrazingRequest
        r = FinishGrazingRequest(notes="fim")
        self.assertEqual(r.notes, "fim")

    def test_paddock_response_fields(self):
        from schemas.pasture_live import PaddockResponse
        r = PaddockResponse(
            public_id="abc", name="P1", area_ha="10",
            forage_species="brachiaria", rest_days=30,
            status="ready", is_inactive=False, is_unavailable=False,
            notes="", created_at="2026-07-01", updated_at="2026-07-01",
        )
        self.assertEqual(r.public_id, "abc")
        self.assertEqual(r.status, "ready")
        self.assertIsNone(r.planned_rest_days)

    def test_measurement_response_fields(self):
        from schemas.pasture_live import MeasurementResponse
        r = MeasurementResponse(
            public_id="abc", paddock_id=1, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha="2000",
            utilization_pct="50", total_dm_kg="20000",
            usable_dm_kg="10000", forage_species="brachiaria",
            notes="", formula_version="pasture_live.v1",
            created_at="2026-07-01",
        )
        self.assertEqual(r.formula_version, "pasture_live.v1")
        self.assertIsNone(r.estimated_height_cm)

    def test_dashboard_response_fields(self):
        from schemas.pasture_live import DashboardResponse
        r = DashboardResponse(
            total_paddocks=5, active_paddocks=4,
            grazing_count=1, resting_count=2, ready_count=1,
            attention_count=0, total_area_ha="50",
            total_usable_dm_kg="100000", measurements_total=20,
        )
        self.assertEqual(r.total_paddocks, 5)
        self.assertEqual(r.measurements_total, 20)

    def test_pagination_response_fields(self):
        from schemas.pasture_live import PaginationResponse
        r = PaginationResponse(limit=25, offset=0, returned=3, total=10, has_more=True)
        self.assertTrue(r.has_more)
        self.assertEqual(r.returned, 3)

    def test_notes_max_length_enforced(self):
        from schemas.pasture_live import PaddockCreateRequest
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            PaddockCreateRequest(name="P1", area_ha="10", notes="x" * 2001)

    def test_decimal_strings_not_float(self):
        from schemas.pasture_live import MeasurementCreateRequest
        m = MeasurementCreateRequest(available_dm_kg_ha="2000", utilization_pct="50")
        self.assertIsInstance(m.available_dm_kg_ha, str)
        self.assertIsInstance(m.utilization_pct, str)


@unittest.skipUnless(HAS_FASTAPI, "FastAPI/Pydantic não disponível")
class TestPastureLiveRouter(unittest.TestCase):
    def test_router_prefix(self):
        from routers.pasture_live import router
        self.assertEqual(router.prefix, "/api/v2/farms")
        self.assertIn("pasture_live", router.tags)

    def test_endpoints_exist(self):
        from routers.pasture_live import router
        routes = {r.path for r in router.routes}
        self.assertIn("/{farm_uuid}/pasture-live/dashboard", routes)
        self.assertIn("/{farm_uuid}/pasture-live/paddocks", routes)
        self.assertIn("/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}", routes)

    def test_measurements_endpoint_exists(self):
        from routers.pasture_live import router
        routes = {r.path for r in router.routes}
        self.assertIn("/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/measurements", routes)

    def test_events_endpoint_exists(self):
        from routers.pasture_live import router
        routes = {r.path for r in router.routes}
        self.assertIn("/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/events", routes)

    def test_grazing_endpoints_exist(self):
        from routers.pasture_live import router
        routes = {r.path for r in router.routes}
        self.assertIn("/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/start-grazing", routes)
        self.assertIn("/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/finish-grazing", routes)

    def test_autonomy_sources_endpoint_exists(self):
        from routers.pasture_live import router
        routes = {r.path for r in router.routes}
        self.assertIn("/{farm_uuid}/pasture-live/autonomy-sources", routes)

    def test_cache_headers_set(self):
        from routers.pasture_live import _cache_headers
        from unittest.mock import MagicMock
        response = MagicMock()
        _cache_headers(response)
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")
        self.assertEqual(response.headers["Pragma"], "no-cache")
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")

    def test_request_id_valid(self):
        from routers.pasture_live import _REQUEST_ID
        self.assertTrue(_REQUEST_ID.fullmatch("test-123"))
        self.assertTrue(_REQUEST_ID.fullmatch("abc:def"))
        self.assertIsNone(_REQUEST_ID.fullmatch("invalid space"))
        self.assertIsNone(_REQUEST_ID.fullmatch("a" * 101))

    def test_feature_flag_default_false(self):
        val = os.getenv("ENABLE_PASTURE_LIVE", "false")
        self.assertNotIn(val.lower(), {"1", "true", "yes"})


if __name__ == "__main__":
    unittest.main()
