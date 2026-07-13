"""Testes de segurança do módulo de Pasto Vivo."""
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


class TestPastureLiveSecurityImports(unittest.TestCase):
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
        self._check_file_no_forbidden("domain/pasture_live.py")

    def test_repository_no_forbidden_imports(self):
        self._check_file_no_forbidden("repositories/pasture_live.py")

    def test_service_no_forbidden_imports(self):
        self._check_file_no_forbidden("services/pasture_live.py")

    def test_router_no_forbidden_imports(self):
        self._check_file_no_forbidden("routers/pasture_live.py")

    def test_schemas_no_forbidden_imports(self):
        self._check_file_no_forbidden("schemas/pasture_live.py")


class TestPastureLiveSecurityPatterns(unittest.TestCase):
    def test_no_eval_in_domain(self):
        content = _read("domain/pasture_live.py")
        self.assertNotIn("eval(", content)
        self.assertNotIn("exec(", content)
        self.assertNotIn("__import__", content)

    def test_no_os_system_in_domain(self):
        content = _read("domain/pasture_live.py")
        self.assertNotIn("os.system(", content)
        self.assertNotIn("os.popen(", content)

    def test_no_subprocess_in_router(self):
        content = _read("routers/pasture_live.py")
        self.assertNotIn("subprocess", content)

    def test_no_sql_in_domain(self):
        content = _read("domain/pasture_live.py")
        self.assertNotIn("cursor", content)
        self.assertNotIn("execute", content)
        self.assertNotIn("SELECT", content)

    def test_router_uses_auth(self):
        content = _read("routers/pasture_live.py")
        self.assertIn("decode_token", content)
        self.assertIn("AuthorizationError", content)

    def test_no_internal_ids_in_api_response(self):
        """Verifica que o schema de resposta não expõe IDs internos do banco."""
        content = _read("schemas/pasture_live.py")
        for class_name in ["PaddockResponse", "PaddockSummary",
                           "EventResponse", "EventSummary",
                           "DashboardResponse"]:
            if f"class {class_name}" in content:
                class_body = content.split(f"class {class_name}")[1].split("class ")[0]
                self.assertNotIn("organization_id", class_body,
                                 f"{class_name} expõe organization_id")
                self.assertNotIn("farm_id", class_body,
                                 f"{class_name} expõe farm_id")
                self.assertNotIn("user_id", class_body,
                                 f"{class_name} expõe user_id")

    def test_html_injection_prevention_in_notes(self):
        """Verifica que o schema limita o tamanho de notes."""
        try:
            from schemas.pasture_live import PaddockCreateRequest
            from pydantic import ValidationError
            long_notes = "<script>alert('xss')</script>" * 100
            with self.assertRaises(ValidationError):
                PaddockCreateRequest(name="P1", area_ha="10", notes=long_notes)
        except ImportError:
            self.skipTest("Pydantic não disponível")

    def test_script_injection_prevention(self):
        """Verifica que o domínio não usa eval/exec."""
        content = _read("domain/pasture_live.py")
        self.assertNotIn("eval(", content)
        self.assertNotIn("exec(", content)
        self.assertNotIn("compile(", content)
        self.assertNotIn("__import__(", content)


class TestPastureLiveSecurityUUID(unittest.TestCase):
    def test_uuid_format_in_response(self):
        """Verifica que public_id é retornado como string UUID."""
        try:
            from schemas.pasture_live import PaddockResponse
            r = PaddockResponse(
                public_id="550e8400-e29b-41d4-a716-446655440000",
                name="P1", area_ha="10", forage_species="mixed",
                rest_days=30, status="ready", is_inactive=False,
                is_unavailable=False, notes="", created_at="2026-07-01",
                updated_at="2026-07-01",
            )
            self.assertIsNotNone(r.public_id)
            uuid_pattern = re.compile(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            )
            self.assertTrue(uuid_pattern.match(r.public_id))
        except ImportError:
            self.skipTest("Pydantic não disponível")


class TestPastureLiveSecurityIsolation(unittest.TestCase):
    def test_cross_tenant_isolation_pattern(self):
        """Verifica que o repositório filtra por farm_id."""
        content = _read("repositories/pasture_live.py")
        self.assertIn("farm_id", content)
        self.assertIn("organization_id", content)

    def test_feature_flag_default_false(self):
        """Feature flag deve estar desligada por padrão."""
        val = os.getenv("ENABLE_PASTURE_LIVE", "false")
        self.assertNotIn(val.lower(), {"1", "true", "yes"},
                         "Feature flag deve estar desligada por padrão")


class TestPastureLiveSecurityWhitelists(unittest.TestCase):
    def test_measurement_method_whitelist(self):
        """Verifica que o domínio tem enum de métodos de medição."""
        from domain.pasture_live import MeasurementMethod
        methods = {m.value for m in MeasurementMethod}
        self.assertEqual(methods, {"visual", "ruler", "rising_plate",
                                   "field_sampling", "external", "other"})

    def test_event_type_whitelist(self):
        """Verifica que o domínio tem enum de tipos de evento."""
        from domain.pasture_live import EventType
        types = {e.value for e in EventType}
        self.assertIn("grazing_started", types)
        self.assertIn("grazing_finished", types)
        self.assertIn("rest_started", types)
        self.assertIn("released", types)
        self.assertIn("marked_unavailable", types)
        self.assertIn("reactivated", types)
        self.assertIn("status_adjusted", types)

    def test_paddock_status_whitelist(self):
        """Verifica que o domínio tem enum de status de pasto."""
        from domain.pasture_live import PaddockStatus
        statuses = {s.value for s in PaddockStatus}
        self.assertEqual(statuses, {"ready", "grazing", "resting", "attention",
                                    "unavailable", "inactive", "no_measurement"})


class TestPastureLiveSecurityPrecision(unittest.TestCase):
    def test_decimal_precision_in_responses(self):
        """Verifica que valores decimais usam 2 casas decimais."""
        from decimal import Decimal
        from domain.pasture_live import _q2
        self.assertEqual(_q2(Decimal("1.235")), Decimal("1.24"))
        self.assertEqual(_q2(Decimal("1.23")), Decimal("1.23"))
        self.assertEqual(_q2(Decimal("5")), Decimal("5.00"))

    def test_no_float_in_domain(self):
        """Verifica que o domínio não usa float para cálculos."""
        content = _read("domain/pasture_live.py")
        self.assertNotIn("float(", content)
        self.assertIn("Decimal", content)


class TestPastureLiveSecurityNoPII(unittest.TestCase):
    def test_no_pii_in_domain(self):
        content = _read("domain/pasture_live.py")
        pii_patterns = ["email", "cpf", "cnpj", "telefone", "password", "senha"]
        for pattern in pii_patterns:
            self.assertNotIn(pattern, content.lower(),
                             f"PII '{pattern}' encontrada no domínio")

    def test_no_pii_in_schemas(self):
        content = _read("schemas/pasture_live.py")
        pii_patterns = ["email", "cpf", "cnpj", "telefone", "password", "senha"]
        for pattern in pii_patterns:
            self.assertNotIn(pattern, content.lower(),
                             f"PII '{pattern}' encontrada nos schemas")


if __name__ == "__main__":
    unittest.main()
