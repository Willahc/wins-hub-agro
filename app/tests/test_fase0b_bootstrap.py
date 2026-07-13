import importlib.util
import json
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from services.legacy_bootstrap import BootstrapInputError, LegacyMapping, run_bootstrap  # noqa: E402


def base_mapping():
    return json.loads((ROOT / "scripts/fase0/examples/legacy_mapping.synthetic.json").read_text(encoding="utf-8"))


class FakeExecutor:
    def __init__(self, report=None):
        self.calls = []
        self.report = report or {
            "mode": "dry-run", "status": "ready", "would_create": {"farms": 1},
            "existing": {}, "conflicts": [], "blocked_actions": [],
            "password": "must-not-leak", "dsn": "must-not-leak",
        }

    def process(self, payload, apply):
        self.calls.append((dict(payload), apply))
        return self.report


def load_cli():
    path = ROOT / "scripts/fase0/bootstrap_legacy.py"
    spec = importlib.util.spec_from_file_location("fase0b_bootstrap_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LegacyBootstrapUnitTest(unittest.TestCase):
    def test_parser_accepts_only_synthetic_explicit_mapping(self):
        parsed = LegacyMapping.parse(base_mapping())
        self.assertEqual(parsed.payload["legacy_client_id"], 1001)
        self.assertEqual(parsed.payload["source_schema"], "fazenda")

    def test_dry_run_is_default_and_does_not_request_apply(self):
        executor = FakeExecutor()
        report = run_bootstrap(LegacyMapping.parse(base_mapping()), executor)
        self.assertFalse(executor.calls[0][1])
        self.assertEqual(report["status"], "ready")

    def test_apply_must_be_explicit_at_service_boundary(self):
        executor = FakeExecutor({"mode": "apply", "status": "applied", "created": {"farms": 1}})
        run_bootstrap(LegacyMapping.parse(base_mapping()), executor, apply=True)
        self.assertTrue(executor.calls[0][1])

    def test_report_is_sanitized(self):
        executor = FakeExecutor()
        report = run_bootstrap(LegacyMapping.parse(base_mapping()), executor)
        self.assertNotIn("password", report)
        self.assertNotIn("dsn", report)
        self.assertNotIn("auth_subject", json.dumps(report))

    def test_source_schema_is_allowlisted(self):
        mapping = base_mapping()
        mapping["source_schema"] = "prospeccao"
        with self.assertRaises(BootstrapInputError):
            LegacyMapping.parse(mapping)

    def test_source_table_is_allowlisted(self):
        mapping = base_mapping()
        mapping["source_table"] = "fazenda_nacional"
        with self.assertRaises(BootstrapInputError):
            LegacyMapping.parse(mapping)

    def test_invalid_legacy_client_ids_are_rejected(self):
        for value in (0, -1, "invalid"):
            mapping = base_mapping()
            mapping["legacy_client_id"] = value
            with self.subTest(value=value), self.assertRaises(BootstrapInputError):
                LegacyMapping.parse(mapping)

    def test_invalid_uuid_is_rejected(self):
        mapping = base_mapping()
        mapping["farm_public_id"] = "invalid"
        with self.assertRaises(BootstrapInputError):
            LegacyMapping.parse(mapping)

    def test_missing_justification_is_rejected(self):
        mapping = base_mapping()
        mapping["justification"] = "curta"
        with self.assertRaises(BootstrapInputError):
            LegacyMapping.parse(mapping)

    def test_unknown_or_sensitive_field_is_rejected(self):
        mapping = base_mapping()
        mapping["password"] = "synthetic"
        with self.assertRaises(BootstrapInputError):
            LegacyMapping.parse(mapping)

    def test_approval_timestamp_requires_timezone(self):
        mapping = base_mapping()
        mapping["approved_at"] = "2026-01-01T00:00:00"
        with self.assertRaises(BootstrapInputError):
            LegacyMapping.parse(mapping)

    def test_invalid_role_and_access_are_rejected(self):
        for field, value in (("role", "superuser"), ("access_level", "owner")):
            mapping = base_mapping()
            mapping[field] = value
            with self.subTest(field=field), self.assertRaises(BootstrapInputError):
                LegacyMapping.parse(mapping)

    def test_cli_rejects_local_and_known_production_dsn(self):
        cli = load_cli()
        blocked = (
            "host=localhost dbname=fase0_test user=synthetic",
            "host=127.0.0.1 dbname=fase0_test user=synthetic",
            "host=db dbname=fase0_test user=synthetic",
            "host=synthetic-isolated dbname=wins_agro user=synthetic",
        )
        for dsn in blocked:
            with self.subTest(dsn=dsn), self.assertRaises(ValueError):
                cli.validate_explicit_dsn(dsn)

    def test_cli_accepts_only_explicit_nonproduction_host_shape(self):
        parsed = load_cli().validate_explicit_dsn(
            "host=synthetic-isolated dbname=fase0_test user=synthetic password=synthetic"
        )
        self.assertEqual(parsed["host"], "synthetic-isolated")

    def test_apply_confirmation_is_mandatory(self):
        cli = load_cli()
        with self.assertRaises(SystemExit) as caught:
            cli.main(["--input", str(ROOT / "scripts/fase0/examples/legacy_mapping.synthetic.json"),
                      "--dsn", "host=synthetic-isolated dbname=fase0_test user=synthetic", "--apply"])
        self.assertIn("confirm", str(caught.exception))

    def test_cli_invalid_report_is_sanitized(self):
        cli = load_cli()
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            path.write_text('{"password":"must-not-leak"}', encoding="utf-8")
            output = StringIO()
            with redirect_stdout(output):
                result = cli.main(["--input", str(path),
                    "--dsn", "host=synthetic-isolated dbname=fase0_test user=synthetic"])
        self.assertEqual(result, 2)
        self.assertIn("mapping_invalid", output.getvalue())
        self.assertNotIn("password", output.getvalue())
        self.assertNotIn("must-not-leak", output.getvalue())

    def test_cli_and_service_do_not_import_main(self):
        sources = [
            (ROOT / "scripts/fase0/bootstrap_legacy.py").read_text(encoding="utf-8"),
            (APP / "services/legacy_bootstrap.py").read_text(encoding="utf-8"),
        ]
        self.assertFalse(any("import app.main" in source or "import main" in source for source in sources))

    def test_sql_declares_idempotency_conflicts_and_audit(self):
        sql = (ROOT / "scripts/fase0/030_legacy_bootstrap_idempotent.sql").read_text(encoding="utf-8")
        for token in ("pg_advisory_xact_lock", "membership_role_or_scope_conflict",
                      "farm_organization_conflict", "legacy_link_conflict", "audit_events"):
            self.assertIn(token, sql)
        self.assertNotIn("prospeccao.fazenda_nacional", sql)

    def test_legacy_link_has_explicit_source_and_cross_org_fk(self):
        sql = (ROOT / "scripts/fase0/020_legacy_mapping_schema.sql").read_text(encoding="utf-8")
        self.assertIn("source_schema = 'fazenda' AND source_table = 'cliente'", sql)
        self.assertIn("FOREIGN KEY (operational_farm_id, organization_id)", sql)
        self.assertIn("REFERENCES fazenda.cliente(id)", sql)

    def test_harness_has_isolation_cleanup_and_no_production_exec(self):
        shell = (ROOT / "scripts/fase0/test_foundation_postgres.sh").read_text(encoding="utf-8")
        for token in ("--network none", "--tmpfs", "--rm", "trap cleanup", "container_removed=true"):
            self.assertIn(token, shell)
        self.assertNotIn("docker exec wins_agro_v1-db-1", shell)
        self.assertNotIn("docker pull", shell)

    def test_grants_revoke_public_and_separate_readonly(self):
        sql = (ROOT / "scripts/fase0/090_foundation_grants.sql").read_text(encoding="utf-8")
        self.assertIn("REVOKE ALL ON SCHEMA foundation FROM PUBLIC", sql)
        self.assertIn('foundation_readonly_role', sql)
        self.assertNotIn("GRANT CREATE", sql)

    def test_down_script_has_no_cascade(self):
        sql = (ROOT / "scripts/fase0/099_foundation_schema_down.sql").read_text(encoding="utf-8").lower()
        self.assertNotIn("cascade", "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--")))
        self.assertIn("drop table foundation.legacy_farm_links", sql)


if __name__ == "__main__":
    unittest.main()
