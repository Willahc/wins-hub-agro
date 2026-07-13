import unittest
import os
import sys

# Insere scripts/fase0e1 no path para poder importar se necessário,
# mas vamos focar em testar as regras estáticas e comportamentos
sys.path.insert(0, '/root/wins_agro_v1/scripts/fase0e1')

class InventoryFase0e1Test(unittest.TestCase):
    def test_tool_does_not_import_main(self):
        """1. A ferramenta não deve importar app/main.py"""
        filepath = "/root/wins_agro_v1/scripts/fase0e1/inventory_readonly.py"
        with open(filepath, 'r') as f:
            content = f.read()
        self.assertNotIn("import main", content)
        self.assertNotIn("from main import", content)
        self.assertNotIn("app.main", content)

    def test_default_dry_run_and_confirm_production(self):
        """2. Produção exige confirmação explícita"""
        filepath = "/root/wins_agro_v1/scripts/fase0e1/inventory_readonly.py"
        with open(filepath, 'r') as f:
            content = f.read()
        self.assertIn("confirm_production_readonly", content)

    def test_transaction_is_readonly_and_rollback(self):
        """3. Transação deve ser READ ONLY e usar ROLLBACK no final"""
        filepath = "/root/wins_agro_v1/scripts/fase0e1/inventory_readonly.py"
        with open(filepath, 'r') as f:
            content = f.read()
        self.assertIn("BEGIN READ ONLY;", content)
        self.assertIn("SET LOCAL transaction_read_only = on;", content)
        self.assertIn("conn.rollback()", content)
        self.assertNotIn("conn.commit()", content)

if __name__ == '__main__':
    unittest.main()
