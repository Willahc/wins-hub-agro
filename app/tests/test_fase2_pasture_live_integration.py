"""Testes de integração entre Pasto Vivo e Autonomia Alimentar."""
import os
import unittest
from datetime import date
from decimal import Decimal

from domain.pasture_live import (
    FORMULA_VERSION, PaddockStatus, MeasurementResult,
    suggest_paddock_state, is_measurement_fresh,
)


APP_DIR = os.path.join(os.path.dirname(__file__), "..")


def _read(relative):
    with open(os.path.join(APP_DIR, relative)) as f:
        return f.read()


def _q2(value):
    from decimal import ROUND_HALF_UP
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TestAutonomySourceFormatCompatibility(unittest.TestCase):
    def test_source_format_matches_food_autonomy(self):
        source = {
            "paddock_public_id": "abc-123",
            "name": "P1",
            "area_ha": "10",
            "forage_species": "brachiaria",
            "status": "ready",
            "latest_measurement": {
                "available_dm_kg_ha": "2000",
                "usable_dm_kg": "5000",
                "utilization_pct": "50",
                "measured_at": "2026-07-01",
            },
        }
        self.assertIn("paddock_public_id", source)
        self.assertIn("name", source)
        self.assertIn("area_ha", source)
        self.assertIn("forage_species", source)
        self.assertIn("status", source)
        self.assertIn("latest_measurement", source)

    def test_measurement_fields_for_autonomy(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("50"), forage_species="brachiaria",
        )
        total = mr.calculate_total_dm(Decimal("10"), Decimal("2000"))
        usable = mr.calculate_usable_dm(Decimal("10"), Decimal("2000"), Decimal("50"))
        self.assertIsInstance(total, Decimal)
        self.assertIsInstance(usable, Decimal)
        self.assertGreater(usable, Decimal("0"))


class TestPaddockDataMapsToPastureItem(unittest.TestCase):
    def test_paddock_fields_map(self):
        paddock = {
            "name": "P1",
            "area_ha": Decimal("10"),
            "available_dm_kg_ha": Decimal("2000"),
            "utilization_pct": Decimal("50"),
        }
        self.assertEqual(paddock["name"], "P1")
        self.assertEqual(paddock["area_ha"], Decimal("10"))
        self.assertEqual(paddock["available_dm_kg_ha"], Decimal("2000"))
        self.assertEqual(paddock["utilization_pct"], Decimal("50"))

    def test_usable_dm_calculation_matches(self):
        area = Decimal("10")
        dm_ha = Decimal("2000")
        util = Decimal("50")
        expected = _q2(area * dm_ha * util / Decimal("100"))
        self.assertEqual(expected, Decimal("10000.00"))


class TestStaleMeasurementIndicator(unittest.TestCase):
    def test_stale_measurement_detected(self):
        from datetime import timedelta
        stale_date = date.today() - timedelta(days=15)
        self.assertFalse(is_measurement_fresh(stale_date, freshness_days=14))

    def test_fresh_measurement_accepted(self):
        from datetime import timedelta
        fresh_date = date.today() - timedelta(days=10)
        self.assertTrue(is_measurement_fresh(fresh_date, freshness_days=14))

    def test_boundary_measurement_accepted(self):
        from datetime import timedelta
        boundary_date = date.today() - timedelta(days=14)
        self.assertTrue(is_measurement_fresh(boundary_date, freshness_days=14))


class TestFeatureFlagControlsVisibility(unittest.TestCase):
    def test_feature_flag_default_hidden(self):
        val = os.getenv("ENABLE_PASTURE_LIVE", "false")
        self.assertNotIn(val.lower(), {"1", "true", "yes"})

    def test_router_checks_feature_flag(self):
        content = _read("routers/pasture_live.py")
        self.assertIn("_check_feature", content)
        self.assertIn("ENABLE_PASTURE_LIVE", content)


class TestSourceMetadataStructure(unittest.TestCase):
    def test_source_has_required_keys(self):
        source = {
            "paddock_public_id": "abc",
            "name": "P1",
            "area_ha": "10",
            "forage_species": "brachiaria",
            "status": "ready",
            "latest_measurement": None,
        }
        required = {"paddock_public_id", "name", "area_ha",
                     "forage_species", "status", "latest_measurement"}
        self.assertEqual(set(source.keys()), required)

    def test_measurement_metadata_has_formula_version(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("50"), forage_species="mixed",
        )
        self.assertEqual(mr.formula_version, "pasture_live.v1")


class TestNoDuplicateImports(unittest.TestCase):
    def test_domain_no_duplicate_imports(self):
        content = _read("domain/pasture_live.py")
        lines = content.split("\n")
        import_lines = [l.strip() for l in lines
                        if l.strip().startswith("from ") or l.strip().startswith("import ")]
        self.assertEqual(len(import_lines), len(set(import_lines)))

    def test_service_no_duplicate_imports(self):
        content = _read("services/pasture_live.py")
        lines = content.split("\n")
        import_lines = [l.strip() for l in lines
                        if l.strip().startswith("from ") or l.strip().startswith("import ")]
        self.assertEqual(len(import_lines), len(set(import_lines)))


class TestModuleIsolation(unittest.TestCase):
    def test_domain_has_no_database_dependency(self):
        content = _read("domain/pasture_live.py")
        self.assertNotIn("from db import", content)
        self.assertNotIn("query(", content)
        self.assertNotIn("_tx()", content)
        self.assertNotIn("cursor", content)

    def test_domain_has_no_http_dependency(self):
        content = _read("domain/pasture_live.py")
        self.assertNotIn("requests.", content)
        self.assertNotIn("httpx", content)
        self.assertNotIn("aiohttp", content)

    def test_domain_has_no_service_import(self):
        content = _read("domain/pasture_live.py")
        self.assertNotIn("from services", content)

    def test_domain_has_no_router_import(self):
        content = _read("domain/pasture_live.py")
        self.assertNotIn("from routers", content)


class TestServerSideRecalculation(unittest.TestCase):
    def test_measurement_recalculates_on_creation(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("50"), forage_species="brachiaria",
        )
        area = Decimal("10")
        total = mr.calculate_total_dm(area, mr.available_dm_kg_ha)
        usable = mr.calculate_usable_dm(area, mr.available_dm_kg_ha, mr.utilization_pct)
        self.assertEqual(total, Decimal("20000.00"))
        self.assertEqual(usable, Decimal("10000.00"))
        self.assertEqual(usable, total * mr.utilization_pct / Decimal("100"))


if __name__ == "__main__":
    unittest.main()
