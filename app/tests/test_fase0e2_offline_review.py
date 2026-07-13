import unittest
import os
import sys
import json
import csv
import shutil
import tempfile
import importlib

SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts", "fase0e2")


def _import_module(name):
    if name in sys.modules:
        return sys.modules[name]
    parts = name.split(".")
    mod = importlib.import_module(name)
    return mod


class TestFase0e2NoForbiddenImports(unittest.TestCase):
    """1. Ferramenta não importa app/main.py"""

    def test_validate_package_no_app_main(self):
        path = os.path.join(SCRIPT_DIR, "validate_private_package.py")
        with open(path, "r") as f:
            content = f.read()
        self.assertNotIn("app.main", content)
        self.assertNotIn("from app", content)
        self.assertNotIn("import app", content)

    def test_generate_template_no_app_main(self):
        path = os.path.join(SCRIPT_DIR, "generate_review_template.py")
        with open(path, "r") as f:
            content = f.read()
        self.assertNotIn("app.main", content)

    def test_validate_decisions_no_app_main(self):
        path = os.path.join(SCRIPT_DIR, "validate_human_decisions.py")
        with open(path, "r") as f:
            content = f.read()
        self.assertNotIn("app.main", content)

    def test_finalize_no_app_main(self):
        path = os.path.join(SCRIPT_DIR, "finalize_review.py")
        with open(path, "r") as f:
            content = f.read()
        self.assertNotIn("app.main", content)

    def test_review_mappings_no_app_main(self):
        path = os.path.join(SCRIPT_DIR, "review_mappings.py")
        with open(path, "r") as f:
            content = f.read()
        self.assertNotIn("app.main", content)

    def test_sanitize_no_app_main(self):
        path = os.path.join(SCRIPT_DIR, "sanitize_review_summary.py")
        with open(path, "r") as f:
            content = f.read()
        self.assertNotIn("app.main", content)


class TestFase0e2NoDbImports(unittest.TestCase):
    """2. Ferramenta não importa app/db.py"""

    def test_no_app_db_in_all_scripts(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("app.db", content, f"app.db found in {s}")
            self.assertNotIn("psycopg", content, f"psycopg found in {s}")
            self.assertNotIn("asyncpg", content, f"asyncpg found in {s}")
            self.assertNotIn("sqlalchemy", content, f"sqlalchemy found in {s}")


class TestFase0e2NoSocket(unittest.TestCase):
    """3. Ferramenta não abre socket"""

    def test_no_socket_in_all_scripts(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("socket.connect", content, f"socket.connect found in {s}")
            self.assertNotIn("socket.socket", content, f"socket.socket found in {s}")


class TestFase0e2NoHttp(unittest.TestCase):
    """4. Ferramenta não faz HTTP"""

    def test_no_http_in_all_scripts(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("requests.", content, f"requests found in {s}")
            self.assertNotIn("httpx", content, f"httpx found in {s}")
            self.assertNotIn("urllib.request", content, f"urllib.request found in {s}")


class TestFase0e2NoDocker(unittest.TestCase):
    """5. Ferramenta não executa Docker"""

    def test_no_docker_in_all_scripts(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("docker", content.lower(), f"docker found in {s}")


class TestFase0e2NoGit(unittest.TestCase):
    """6. Ferramenta não executa Git"""

    def test_no_git_in_all_scripts(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("git add", content, f"git add found in {s}")
            self.assertNotIn("git commit", content, f"git commit found in {s}")
            self.assertNotIn("git push", content, f"git push found in {s}")


class TestFase0e2NoSystemOrEval(unittest.TestCase):
    """7. Ferramenta não usa os.system, eval ou exec dinâmico"""

    def test_no_system_calls(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("os.system", content, f"os.system found in {s}")
            self.assertNotIn("subprocess.run", content, f"subprocess.run found in {s}")
            self.assertNotIn("subprocess.Popen", content, f"subprocess.Popen found in {s}")
            self.assertNotIn("eval(", content, f"eval( found in {s}")
            self.assertNotIn("exec(", content, f"exec( found in {s}")


class TestFase0e2SourcePackageReadOnly(unittest.TestCase):
    """8. Pacote de origem é somente leitura"""

    def test_source_permissions_are_readonly(self):
        source_dir = "/root/.config/wins_agro/fase0e1/20260713_165551_production"
        if not os.path.isdir(source_dir):
            self.skipTest("Source package not available")
        st = os.stat(source_dir)
        mode = st.st_mode & 0o777
        self.assertEqual(mode, 0o700)

    def test_source_files_are_600(self):
        source_dir = "/root/.config/wins_agro/fase0e1/20260713_165551_production"
        if not os.path.isdir(source_dir):
            self.skipTest("Source package not available")
        for fname in os.listdir(source_dir):
            fpath = os.path.join(source_dir, fname)
            if os.path.isfile(fpath):
                st = os.stat(fpath)
                mode = st.st_mode & 0o777
                self.assertEqual(mode, 0o600, f"File {fname} has wrong permissions: {oct(mode)}")


class TestFase0e2SupersededRejection(unittest.TestCase):
    """9. Execução superseded é rejeitada"""

    def test_superseded_rejected(self):
        sys_argv = sys.argv
        try:
            from scripts.fase0e2.validate_private_package import main as val_main
            for sup in ["20260713_164030_production", "20260713_164036_production", "20260713_164049_production"]:
                sys.argv = ["validate_private_package.py", "--source", f"/root/.config/wins_agro/fase0e1/{sup}"]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 4, f"Superseded {sup} should exit with code 4")
        finally:
            sys.argv = sys_argv


class TestFase0e2ChecksumValidation(unittest.TestCase):
    """10. Checksum inválido é rejeitado"""

    def test_invalid_checksum_rejected(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "fake_source")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)

            manifest = {"timestamp": "20260713_165551", "is_production": True, "files": {}}
            with open(os.path.join(source_dir, "execution_manifest_private.json"), "w") as f:
                json.dump(manifest, f)
            os.chmod(os.path.join(source_dir, "execution_manifest_private.json"), 0o600)

            proposals = [{"proposal_id": f"p_{i}", "approved": False, "confidence_class": "F"} for i in range(5)]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)
            os.chmod(os.path.join(source_dir, "mapping_proposals_private.json"), 0o600)

            with open(os.path.join(source_dir, "checksums.sha256"), "w") as f:
                f.write("0000000000000000000000000000000000000000000000000000000000000000  execution_manifest_private.json\n")
                f.write("0000000000000000000000000000000000000000000000000000000000000000  mapping_proposals_private.json\n")
                f.write("0000000000000000000000000000000000000000000000000000000000000000  mapping_review_checklist_private.csv\n")
            os.chmod(os.path.join(source_dir, "checksums.sha256"), 0o600)

            checklist_path = os.path.join(source_dir, "mapping_review_checklist_private.csv")
            with open(checklist_path, "w") as f:
                f.write("proposal_id,display_user,display_client\n")
            os.chmod(checklist_path, 0o600)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_private_package import main as val_main
                sys.argv = ["validate_private_package.py", "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertNotEqual(cm.exception.code, 0)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestFase0e2MissingFileRejection(unittest.TestCase):
    """11. Arquivo ausente é rejeitado"""

    def test_missing_manifest_rejected(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "fake_source")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)

            with open(os.path.join(source_dir, "checksums.sha256"), "w") as f:
                f.write("")
            os.chmod(os.path.join(source_dir, "checksums.sha256"), 0o600)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_private_package import main as val_main
                sys.argv = ["validate_private_package.py", "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    try:
                        val_main()
                    except FileNotFoundError:
                        raise SystemExit(1)
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestFase0e2SymlinkRejection(unittest.TestCase):
    """12. Symlink é rejeitado"""

    def test_symlink_source_dir_rejected(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            real_dir = os.path.join(tmp_dir, "real")
            os.makedirs(real_dir, mode=0o700)
            link_path = os.path.join(tmp_dir, "link")
            os.symlink(real_dir, link_path)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_private_package import main as val_main
                sys.argv = ["validate_private_package.py", "--source", link_path]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 2)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestFase0e2PathTraversalRejection(unittest.TestCase):
    """13. Path traversal é rejeitado"""

    def test_path_traversal_rejected(self):
        sys_argv = sys.argv
        try:
            from scripts.fase0e2.validate_private_package import main as val_main
            sys.argv = ["validate_private_package.py", "--source", "/etc/passwd/../../etc"]
            with self.assertRaises(SystemExit) as cm:
                val_main()
            self.assertIn(cm.exception.code, [1, 2])
        finally:
            sys.argv = sys_argv


class TestFase0e2PermissionRejection(unittest.TestCase):
    """14. Permissões diferentes de 700/600 são rejeitadas"""

    def test_wrong_dir_permissions(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "bad_perms")
            os.makedirs(source_dir, mode=0o777, exist_ok=True)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_private_package import main as val_main
                sys.argv = ["validate_private_package.py", "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 3)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestFase0e2ProposalCountValidation(unittest.TestCase):
    """15. Quantidade diferente de cinco propostas é sinalizada"""

    def test_wrong_proposal_count(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "bad_count")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)

            manifest = {"timestamp": "20260713_165551", "is_production": True, "files": {}}
            with open(os.path.join(source_dir, "execution_manifest_private.json"), "w") as f:
                json.dump(manifest, f)
            os.chmod(os.path.join(source_dir, "execution_manifest_private.json"), 0o600)

            proposals = [{"proposal_id": "p_1", "approved": False, "confidence_class": "F"}]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)
            os.chmod(os.path.join(source_dir, "mapping_proposals_private.json"), 0o600)

            with open(os.path.join(source_dir, "checksums.sha256"), "w") as f:
                f.write("")
            os.chmod(os.path.join(source_dir, "checksums.sha256"), 0o600)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_private_package import main as val_main
                sys.argv = ["validate_private_package.py", "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestFase0e2ApprovedTrueRejection(unittest.TestCase):
    """16. approved=true na origem é rejeitado"""

    def test_approved_true_rejected(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "approved_true")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)

            manifest = {"timestamp": "20260713_165551", "is_production": True, "files": {}}
            with open(os.path.join(source_dir, "execution_manifest_private.json"), "w") as f:
                json.dump(manifest, f)
            os.chmod(os.path.join(source_dir, "execution_manifest_private.json"), 0o600)

            proposals = [
                {"proposal_id": f"p_{i}", "approved": True if i == 0 else False, "confidence_class": "F"}
                for i in range(5)
            ]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)
            os.chmod(os.path.join(source_dir, "mapping_proposals_private.json"), 0o600)

            with open(os.path.join(source_dir, "checksums.sha256"), "w") as f:
                f.write("")
            os.chmod(os.path.join(source_dir, "checksums.sha256"), 0o600)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_private_package import main as val_main
                sys.argv = ["validate_private_package.py", "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestFase0e2WrongClassRejection(unittest.TestCase):
    """17. Classe diferente de F é sinalizada"""

    def test_wrong_class_rejected(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "wrong_class")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)

            manifest = {"timestamp": "20260713_165551", "is_production": True, "files": {}}
            with open(os.path.join(source_dir, "execution_manifest_private.json"), "w") as f:
                json.dump(manifest, f)
            os.chmod(os.path.join(source_dir, "execution_manifest_private.json"), 0o600)

            proposals = [
                {"proposal_id": f"p_{i}", "approved": False, "confidence_class": "B" if i == 0 else "F"}
                for i in range(5)
            ]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)
            os.chmod(os.path.join(source_dir, "mapping_proposals_private.json"), 0o600)

            with open(os.path.join(source_dir, "checksums.sha256"), "w") as f:
                f.write("")
            os.chmod(os.path.join(source_dir, "checksums.sha256"), 0o600)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_private_package import main as val_main
                sys.argv = ["validate_private_package.py", "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestFase0e2NoStaging(unittest.TestCase):
    """18. Nenhum staging é iniciado"""

    def test_no_staging_references(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("start_staging", content, f"start_staging found in {s}")
            self.assertNotIn("run_production_readonly", content, f"run_production_readonly found in {s}")
            self.assertNotIn("run_staging_rehearsal", content, f"run_staging_rehearsal found in {s}")


class TestFase0e2NoBootstrap(unittest.TestCase):
    """19. Nenhum bootstrap é executado"""

    def test_no_bootstrap_references(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                lines = f.readlines()
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                lower = stripped.lower()
                self.assertNotIn("run_bootstrap", lower, f"run_bootstrap found in {s}")
                self.assertNotIn("execute_bootstrap", lower, f"execute_bootstrap found in {s}")
                self.assertNotIn("start_bootstrap", lower, f"start_bootstrap found in {s}")


class TestFase0e2NoMigration(unittest.TestCase):
    """20. Nenhuma migration é executada"""

    def test_no_migration_references(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("migration", content.lower(), f"migration found in {s}")
            self.assertNotIn("alembic", content.lower(), f"alembic found in {s}")


class TestFase0e2NoFeatureFlag(unittest.TestCase):
    """21. Nenhuma feature flag é alterada"""

    def test_no_feature_flag_references(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("feature_flag", content.lower(), f"feature_flag found in {s}")
            self.assertNotIn("enable_feature", content.lower(), f"enable_feature found in {s}")


class TestFase0e2NoDeploy(unittest.TestCase):
    """22. Nenhum deploy é executado"""

    def test_no_deploy_references(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("deploy", content.lower(), f"deploy found in {s}")


class TestFase0e2NoApprovedTrueInCode(unittest.TestCase):
    """23. Nenhum approved=true no código"""

    def test_no_approved_true(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                lines = f.readlines()
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                self.assertNotIn("approved = True", stripped, f"approved = True found in {s}")
                self.assertNotIn('"approved": True', stripped, f'"approved": True found in {s}')
                self.assertNotIn("approved=True", stripped, f"approved=True found in {s}")


class TestFase0e2NoEligibilityTrueInCode(unittest.TestCase):
    """24. Nenhuma elegibilidade vira true no código"""

    def test_no_eligibility_true(self):
        scripts = [
            "validate_private_package.py",
            "generate_review_template.py",
            "validate_human_decisions.py",
            "finalize_review.py",
            "review_mappings.py",
            "sanitize_review_summary.py",
        ]
        for s in scripts:
            path = os.path.join(SCRIPT_DIR, s)
            with open(path, "r") as f:
                content = f.read()
            self.assertNotIn("eligible_for_bootstrap = True", content, f"eligible_for_bootstrap=True in {s}")
            self.assertNotIn("eligible_for_backfill = True", content, f"eligible_for_backfill=True in {s}")
            self.assertNotIn("eligible_for_phase_0e3 = True", content, f"eligible_for_phase_0e3=True in {s}")
            self.assertNotIn('"eligible_for_bootstrap": true', content.lower(), f"eligible_for_bootstrap:true in {s}")
            self.assertNotIn('"eligible_for_backfill": true', content.lower(), f"eligible_for_backfill:true in {s}")
            self.assertNotIn('"eligible_for_phase_0e3": true', content.lower(), f"eligible_for_phase_0e3:true in {s}")


if __name__ == '__main__':
    unittest.main()
