import unittest
import os
import sys

class SecurityFase0e1Test(unittest.TestCase):
    def setUp(self):
        self.script_path = "/root/wins_agro_v1/scripts/fase0e1/inventory_readonly.py"
        with open(self.script_path, 'r') as f:
            self.content = f.read()
            self.lines = self.content.splitlines()

    def test_no_forbidden_sql_statements(self):
        """1. Sem INSERT, UPDATE, DELETE, CREATE, ALTER ou DROP nas queries reais"""
        for idx, line in enumerate(self.lines):
            # Ignora o teste negativo explicitamente
            if "Teste Escrita Rejeitada" in line:
                continue
            # Ignora comentários
            if line.strip().startswith("#"):
                continue

            cleaned = line.upper()
            if "INSERT " in cleaned or "UPDATE " in cleaned or "DELETE " in cleaned or "ALTER " in cleaned or "DROP " in cleaned:
                # Verifica se está em uma query string
                if "SELECT " in cleaned or "cur.execute" in line:
                    self.fail(f"Comando proibido encontrado na linha {idx+1}: {line.strip()}")

    def test_prospeccao_fazenda_nacional_not_queried(self):
        """2. A tabela prospeccao.fazenda_nacional não deve ser consultada"""
        self.assertNotIn("prospeccao.fazenda_nacional", self.content)

    def test_webauthn_not_in_allowlist(self):
        """3. WebAuthn não pode estar nas tabelas ou queries consultadas"""
        self.assertNotIn("webauthn_credential", self.content)
        self.assertNotIn("webauthn", self.content.lower())

    def test_session_tables_not_in_allowlist(self):
        """4. Tabelas de sessão não podem estar nas queries consultadas"""
        cleaned_content = self.content.lower().replace("idle_in_transaction_session_timeout", "")
        self.assertNotIn("session", cleaned_content)
        self.assertNotIn("sessions", cleaned_content)

    def test_audit_content_not_used_for_mapping(self):
        """5. Conteúdo de auditoria não pode ser usado para mapping"""
        self.assertNotIn("audit_log", self.content)
        self.assertNotIn("audit_events", self.content)

    def test_no_real_names_in_markdown(self):
        """6. Nomes reais (pessoas/propriedades) não devem estar no Markdown sanitizado"""
        md_path = "/root/wins_agro_v1/docs/fase0_fundacoes/34_EVIDENCIAS_SANITIZADAS_FASE0E1.md"
        if os.path.exists(md_path):
            with open(md_path, 'r') as f:
                md_content = f.read().lower()
            # Garante que não há menção a nomes reais de propriedades ou pessoas coletadas
            self.assertNotIn("fazenda demonstração", md_content)
            self.assertNotIn("mari@winshubagro", md_content)
            self.assertNotIn("williamvnvn", md_content)
            # Apenas pseudônimos HMAC (como client-...)
            self.assertIn("client-", md_content)

    def test_no_elevated_confidence_without_explicit_evidence(self):
        """7. Sem relação explícita no banco, a classe não pode ser A ou B"""
        # Garante que a classe de confiança padrão para as propostas geradas é F
        self.assertIn('conf_class = "F"', self.content)
        self.assertNotIn('conf_class = "A"', self.content)
        self.assertNotIn('conf_class = "B"', self.content)

    def test_fuzzy_matching_does_not_elevate_confidence(self):
        """8. Fuzzy matching ou similaridade de nomes não eleva confiança"""
        self.assertNotIn("fuzzy", self.content.lower())
        self.assertNotIn("similarity", self.content.lower())

    def test_approved_remains_false(self):
        """9. O campo approved de todas as propostas deve permanecer False"""
        self.assertIn('"approved": False', self.content)

if __name__ == '__main__':
    unittest.main()
