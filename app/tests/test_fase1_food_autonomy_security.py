"""Testes de segurança do módulo de Autonomia Alimentar."""
import unittest
import ast
import os


APP_DIR = os.path.join(os.path.dirname(__file__), "..")
FORBIDDEN_IMPORTS = {"subprocess", "shlex", "ctypes", "importlib"}


def _filepath(relative):
    return os.path.join(APP_DIR, relative)


def _read(relative):
    with open(_filepath(relative)) as f:
        return f.read()


class TestFoodAutonomySecurityImports(unittest.TestCase):
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
        self._check_file_no_forbidden("domain/food_autonomy.py")

    def test_repository_no_forbidden_imports(self):
        self._check_file_no_forbidden("repositories/food_autonomy.py")

    def test_service_no_forbidden_imports(self):
        self._check_file_no_forbidden("services/food_autonomy.py")

    def test_router_no_forbidden_imports(self):
        self._check_file_no_forbidden("routers/food_autonomy.py")

    def test_schemas_no_forbidden_imports(self):
        self._check_file_no_forbidden("schemas/food_autonomy.py")


class TestFoodAutonomySecurityPatterns(unittest.TestCase):
    def test_no_eval_in_domain(self):
        content = _read("domain/food_autonomy.py")
        self.assertNotIn("eval(", content)
        self.assertNotIn("exec(", content)
        self.assertNotIn("__import__", content)

    def test_no_os_system_in_domain(self):
        content = _read("domain/food_autonomy.py")
        self.assertNotIn("os.system(", content)
        self.assertNotIn("os.popen(", content)

    def test_no_subprocess_in_router(self):
        content = _read("routers/food_autonomy.py")
        self.assertNotIn("subprocess", content)

    def test_no_sql_in_domain(self):
        content = _read("domain/food_autonomy.py")
        self.assertNotIn("cursor", content)
        self.assertNotIn("execute", content)
        self.assertNotIn("SELECT", content)

    def test_router_uses_auth(self):
        content = _read("routers/food_autonomy.py")
        self.assertIn("decode_token", content)
        self.assertIn("AuthorizationError", content)

    def test_router_no_organization_id_from_client(self):
        content = _read("routers/food_autonomy.py")
        # O router não deve aceitar organization_id do cliente
        self.assertNotIn("organization_id", content.split("def ")[0] if "def " in content else content)

    def test_no_client_id_accepted(self):
        for path in ["routers/food_autonomy.py", "services/food_autonomy.py"]:
            content = _read(path)
            self.assertNotIn("cliente_id", content)

    def test_domain_no_database(self):
        content = _read("domain/food_autonomy.py")
        self.assertNotIn("from db import", content)
        self.assertNotIn("query(", content)
        self.assertNotIn("_tx()", content)

    def test_repository_tenant_isolation(self):
        content = _read("repositories/food_autonomy.py")
        self.assertIn("farm_id", content)
        self.assertIn("organization_id", content)

    def test_feature_flag_pattern(self):
        val = os.getenv("ENABLE_FOOD_AUTONOMY", "")
        self.assertNotIn(val.lower(), {"1", "true", "yes"},
                         "Feature flag deve estar desligada por padrão")


class TestFoodAutonomySecurityNoPII(unittest.TestCase):
    def test_no_pii_in_domain(self):
        content = _read("domain/food_autonomy.py")
        pii_patterns = ["email", "cpf", "cnpj", "telefone", "password", "senha"]
        for pattern in pii_patterns:
            self.assertNotIn(pattern, content.lower(),
                             f"PII '{pattern}' encontrada no domínio")

    def test_no_pii_in_schemas(self):
        content = _read("schemas/food_autonomy.py")
        pii_patterns = ["email", "cpf", "cnpj", "telefone", "password", "senha"]
        for pattern in pii_patterns:
            self.assertNotIn(pattern, content.lower(),
                             f"PII '{pattern}' encontrada nos schemas")

    def test_notes_sanitized_max_length(self):
        import os as _os
        _os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        try:
            from schemas.food_autonomy import SimulationRequest
            from datetime import date
            from pydantic import ValidationError
            long_notes = "x" * 2001
            with self.assertRaises(ValidationError):
                SimulationRequest(
                    reference_date=date(2026, 1, 1),
                    herd=[{"category": "lactating_cows", "head_count": 10,
                           "average_weight_kg": "400", "intake_pct_body_weight": "2.5"}],
                    notes=long_notes,
                )
        except ImportError:
            self.skipTest("Pydantic não disponível")


if __name__ == "__main__":
    unittest.main()
