import unittest
import os
import sys
import ast
import re

SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts", "fase0e2")

ALL_SCRIPTS = [
    "review_mappings.py",
    "generate_review_template.py",
    "validate_human_decisions.py",
    "finalize_review.py",
    "validate_private_package.py",
    "sanitize_review_summary.py",
]


def _read_script(name):
    path = os.path.join(SCRIPT_DIR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TestSecurityNoForbiddenDatabaseImports(unittest.TestCase):
    """1. Módulos proibidos de banco não devem ser importados"""

    def test_no_psycopg(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("psycopg", content, f"psycopg found in {s}")

    def test_no_asyncpg(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("asyncpg", content, f"asyncpg found in {s}")

    def test_no_sqlalchemy(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("sqlalchemy", content, f"sqlalchemy found in {s}")

    def test_no_app_db(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("app.db", content, f"app.db found in {s}")

    def test_no_app_main(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("app.main", content, f"app.main found in {s}")


class TestSecurityNoNetworkImports(unittest.TestCase):
    """2. Módulos proibidos de rede não devem ser importados"""

    def test_no_requests(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("import requests", content, f"import requests found in {s}")
            self.assertNotIn("from requests", content, f"from requests found in {s}")

    def test_no_httpx(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("httpx", content, f"httpx found in {s}")

    def test_no_urllib(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("urllib.request", content, f"urllib.request found in {s}")

    def test_no_socket(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("socket.connect", content, f"socket.connect found in {s}")
            self.assertNotIn("socket.socket", content, f"socket.socket found in {s}")


class TestSecurityNoSystemCalls(unittest.TestCase):
    """3. Chamadas de subprocessos e eval são proibidas"""

    def test_no_os_system(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("os.system", content, f"os.system found in {s}")

    def test_no_subprocess(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("subprocess.run", content, f"subprocess.run found in {s}")
            self.assertNotIn("subprocess.Popen", content, f"subprocess.Popen found in {s}")
            self.assertNotIn("subprocess.call", content, f"subprocess.call found in {s}")

    def test_no_eval(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("eval(", content, f"eval( found in {s}")

    def test_no_exec(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("exec(", content, f"exec( found in {s}")


class TestSecurityNoDockerOrKubectl(unittest.TestCase):
    """4. Docker e kubectl são proibidos"""

    def test_no_docker(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s).lower()
            self.assertNotIn("docker", content, f"docker found in {s}")

    def test_no_kubectl(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("kubectl", content, f"kubectl found in {s}")


class TestSecurityNoGitCommands(unittest.TestCase):
    """5. Git add/commit/push são proibidos"""

    def test_no_git_add(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("git add", content, f"git add found in {s}")

    def test_no_git_commit(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("git commit", content, f"git commit found in {s}")

    def test_no_git_push(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("git push", content, f"git push found in {s}")


class TestSecurityNoApprovedTrue(unittest.TestCase):
    """6. approved=true não deve existir no código"""

    def test_no_approved_true任何形式(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                self.assertNotIn("approved = True", stripped, f"approved = True found in {s}")
                self.assertNotIn('"approved": True', stripped, f'"approved": True found in {s}')
                self.assertNotIn("approved=True", stripped, f"approved=True found in {s}")


class TestSecurityNoEligibilityTrue(unittest.TestCase):
    """7. eligible_for_*=true não deve existir no código"""

    def test_no_eligibility_true任何形式(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("eligible_for_bootstrap = True", content, f"eligible_for_bootstrap=True in {s}")
            self.assertNotIn("eligible_for_backfill = True", content, f"eligible_for_backfill=True in {s}")
            self.assertNotIn("eligible_for_phase_0e3 = True", content, f"eligible_for_phase_0e3=True in {s}")


class TestSecurityNoForbiddenCommandsInCode(unittest.TestCase):
    """8. Comandos proibidos não devem aparecer"""

    def test_no_start_staging(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("start_staging", content, f"start_staging found in {s}")

    def test_no_run_production_readonly(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("run_production_readonly", content, f"run_production_readonly found in {s}")

    def test_no_bootstrap_command(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                lower = stripped.lower()
                self.assertNotIn("run_bootstrap", lower, f"run_bootstrap found in {s}")
                self.assertNotIn("execute_bootstrap", lower, f"execute_bootstrap found in {s}")
                self.assertNotIn("start_bootstrap", lower, f"start_bootstrap found in {s}")

    def test_no_migration_command(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("migration", content.lower(), f"migration found in {s}")

    def test_no_feature_flag(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("feature_flag", content.lower(), f"feature_flag found in {s}")

    def test_no_deploy(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("deploy", content.lower(), f"deploy found in {s}")


class TestSecurityCheckSecurityFunction(unittest.TestCase):
    """9. Função check_security deve existir em todos os scripts"""

    def test_check_security_exists(self):
        scripts_with_check = [
            "review_mappings.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "validate_private_package.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts_with_check:
            content = _read_script(s)
            self.assertIn("def check_security", content, f"check_security not found in {s}")


class TestSecuritySymlinkCheck(unittest.TestCase):
    """10. check_security deve rejeitar symlinks"""

    def test_symlink_check_in_all_scripts(self):
        scripts_with_check = [
            "review_mappings.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "validate_private_package.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts_with_check:
            content = _read_script(s)
            self.assertIn("os.path.islink", content, f"os.path.islink not in {s}")


class TestSecurityPathTraversalCheck(unittest.TestCase):
    """11. check_security deve validar path traversal"""

    def test_realpath_check_in_all_scripts(self):
        scripts_with_check = [
            "review_mappings.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "validate_private_package.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts_with_check:
            content = _read_script(s)
            self.assertIn("os.path.realpath", content, f"os.path.realpath not in {s}")


class TestSecurityAtomicWrite(unittest.TestCase):
    """12. Escritas devem ser atômicas"""

    def test_atomic_write_in_finalize(self):
        content = _read_script("finalize_review.py")
        self.assertIn("fsync", content, "fsync not found in finalize_review.py")
        self.assertIn("os.rename", content, "os.rename not found in finalize_review.py")

    def test_atomic_write_in_template(self):
        content = _read_script("generate_review_template.py")
        self.assertIn("fsync", content, "fsync not found in generate_review_template.py")
        self.assertIn("os.rename", content, "os.rename not found in generate_review_template.py")


class TestSecurityChmodApplied(unittest.TestCase):
    """13. chmod 600/700 deve ser aplicado"""

    def test_chmod_in_finalize(self):
        content = _read_script("finalize_review.py")
        self.assertIn("0o600", content, "chmod 600 not in finalize_review.py")

    def test_chmod_in_template(self):
        content = _read_script("generate_review_template.py")
        self.assertIn("0o600", content, "chmod 600 not in generate_review_template.py")
        self.assertIn("0o700", content, "chmod 700 not in generate_review_template.py")

    def test_chmod_in_sanitize(self):
        content = _read_script("sanitize_review_summary.py")
        self.assertIn("0o600", content, "chmod 600 not in sanitize_review_summary.py")


class TestSecurityNoPrivateDataInTerminal(unittest.TestCase):
    """14. Scripts não devem imprimir dados privados"""

    def test_no_print_of_private_fields(self):
        scripts_with_output = [
            "review_mappings.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "validate_private_package.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts_with_output:
            content = _read_script(s)
            self.assertNotIn("print(f\"name", content, f"print name found in {s}")
            self.assertNotIn("print(f\"email", content, f"print email found in {s}")
            self.assertNotIn("print(f\"phone", content, f"print phone found in {s}")
            self.assertNotIn("print(f\"address", content, f"print address found in {s}")
            self.assertNotIn("print(f\"document", content, f"print document found in {s}")


class TestSecurityReviewNotesSecrets(unittest.TestCase):
    """15. Review notes devem bloquear secrets"""

    def test_notes_validator_blocks_token(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("token exposto")
        self.assertFalse(ok)

    def test_notes_validator_blocks_password(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("password 123")
        self.assertFalse(ok)

    def test_notes_validator_blocks_cookie(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("cookie armazenado")
        self.assertFalse(ok)

    def test_notes_validator_blocks_html(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("texto <b>negrito</b>")
        self.assertFalse(ok)

    def test_notes_validator_blocks_url(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("ver https://exemplo.com")
        self.assertFalse(ok)

    def test_notes_validator_allows_normal_text(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("Revisão humana padrão sem dados sensíveis")
        self.assertTrue(ok)

    def test_notes_validator_blocks_at_sign(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("usuario@email.com")
        self.assertFalse(ok)

    def test_notes_validator_blocks_senha(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("senha do sistema")
        self.assertFalse(ok)


class TestSecurityNoPsql(unittest.TestCase):
    """16. psql não deve ser referenciado"""

    def test_no_psql(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("psql", content, f"psql found in {s}")


class TestSecurityWriteAtomicPattern(unittest.TestCase):
    """17. Padrão de escrita atômica deve seguir o protocolo"""

    def test_tmp_then_rename_pattern(self):
        content = _read_script("finalize_review.py")
        self.assertIn(".tmp", content, ".tmp pattern not in finalize_review.py")
        self.assertIn("fsync", content, "fsync not in finalize_review.py")
        self.assertIn("os.rename", content, "os.rename not in finalize_review.py")
        self.assertIn("os.chmod", content, "os.chmod not in finalize_review.py")


class TestSecurityAllScriptsStartWithShebang(unittest.TestCase):
    """18. Todos os scripts Python devem ter shebang"""

    def test_shebang_in_all_python_scripts(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertTrue(content.startswith("#!/usr/bin/env python3"), f"Shebang missing in {s}")


class TestSecurityNoPasswordInOutput(unittest.TestCase):
    """19. Nenhuma senha ou token deve ser impresso"""

    def test_no_password_in_any_script(self):
        for s in ALL_SCRIPTS:
            content = _read_script(s)
            self.assertNotIn("print.*password", content.lower(), f"password print found in {s}")
            self.assertNotIn("print.*token", content.lower(), f"token print found in {s}")


if __name__ == '__main__':
    unittest.main()
