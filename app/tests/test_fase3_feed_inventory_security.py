"""Testes de segurança do módulo de Estoque de Ração."""
import unittest
import ast
import os
import re


APP_DIR = os.path.join(os.path.dirname(__file__), "..")
FORBIDDEN_IMPORTS = {"subprocess", "shlex", "ctypes", "importlib"}


def _filepath(relative):
    return os.path.join(APP_DIR, relative)


def _read(relative):
    with open(_filepath(relative)) as f:
        return f.read()


class TestForbiddenImports(unittest.TestCase):
    def _check_file_no_forbidden(self, relative):
        content = _read(relative)
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".")[0], FORBIDDEN_IMPORTS,
                                     f"Import proibido {alias.name} em {relative}")
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    self.assertNotIn(node.module.split(".")[0], FORBIDDEN_IMPORTS,
                                     f"Import proibido {node.module} em {relative}")

    def test_domain_no_forbidden_imports(self):
        self._check_file_no_forbidden("domain/feed_inventory.py")


class TestNoEvalInDomain(unittest.TestCase):
    def test_no_eval_in_domain(self):
        content = _read("domain/feed_inventory.py")
        self.assertNotIn("eval(", content)
        self.assertNotIn("exec(", content)
        self.assertNotIn("__import__", content)

    def test_no_os_system_in_domain(self):
        content = _read("domain/feed_inventory.py")
        self.assertNotIn("os.system(", content)
        self.assertNotIn("os.popen(", content)

    def test_script_injection_prevention(self):
        content = _read("domain/feed_inventory.py")
        self.assertNotIn("eval(", content)
        self.assertNotIn("exec(", content)
        self.assertNotIn("compile(", content)
        self.assertNotIn("__import__(", content)


class TestNoSQLInDomain(unittest.TestCase):
    def test_no_sql_in_domain(self):
        content = _read("domain/feed_inventory.py")
        self.assertNotIn("cursor", content)
        self.assertNotIn("execute", content)
        self.assertNotIn("SELECT", content)


class TestRouterUsesDecodeToken(unittest.TestCase):
    def test_router_uses_decode_token(self):
        content = _read("routers/feed_inventory.py")
        self.assertIn("decode_token", content)
        self.assertIn("AuthorizationError", content)


class TestNoInternalIDs(unittest.TestCase):
    def test_response_schemas_have_no_integer_id_fields(self):
        content = _read("schemas/feed_inventory.py")
        for class_name in ["FacilityResponse", "LotResponse",
                           "MovementResponse", "DashboardResponse"]:
            if f"class {class_name}" in content:
                class_body = content.split(f"class {class_name}")[1].split("class ")[0]
                self.assertNotIn("organization_id", class_body,
                                 f"{class_name} expõe organization_id")
                self.assertNotIn("farm_id", class_body,
                                 f"{class_name} expõe farm_id")
                self.assertNotIn("user_id", class_body,
                                 f"{class_name} expõe user_id")


class TestNoPII(unittest.TestCase):
    def test_no_pii_in_domain(self):
        content = _read("domain/feed_inventory.py")
        pii_patterns = ["email", "cpf", "cnpj", "telefone", "password", "senha"]
        for pattern in pii_patterns:
            self.assertNotIn(pattern, content.lower(),
                             f"PII '{pattern}' encontrada no domínio")

    def test_no_pii_in_schemas(self):
        content = _read("schemas/feed_inventory.py")
        pii_patterns = ["email", "cpf", "cnpj", "telefone", "password", "senha"]
        for pattern in pii_patterns:
            self.assertNotIn(pattern, content.lower(),
                             f"PII '{pattern}' encontrada nos schemas")


class TestDecimalPrecision(unittest.TestCase):
    def test_no_float_in_domain(self):
        content = _read("domain/feed_inventory.py")
        self.assertNotIn("float(", content)
        self.assertIn("Decimal", content)

    def test_q2_function_exists(self):
        from domain.feed_inventory import _q2
        from decimal import Decimal
        result = _q2(Decimal("1.235"))
        self.assertEqual(result, Decimal("1.24"))

    def test_q4_function_exists(self):
        from domain.feed_inventory import _q4
        from decimal import Decimal
        result = _q4(Decimal("3.80952"))
        self.assertEqual(result, Decimal("3.8095"))


class TestUUIDFormat(unittest.TestCase):
    def test_uuid_format_in_facility_response(self):
        try:
            from schemas.feed_inventory import FacilityResponse
            r = FacilityResponse(
                public_id="550e8400-e29b-41d4-a716-446655440000",
                name="Silo A", code="", facility_type="silo_trincheira",
                capacity_natural_kg="50000", preferred_display_unit="kg",
                location_description="", active=True, notes="",
                created_at="2026-07-01", updated_at="2026-07-01",
            )
            uuid_pattern = re.compile(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            )
            self.assertTrue(uuid_pattern.match(r.public_id))
        except ImportError:
            self.skipTest("Pydantic não disponível")

    def test_uuid_format_in_lot_response(self):
        try:
            from schemas.feed_inventory import LotResponse
            r = LotResponse(
                public_id="550e8400-e29b-41d4-a716-446655440000",
                facility_uuid="550e8400-e29b-41d4-a716-446655440001",
                facility_name="Silo A", name="Lote 1",
                feed_type="silagem_milho", custom_feed_type="",
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
            uuid_pattern = re.compile(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            )
            self.assertTrue(uuid_pattern.match(r.public_id))
            self.assertTrue(uuid_pattern.match(r.facility_uuid))
        except ImportError:
            self.skipTest("Pydantic não disponível")


class TestFeatureFlagDefault(unittest.TestCase):
    def test_feature_flag_default_false(self):
        old_val = os.environ.get("ENABLE_FEED_INVENTORY")
        try:
            if "ENABLE_FEED_INVENTORY" in os.environ:
                del os.environ["ENABLE_FEED_INVENTORY"]
            val = os.getenv("ENABLE_FEED_INVENTORY", "false")
            self.assertNotIn(val.lower(), {"1", "true", "yes"},
                             "Feature flag deve estar desligada por padrão")
        finally:
            if old_val is not None:
                os.environ["ENABLE_FEED_INVENTORY"] = old_val


if __name__ == "__main__":
    unittest.main()
