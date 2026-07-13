import unittest
import os
import sys

class MappingProposalsTest(unittest.TestCase):
    def test_proposals_start_not_approved(self):
        """1. Todas as propostas devem começar como approved = False"""
        filepath = "/root/wins_agro_v1/scripts/fase0e1/inventory_readonly.py"
        with open(filepath, 'r') as f:
            content = f.read()
        self.assertIn('"approved": False', content)
        self.assertIn('"reviewer": None', content)
        self.assertIn('"reviewed_at": None', content)

    def test_no_privileged_roles_inferred(self):
        """2. Papéis privilegiados como owner ou admin não devem ser assumidos na proposta remediada"""
        filepath = "/root/wins_agro_v1/scripts/fase0e1/inventory_readonly.py"
        with open(filepath, 'r') as f:
            content = f.read()

        # Garante que propõe pending_review por padrão para todos os casos
        self.assertIn('proposed_role = "pending_review"', content)
        # E que não existe atribuição direta ou implícita de owner/admin
        self.assertNotIn('proposed_role = "owner"', content)
        self.assertNotIn('proposed_role = "admin"', content)

if __name__ == '__main__':
    unittest.main()
