import ast
import importlib
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from core.legacy_compatibility import LegacyCompatibilitySettings  # noqa: E402
from domain.audit import sanitize_metadata  # noqa: E402


class AuditSqlImportsTest(unittest.TestCase):
    def test_audit_sanitizes_secrets_and_payload(self):
        clean = sanitize_metadata({
            "reason_code": "synthetic_denial", "password": "never", "access_token": "never",
            "cookie": "never", "full_payload": {"private": "never"}, "permission": "farm.read",
        })
        self.assertEqual(clean, {"reason_code": "synthetic_denial", "permission": "farm.read"})
        serialized = repr(clean).lower()
        self.assertNotIn("password", serialized)
        self.assertNotIn("token", serialized)

    def test_legacy_compatibility_is_disabled_and_not_hardcoded(self):
        old_enabled = os.environ.pop("ENABLE_LEGACY_ORGANIZATION_COMPATIBILITY", None)
        old_id = os.environ.pop("LEGACY_ORGANIZATION_PUBLIC_ID", None)
        try:
            settings = LegacyCompatibilitySettings.from_environment()
            self.assertFalse(settings.enabled)
            self.assertIsNone(settings.organization_public_id)
            os.environ["ENABLE_LEGACY_ORGANIZATION_COMPATIBILITY"] = "true"
            with self.assertRaises(RuntimeError):
                LegacyCompatibilitySettings.from_environment()
        finally:
            if old_enabled is not None:
                os.environ["ENABLE_LEGACY_ORGANIZATION_COMPATIBILITY"] = old_enabled
            else:
                os.environ.pop("ENABLE_LEGACY_ORGANIZATION_COMPATIBILITY", None)
            if old_id is not None:
                os.environ["LEGACY_ORGANIZATION_PUBLIC_ID"] = old_id

    def test_sql_is_structural_reversible_and_separates_prospecting(self):
        files = sorted((ROOT / "scripts" / "fase0").glob("*.sql"))
        self.assertEqual([path.name for path in files], [
            "001_foundation_schema.sql", "002_reference_units.sql", "010_legacy_bootstrap_template.sql",
            "020_legacy_mapping_schema.sql", "030_legacy_bootstrap_idempotent.sql",
            "040_legacy_bootstrap_rollback.sql", "090_foundation_grants.sql",
            "099_foundation_schema_down.sql",
        ])
        schema = files[0].read_text(encoding="utf-8").lower()
        self.assertIn("create table foundation.operational_farms", schema)
        self.assertIn("foreign key (farm_id, organization_id)", schema)
        self.assertNotIn("alter table prospeccao", schema)
        self.assertNotRegex(schema, r"organization_id\s*=\s*1")
        self.assertNotRegex(schema, r"\b(drop|truncate)\s+table\b")
        for path in files:
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("CHANGE-ME", text)

    def test_new_module_import_does_not_open_database(self):
        db = importlib.import_module("db")
        self.assertIsNone(db._POOL)
        importlib.import_module("repositories.foundation")
        self.assertIsNone(db._POOL)

    def test_foundation_python_has_no_eval_call(self):
        paths = list((APP / "core").glob("*.py")) + list((APP / "domain").glob("*.py"))
        for path in paths:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
            self.assertFalse(any(isinstance(node.func, ast.Name) and node.func.id == "eval" for node in calls), path)


if __name__ == "__main__":
    unittest.main()
