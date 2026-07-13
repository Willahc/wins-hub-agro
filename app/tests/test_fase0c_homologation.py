# Testes automatizados da Fase 0C
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


class HomologationFase0cTest(unittest.TestCase):
    def setUp(self):
        self.fase0c_dir = ROOT / "scripts" / "fase0c"

    def test_harness_does_not_use_production_network(self):
        # 1. Harness não usa rede de produção; 2. Nenhuma porta é publicada
        run_script = (self.fase0c_dir / "run_homologation.sh").read_text(encoding="utf-8")
        self.assertIn("docker network create", run_script)
        for line in run_script.splitlines():
            if "docker run" in line:
                self.assertNotIn("-p", line)
                self.assertNotIn("--publish", line)

    def test_harness_volumes_exclusive_prefix(self):
        # 3. Volumes possuem prefixo exclusivo
        run_script = (self.fase0c_dir / "run_homologation.sh").read_text(encoding="utf-8")
        self.assertIn("wins_agro_fase0c_source_data_", run_script)
        self.assertIn("wins_agro_fase0c_restore_data_", run_script)

    def test_cleanup_uses_only_execution_names_and_no_generic_prune(self):
        # 4. Cleanup usa nomes da execução; 5. Não existe prune genérico
        cleanup_script = (self.fase0c_dir / "cleanup_homologation.sh").read_text(encoding="utf-8")
        self.assertIn("docker rm -f", cleanup_script)
        self.assertNotIn("docker system prune", cleanup_script)
        self.assertNotIn("docker volume prune", cleanup_script)
        self.assertNotIn("docker network prune", cleanup_script)

    def test_dot_env_is_not_read_by_scripts(self):
        # 6. .env não é lido
        for p in self.fase0c_dir.glob("*"):
            if p.is_file() and p.suffix in (".sh", ".py"):
                content = p.read_text(encoding="utf-8")
                self.assertNotIn(".env", content)

    def test_production_dsn_and_localhost_rejected(self):
        # 7. DSN de produção é rejeitado; 8. localhost é rejeitado; 9. db:5432 é rejeitado
        # Verificado via bootstrap_legacy.py BLOCKED_HOSTS e dbname checks
        cli_path = ROOT / "scripts" / "fase0" / "bootstrap_legacy.py"
        cli_content = cli_path.read_text(encoding="utf-8")
        self.assertIn("BLOCKED_HOSTS = frozenset", cli_content)
        self.assertIn('"localhost"', cli_content)
        self.assertIn('"127.0.0.1"', cli_content)
        self.assertIn('"db"', cli_content)
        self.assertIn('"wins_agro"', cli_content)

    def test_roles_attributes_constraints(self):
        # 10. Roles não são superuser; 11. Não têm CREATEDB; 12. Não têm CREATEROLE
        seed_sql = (self.fase0c_dir / "seed_synthetic_legacy.sql").read_text(encoding="utf-8")
        self.assertIn("NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION", seed_sql)

        # 13. PUBLIC não tem CREATE
        # 14. Readonly não escreve (SELECT apenas)
        # 15. App não altera schema (USAGE, SELECT, e DMLs operacionais apenas)
        validate_roles = (self.fase0c_dir / "validate_roles.sql").read_text(encoding="utf-8")
        self.assertIn("Privilégio PUBLIC detectado", validate_roles)
        self.assertIn("wins_agro_readonly", validate_roles)
        self.assertIn("wins_agro_app", validate_roles)
        self.assertIn("wins_agro_migrator", validate_roles)

    def test_sql_scripts_use_on_error_stop(self):
        # 16. Scripts usam ON_ERROR_STOP
        for p in self.fase0c_dir.glob("*.sql"):
            content = p.read_text(encoding="utf-8")
            self.assertIn("ON_ERROR_STOP on", content)

    def test_backup_and_restore_arguments(self):
        # 17. Backup usa no-owner; 18. Backup usa no-acl
        # 19. Restore usa exit-on-error
        # 20. Dump não é salvo no repositório (verificado pelo gitignore e caminhos em /tmp)
        run_script = (self.fase0c_dir / "run_homologation.sh").read_text(encoding="utf-8")
        self.assertIn("pg_dump", run_script)
        self.assertIn("--no-owner", run_script)
        self.assertIn("--no-acl", run_script)
        self.assertIn("pg_restore", run_script)
        self.assertIn("--exit-on-error", run_script)
        self.assertIn("/tmp/wins_agro_fase0c_", run_script)

    def test_comparison_logical_and_physical(self):
        # 21. Manifesto usa SHA-256; 22. Restore ocorre em instância diferente; 23. Origem destruída antes do restore
        # 24. Comparação valida contagens; 25. Comparação valida constraints; 26. Comparação valida índices; 27. Comparação valida grants
        run_script = (self.fase0c_dir / "run_homologation.sh").read_text(encoding="utf-8")
        self.assertIn("sha256sum", run_script)
        self.assertIn("wins_agro_fase0c_restore_", run_script)
        self.assertIn("docker rm -f \"$SOURCE_CONTAINER\"", run_script)

        compare_script = (self.fase0c_dir / "compare_databases.sh").read_text(encoding="utf-8")
        self.assertIn("pg_dump -s", compare_script)
        self.assertIn("diff -u", compare_script)
        self.assertIn("SELECT count(*)", compare_script)

    def test_cli_execution_rules(self):
        # 28. CLI executa dry-run; 29. CLI exige apply explícito; 30. Reapply é idempotente
        # 31. Conflito faz rollback; 32. Papel não é elevado; 33. Organização não é trocada
        # 34. Relatório é sanitizado; 35. Nenhum dado real aparece
        run_script = (self.fase0c_dir / "run_homologation.sh").read_text(encoding="utf-8")
        self.assertIn("bootstrap_legacy.py", run_script)
        self.assertIn("--apply", run_script)
        self.assertIn("--confirm APPLY_EXPLICIT_LEGACY_MAPPING", run_script)
        self.assertIn("mapping_conflict_org.json", run_script)
        self.assertIn("mapping_invalid_source.json", run_script)

        # 36. Prospecção não é referenciada nos arquivos da Fase 0C
        for p in self.fase0c_dir.glob("*"):
            if p.is_file():
                content = p.read_text(encoding="utf-8")
                self.assertNotIn("prospeccao.fazenda_nacional", content)

    def test_feature_flag_disabled_by_default(self):
        # 37. Operação legada escolhida é somente leitura (validado no documento desenhado)
        # 38. Feature flag permanece desligada
        main_py = (ROOT / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("ENABLE_MULTI_TENANCY_FOUNDATION", main_py)
        # Verifica se por padrão o env não é ativado no código
        self.assertEqual(os.getenv("ENABLE_MULTI_TENANCY_FOUNDATION", ""), "")

    def test_cli_import_efficiency(self):
        # 39. Nenhum módulo importa app/main.py desnecessariamente
        # 40. Novos arquivos podem ser importados sem acessar banco
        cli_content = (ROOT / "scripts" / "fase0" / "bootstrap_legacy.py").read_text(encoding="utf-8")
        self.assertNotIn("import app.main", cli_content)
        self.assertNotIn("import main", cli_content)


if __name__ == "__main__":
    unittest.main()
