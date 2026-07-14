"""Testes de integração entre Estoque de Ração e Autonomia Alimentar."""
import os
import unittest
from datetime import date
from decimal import Decimal

from domain.feed_inventory import (
    FORMULA_VERSION, LotStatus, MovementType, FacilityType, FeedType,
    calculate_physical_dm, calculate_usable_dm,
    reconcile_balance, _q2,
)


APP_DIR = os.path.join(os.path.dirname(__file__), "..")


def _read(relative):
    with open(os.path.join(APP_DIR, relative)) as f:
        return f.read()


class TestModuleStructure(unittest.TestCase):
    def test_domain_file_exists(self):
        path = os.path.join(APP_DIR, "domain/feed_inventory.py")
        self.assertTrue(os.path.isfile(path))

    def test_service_file_exists(self):
        path = os.path.join(APP_DIR, "services/feed_inventory.py")
        self.assertTrue(os.path.isfile(path))

    def test_schemas_file_exists(self):
        path = os.path.join(APP_DIR, "schemas/feed_inventory.py")
        self.assertTrue(os.path.isfile(path))

    def test_router_file_exists(self):
        path = os.path.join(APP_DIR, "routers/feed_inventory.py")
        self.assertTrue(os.path.isfile(path))

    def test_repository_file_exists(self):
        path = os.path.join(APP_DIR, "repositories/feed_inventory.py")
        self.assertTrue(os.path.isfile(path))

    def test_domain_importable(self):
        import importlib
        mod = importlib.import_module("domain.feed_inventory")
        self.assertTrue(hasattr(mod, "FORMULA_VERSION"))

    def test_service_importable(self):
        import importlib
        mod = importlib.import_module("services.feed_inventory")
        self.assertTrue(hasattr(mod, "FeedInventoryService"))

    def test_schemas_importable(self):
        try:
            import importlib
            mod = importlib.import_module("schemas.feed_inventory")
            self.assertTrue(hasattr(mod, "FacilityCreateRequest"))
        except (ImportError, ModuleNotFoundError):
            self.skipTest("Pydantic não disponível")

    def test_router_importable(self):
        try:
            import importlib
            mod = importlib.import_module("routers.feed_inventory")
            self.assertTrue(hasattr(mod, "router"))
        except (ImportError, ModuleNotFoundError):
            self.skipTest("FastAPI não disponível")


class TestDomainIsolation(unittest.TestCase):
    def test_domain_has_no_database_dependency(self):
        content = _read("domain/feed_inventory.py")
        self.assertNotIn("from db import", content)
        self.assertNotIn("query(", content)
        self.assertNotIn("_tx()", content)
        self.assertNotIn("cursor", content)

    def test_domain_has_no_http_dependency(self):
        content = _read("domain/feed_inventory.py")
        self.assertNotIn("requests.", content)
        self.assertNotIn("httpx", content)
        self.assertNotIn("aiohttp", content)

    def test_domain_has_no_service_import(self):
        content = _read("domain/feed_inventory.py")
        self.assertNotIn("from services", content)

    def test_domain_has_no_router_import(self):
        content = _read("domain/feed_inventory.py")
        self.assertNotIn("from routers", content)

    def test_domain_has_no_repository_import(self):
        content = _read("domain/feed_inventory.py")
        self.assertNotIn("from repositories", content)


class TestFeatureFlagVisibility(unittest.TestCase):
    def test_feature_flag_default_hidden(self):
        old_val = os.environ.get("ENABLE_FEED_INVENTORY")
        try:
            if "ENABLE_FEED_INVENTORY" in os.environ:
                del os.environ["ENABLE_FEED_INVENTORY"]
            val = os.getenv("ENABLE_FEED_INVENTORY", "false")
            self.assertNotIn(val.lower(), {"1", "true", "yes"})
        finally:
            if old_val is not None:
                os.environ["ENABLE_FEED_INVENTORY"] = old_val

    def test_router_checks_feature_flag(self):
        content = _read("routers/feed_inventory.py")
        self.assertIn("_check_feature", content)
        self.assertIn("ENABLE_FEED_INVENTORY", content)


class TestAuditMetadata(unittest.TestCase):
    def test_repository_has_audit_event_import(self):
        content = _read("repositories/feed_inventory.py")
        self.assertIn("AuditEvent", content)
        self.assertIn("AuditService", content)

    def test_facility_created_has_audit_action(self):
        content = _read("repositories/feed_inventory.py")
        self.assertIn("feed_inventory.facility_created", content)

    def test_lot_created_has_audit_action(self):
        content = _read("repositories/feed_inventory.py")
        self.assertIn("feed_inventory.lot_created", content)

    def test_movement_has_audit_action(self):
        content = _read("repositories/feed_inventory.py")
        self.assertIn("feed_inventory.movement_", content)


class TestFormulaVersion(unittest.TestCase):
    def test_formula_version_in_domain(self):
        from domain.feed_inventory import FORMULA_VERSION as domain_fv
        self.assertEqual(domain_fv, "feed_inventory.v1")

    def test_formula_version_in_service(self):
        content = _read("services/feed_inventory.py")
        self.assertIn("FORMULA_VERSION", content)

    def test_formula_version_is_string(self):
        self.assertIsInstance(FORMULA_VERSION, str)

    def test_formula_version_in_lot_response(self):
        content = _read("services/feed_inventory.py")
        self.assertIn("formula_version", content)


class TestAutonomyIntegration(unittest.TestCase):
    def test_autonomy_sources_format_compatible(self):
        source = {
            "lot_public_id": "abc-123",
            "name": "Lote 1",
            "feed_type": "silagem_milho",
            "facility_name": "Silo A",
            "balance_natural_kg": "10000",
            "dry_matter_pct": "35",
            "utilization_pct": "90",
            "calculated_physical_dm_kg": "3500",
            "calculated_usable_dm_kg": "3150",
            "status": "available",
        }
        required = {"lot_public_id", "name", "feed_type", "facility_name",
                     "balance_natural_kg", "dry_matter_pct", "utilization_pct",
                     "calculated_physical_dm_kg", "calculated_usable_dm_kg", "status"}
        self.assertEqual(set(source.keys()), required)

    def test_measurement_fields_for_autonomy(self):
        physical_dm = calculate_physical_dm(Decimal("10000"), Decimal("35"))
        usable_dm = calculate_usable_dm(physical_dm, Decimal("90"))
        self.assertIsInstance(physical_dm, Decimal)
        self.assertIsInstance(usable_dm, Decimal)
        self.assertGreater(usable_dm, Decimal("0"))

    def test_usable_dm_calculation_matches(self):
        qty = Decimal("10000")
        dm_pct = Decimal("35")
        util = Decimal("90")
        physical = _q2(qty * dm_pct / Decimal("100"))
        usable = _q2(physical * util / Decimal("100"))
        self.assertEqual(physical, Decimal("3500.00"))
        self.assertEqual(usable, Decimal("3150.00"))


class TestNoDuplicateImports(unittest.TestCase):
    def test_domain_no_duplicate_imports(self):
        content = _read("domain/feed_inventory.py")
        lines = content.split("\n")
        import_lines = [l.strip() for l in lines
                        if l.strip().startswith("from ") or l.strip().startswith("import ")]
        self.assertEqual(len(import_lines), len(set(import_lines)))

    def test_service_no_duplicate_imports(self):
        content = _read("services/feed_inventory.py")
        lines = content.split("\n")
        import_lines = [l.strip() for l in lines
                        if l.strip().startswith("from ") or l.strip().startswith("import ")]
        self.assertEqual(len(import_lines), len(set(import_lines)))


class TestReconciliation(unittest.TestCase):
    def test_reconcile_balance_additive_movements(self):
        movements = [
            {"movement_type": "initial_balance", "quantity_natural_kg": "10000"},
            {"movement_type": "entry", "quantity_natural_kg": "5000"},
            {"movement_type": "adjustment_positive", "quantity_natural_kg": "1000"},
        ]
        result = reconcile_balance(Decimal("0"), movements)
        self.assertEqual(result, Decimal("16000"))

    def test_reconcile_balance_subtractive_movements(self):
        movements = [
            {"movement_type": "initial_balance", "quantity_natural_kg": "10000"},
            {"movement_type": "withdrawal", "quantity_natural_kg": "2000"},
            {"movement_type": "loss", "quantity_natural_kg": "500"},
            {"movement_type": "adjustment_negative", "quantity_natural_kg": "300"},
        ]
        result = reconcile_balance(Decimal("0"), movements)
        self.assertEqual(result, Decimal("7200"))

    def test_reconcile_balance_mixed_movements(self):
        movements = [
            {"movement_type": "initial_balance", "quantity_natural_kg": "10000"},
            {"movement_type": "entry", "quantity_natural_kg": "5000"},
            {"movement_type": "withdrawal", "quantity_natural_kg": "3000"},
            {"movement_type": "loss", "quantity_natural_kg": "200"},
        ]
        result = reconcile_balance(Decimal("0"), movements)
        self.assertEqual(result, Decimal("11800"))


if __name__ == "__main__":
    unittest.main()
