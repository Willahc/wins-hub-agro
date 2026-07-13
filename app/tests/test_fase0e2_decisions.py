import unittest
import os
import sys
import json
import csv
import shutil
import tempfile

SCRIPT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "scripts", "fase0e2")


class TestDecisionsAllowedEnum(unittest.TestCase):
    """1. APPROVE é rejeitado"""

    def test_approve_not_in_allowed(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        self.assertNotIn("APPROVE", ALLOWED_REASONS)


class TestDecisionsAcceptRejected(unittest.TestCase):
    """2. ACCEPT é rejeitado"""

    def test_accept_not_in_allowed(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        self.assertNotIn("ACCEPT", ALLOWED_REASONS)


class TestDecisionsApplyRejected(unittest.TestCase):
    """3. APPLY é rejeitado"""

    def test_apply_not_in_allowed(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        self.assertNotIn("APPLY", ALLOWED_REASONS)


class TestDecisionsUnknownRejected(unittest.TestCase):
    """4. Decisão desconhecida é rejeitada"""

    def test_unknown_decision_rejected(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        self.assertNotIn("UNKNOWN_DECISION", ALLOWED_REASONS)
        self.assertNotIn("MIGRATE", ALLOWED_REASONS)
        self.assertNotIn("BACKFILL", ALLOWED_REASONS)
        self.assertNotIn("ENABLE", ALLOWED_REASONS)
        self.assertNotIn("DEPLOY", ALLOWED_REASONS)
        self.assertNotIn("OWNER_CONFIRMED", ALLOWED_REASONS)
        self.assertNotIn("ADMIN_CONFIRMED", ALLOWED_REASONS)


class TestDecisionsReasonCodeCompatibility(unittest.TestCase):
    """5. Reason code incompatível é rejeitado"""

    def test_reject_reasons_only_for_reject(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        reject_only = {
            "NO_EXPLICIT_RELATION", "INSUFFICIENT_EVIDENCE", "AMBIGUOUS_IDENTITY",
            "AMBIGUOUS_OPERATIONAL_SCOPE", "INACTIVE_OR_OBSOLETE_RECORD",
            "DUPLICATE_OR_CONFLICTING_RECORD", "NOT_A_VALID_OPERATIONAL_USER",
            "NOT_A_VALID_OPERATIONAL_CLIENT"
        }
        self.assertEqual(ALLOWED_REASONS["REJECT"], reject_only)

    def test_pending_reasons_only_for_pending(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        pending_only = {
            "WAITING_HUMAN_CONTEXT", "WAITING_BUSINESS_VALIDATION",
            "WAITING_ROLE_CONFIRMATION", "WAITING_FARM_CONFIRMATION",
            "INSUFFICIENT_INFORMATION", "CONFLICT_REQUIRES_REVIEW"
        }
        self.assertEqual(ALLOWED_REASONS["PENDING"], pending_only)

    def test_evidence_reasons_only_for_request(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        evidence_only = {
            "REQUIRE_ACCOUNT_OWNER_CONFIRMATION", "REQUIRE_EMPLOYMENT_CONFIRMATION",
            "REQUIRE_CLIENT_RELATION_CONFIRMATION", "REQUIRE_ROLE_CONFIRMATION",
            "REQUIRE_FARM_ACCESS_CONFIRMATION", "REQUIRE_OPERATIONAL_RESPONSIBILITY_CONFIRMATION"
        }
        self.assertEqual(ALLOWED_REASONS["REQUEST_OPERATIONAL_EVIDENCE"], evidence_only)

    def test_manual_reasons_only_for_manual(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        manual_only = {
            "LEGACY_MAPPING_NOT_SAFE", "MANUAL_ONBOARDING_PREFERRED",
            "NEW_IDENTITY_REQUIRED", "NEW_ORGANIZATION_REQUIRED",
            "NEW_MEMBERSHIP_REQUIRED", "NEW_FARM_ACCESS_REQUIRED",
            "LEGACY_DATA_NOT_AUTHORITATIVE"
        }
        self.assertEqual(ALLOWED_REASONS["MANUAL_REGISTRATION_FUTURE"], manual_only)

    def test_reject_reason_not_in_pending(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        self.assertNotIn("NO_EXPLICIT_RELATION", ALLOWED_REASONS["PENDING"])

    def test_pending_reason_not_in_reject(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        self.assertNotIn("WAITING_HUMAN_CONTEXT", ALLOWED_REASONS["REJECT"])


class TestDecisionsReviewerNotEmpty(unittest.TestCase):
    """6. Reviewer vazio é rejeitado"""

    def test_empty_reviewer_rejected(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "source")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)
            proposals = [{"proposal_id": f"p_{i}", "approved": False, "confidence_class": "F"} for i in range(5)]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)

            decisions_path = os.path.join(tmp_dir, "decisions.csv")
            fieldnames = ["proposal_id", "proposal_reference", "current_confidence_class", "decision",
                          "reason_codes", "required_evidence", "reviewer", "reviewed_at", "review_notes",
                          "next_action", "human_confirmation"]
            rows = []
            for i in range(5):
                rows.append({
                    "proposal_id": f"p_{i}",
                    "proposal_reference": "ref",
                    "current_confidence_class": "F",
                    "decision": "REJECT",
                    "reason_codes": "NO_EXPLICIT_RELATION",
                    "required_evidence": "",
                    "reviewer": "",
                    "reviewed_at": "2026-07-13T17:00:00Z",
                    "review_notes": "",
                    "next_action": "",
                    "human_confirmation": "I_REVIEWED_THIS_PROPOSAL"
                })
            with open(decisions_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_human_decisions import main as val_main
                sys.argv = ["validate_human_decisions.py", "--decisions", decisions_path, "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestDecisionsTimestampWithTimezone(unittest.TestCase):
    """7. Timestamp sem timezone é rejeitado"""

    def test_timestamp_without_timezone(self):
        from scripts.fase0e2.validate_human_decisions import validate_iso_timestamp
        ok, _ = validate_iso_timestamp("2026-07-13T17:00:00")
        self.assertFalse(ok)

    def test_timestamp_with_timezone_ok(self):
        from scripts.fase0e2.validate_human_decisions import validate_iso_timestamp
        ok, _ = validate_iso_timestamp("2026-07-13T17:00:00Z")
        self.assertTrue(ok)

    def test_timestamp_with_offset_ok(self):
        from scripts.fase0e2.validate_human_decisions import validate_iso_timestamp
        ok, _ = validate_iso_timestamp("2026-07-13T10:00:00-03:00")
        self.assertTrue(ok)


class TestDecisionsFutureTimestampRejection(unittest.TestCase):
    """8. Timestamp futuro inválido é rejeitado"""

    def test_far_future_rejected(self):
        from scripts.fase0e2.validate_human_decisions import validate_iso_timestamp
        ok, _ = validate_iso_timestamp("2099-01-01T00:00:00Z")
        self.assertFalse(ok)

    def test_slightly_future_rejected(self):
        from scripts.fase0e2.validate_human_decisions import validate_iso_timestamp
        ok, _ = validate_iso_timestamp("2099-12-31T23:59:59Z")
        self.assertFalse(ok)


class TestDecisionsConfirmationRequired(unittest.TestCase):
    """9. Confirmação incorreta é rejeitada"""

    def test_wrong_confirmation_rejected(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "source")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)
            proposals = [{"proposal_id": f"p_{i}", "approved": False, "confidence_class": "F"} for i in range(5)]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)

            decisions_path = os.path.join(tmp_dir, "decisions.csv")
            fieldnames = ["proposal_id", "proposal_reference", "current_confidence_class", "decision",
                          "reason_codes", "required_evidence", "reviewer", "reviewed_at", "review_notes",
                          "next_action", "human_confirmation"]
            rows = []
            for i in range(5):
                rows.append({
                    "proposal_id": f"p_{i}",
                    "proposal_reference": "ref",
                    "current_confidence_class": "F",
                    "decision": "REJECT",
                    "reason_codes": "NO_EXPLICIT_RELATION",
                    "required_evidence": "",
                    "reviewer": "test_reviewer",
                    "reviewed_at": "2026-07-13T17:00:00Z",
                    "review_notes": "",
                    "next_action": "",
                    "human_confirmation": "WRONG_CONFIRMATION"
                })
            with open(decisions_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_human_decisions import main as val_main
                sys.argv = ["validate_human_decisions.py", "--decisions", decisions_path, "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestDecisionsUnknownProposalId(unittest.TestCase):
    """10. proposal_id desconhecido é rejeitado"""

    def test_unknown_proposal_id_rejected(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "source")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)
            proposals = [{"proposal_id": f"p_{i}", "approved": False, "confidence_class": "F"} for i in range(5)]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)

            decisions_path = os.path.join(tmp_dir, "decisions.csv")
            fieldnames = ["proposal_id", "proposal_reference", "current_confidence_class", "decision",
                          "reason_codes", "required_evidence", "reviewer", "reviewed_at", "review_notes",
                          "next_action", "human_confirmation"]
            rows = []
            for i in range(5):
                rows.append({
                    "proposal_id": f"UNKNOWN_{i}",
                    "proposal_reference": "ref",
                    "current_confidence_class": "F",
                    "decision": "REJECT",
                    "reason_codes": "NO_EXPLICIT_RELATION",
                    "required_evidence": "",
                    "reviewer": "test_reviewer",
                    "reviewed_at": "2026-07-13T17:00:00Z",
                    "review_notes": "",
                    "next_action": "",
                    "human_confirmation": "I_REVIEWED_THIS_PROPOSAL"
                })
            with open(decisions_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_human_decisions import main as val_main
                sys.argv = ["validate_human_decisions.py", "--decisions", decisions_path, "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestDecisionsDuplicateProposalId(unittest.TestCase):
    """11. Proposta duplicada é rejeitada"""

    def test_duplicate_proposal_id_rejected(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "source")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)
            proposals = [{"proposal_id": f"p_{i}", "approved": False, "confidence_class": "F"} for i in range(5)]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)

            decisions_path = os.path.join(tmp_dir, "decisions.csv")
            fieldnames = ["proposal_id", "proposal_reference", "current_confidence_class", "decision",
                          "reason_codes", "required_evidence", "reviewer", "reviewed_at", "review_notes",
                          "next_action", "human_confirmation"]
            rows = []
            for i in range(5):
                rows.append({
                    "proposal_id": "p_0",
                    "proposal_reference": "ref",
                    "current_confidence_class": "F",
                    "decision": "REJECT",
                    "reason_codes": "NO_EXPLICIT_RELATION",
                    "required_evidence": "",
                    "reviewer": "test_reviewer",
                    "reviewed_at": "2026-07-13T17:00:00Z",
                    "review_notes": "",
                    "next_action": "",
                    "human_confirmation": "I_REVIEWED_THIS_PROPOSAL"
                })
            with open(decisions_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_human_decisions import main as val_main
                sys.argv = ["validate_human_decisions.py", "--decisions", decisions_path, "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestDecisionsMissingProposalReported(unittest.TestCase):
    """12. Ausência de proposta é reportada"""

    def test_missing_proposals_rejected(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "source")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)
            proposals = [{"proposal_id": f"p_{i}", "approved": False, "confidence_class": "F"} for i in range(5)]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)

            decisions_path = os.path.join(tmp_dir, "decisions.csv")
            fieldnames = ["proposal_id", "proposal_reference", "current_confidence_class", "decision",
                          "reason_codes", "required_evidence", "reviewer", "reviewed_at", "review_notes",
                          "next_action", "human_confirmation"]
            rows = []
            for i in range(3):
                rows.append({
                    "proposal_id": f"p_{i}",
                    "proposal_reference": "ref",
                    "current_confidence_class": "F",
                    "decision": "REJECT",
                    "reason_codes": "NO_EXPLICIT_RELATION",
                    "required_evidence": "",
                    "reviewer": "test_reviewer",
                    "reviewed_at": "2026-07-13T17:00:00Z",
                    "review_notes": "",
                    "next_action": "",
                    "human_confirmation": "I_REVIEWED_THIS_PROPOSAL"
                })
            with open(decisions_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_human_decisions import main as val_main
                sys.argv = ["validate_human_decisions.py", "--decisions", decisions_path, "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestDecisionsPartialReviewAllowed(unittest.TestCase):
    """13. Revisão parcial é permitida"""

    def test_partial_review_no_crash(self):
        from scripts.fase0e2.validate_human_decisions import validate_iso_timestamp, validate_notes
        ts_ok, _ = validate_iso_timestamp("2026-07-13T17:00:00Z")
        self.assertTrue(ts_ok)
        notes_ok, _ = validate_notes("Partial review context")
        self.assertTrue(notes_ok)


class TestDecisionsNoClassChange(unittest.TestCase):
    """14. Decisão não altera confidence_class"""

    def test_class_not_changed_by_decision(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "source")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)
            proposals = [{"proposal_id": f"p_{i}", "approved": False, "confidence_class": "F"} for i in range(5)]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)

            decisions_path = os.path.join(tmp_dir, "decisions.csv")
            fieldnames = ["proposal_id", "proposal_reference", "current_confidence_class", "decision",
                          "reason_codes", "required_evidence", "reviewer", "reviewed_at", "review_notes",
                          "next_action", "human_confirmation"]
            rows = []
            for i in range(5):
                rows.append({
                    "proposal_id": f"p_{i}",
                    "proposal_reference": "ref",
                    "current_confidence_class": "F",
                    "decision": "REJECT",
                    "reason_codes": "NO_EXPLICIT_RELATION",
                    "required_evidence": "",
                    "reviewer": "test_reviewer",
                    "reviewed_at": "2026-07-13T17:00:00Z",
                    "review_notes": "",
                    "next_action": "",
                    "human_confirmation": "I_REVIEWED_THIS_PROPOSAL"
                })
            with open(decisions_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_human_decisions import main as val_main
                sys.argv = ["validate_human_decisions.py", "--decisions", decisions_path, "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 0)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestDecisionsApprovedAlwaysFalse(unittest.TestCase):
    """15. Decisão mantém approved=false"""

    def test_approved_always_false_in_finalize(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "source")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)
            proposals = [{"proposal_id": f"p_{i}", "approved": False, "confidence_class": "F"} for i in range(5)]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)

            review_dir = os.path.join(tmp_dir, "review")
            os.makedirs(review_dir, mode=0o700, exist_ok=True)

            decisions_path = os.path.join(review_dir, "human_decisions_private.csv")
            fieldnames = ["proposal_id", "proposal_reference", "current_confidence_class", "decision",
                          "reason_codes", "required_evidence", "reviewer", "reviewed_at", "review_notes",
                          "next_action", "human_confirmation"]
            rows = []
            for i in range(5):
                rows.append({
                    "proposal_id": f"p_{i}",
                    "proposal_reference": "ref",
                    "current_confidence_class": "F",
                    "decision": "REJECT",
                    "reason_codes": "NO_EXPLICIT_RELATION",
                    "required_evidence": "",
                    "reviewer": "test_reviewer",
                    "reviewed_at": "2026-07-13T17:00:00Z",
                    "review_notes": "",
                    "next_action": "",
                    "human_confirmation": "I_REVIEWED_THIS_PROPOSAL"
                })
            with open(decisions_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            readme_path = os.path.join(review_dir, "README_PRIVATE.txt")
            with open(readme_path, "w") as f:
                f.write("test")

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.finalize_review import main as fin_main
                sys.argv = ["finalize_review.py", "--decisions", decisions_path, "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    fin_main()
                self.assertEqual(cm.exception.code, 0)

                json_path = os.path.join(review_dir, "human_decisions_private.json")
                with open(json_path, "r") as f:
                    data = json.load(f)
                for dec in data:
                    self.assertFalse(dec["approved"])
                    self.assertFalse(dec["eligible_for_bootstrap"])
                    self.assertFalse(dec["eligible_for_backfill"])
                    self.assertFalse(dec["eligible_for_phase_0e3"])
                    self.assertEqual(dec["original_confidence_class"], "F")
                    self.assertEqual(dec["decision_version"], 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestDecisionsNotesLimit(unittest.TestCase):
    """16. Review notes têm limite"""

    def test_notes_too_long(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("x" * 1001)
        self.assertFalse(ok)

    def test_notes_at_limit(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("x" * 1000)
        self.assertTrue(ok)


class TestDecisionsNotesBlockSecrets(unittest.TestCase):
    """17. Review notes bloqueiam secrets"""

    def test_notes_with_password(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("A senha do sistema é 123")
        self.assertFalse(ok)

    def test_notes_with_token(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("O token de acesso foi exposto")
        self.assertFalse(ok)

    def test_notes_with_cookie(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("Cookie de sessão armazenado")
        self.assertFalse(ok)

    def test_notes_with_email(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("Contato: usuario@exemplo.com")
        self.assertFalse(ok)


class TestDecisionsNotesRejectHtml(unittest.TestCase):
    """18. HTML é rejeitado"""

    def test_notes_with_html_tags(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("Revisão <b>necessária</b>")
        self.assertFalse(ok)

    def test_notes_with_script_tag(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("Revisão <script>alert(1)</script>")
        self.assertFalse(ok)


class TestDecisionsNotesRejectUrl(unittest.TestCase):
    """19. URL em notes é rejeitada"""

    def test_notes_with_http_url(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("Verificar em http://exemplo.com")
        self.assertFalse(ok)

    def test_notes_with_https_url(self):
        from scripts.fase0e2.validate_human_decisions import validate_notes
        ok, _ = validate_notes("Verificar em https://exemplo.com")
        self.assertFalse(ok)


class TestDecisionsEmptyReasonCodes(unittest.TestCase):
    """20. reason_codes vazio é rejeitado"""

    def test_empty_reason_codes(self):
        tmp_dir = tempfile.mkdtemp()
        try:
            source_dir = os.path.join(tmp_dir, "source")
            os.makedirs(source_dir, mode=0o700, exist_ok=True)
            proposals = [{"proposal_id": f"p_{i}", "approved": False, "confidence_class": "F"} for i in range(5)]
            with open(os.path.join(source_dir, "mapping_proposals_private.json"), "w") as f:
                json.dump(proposals, f)

            decisions_path = os.path.join(tmp_dir, "decisions.csv")
            fieldnames = ["proposal_id", "proposal_reference", "current_confidence_class", "decision",
                          "reason_codes", "required_evidence", "reviewer", "reviewed_at", "review_notes",
                          "next_action", "human_confirmation"]
            rows = []
            for i in range(5):
                rows.append({
                    "proposal_id": f"p_{i}",
                    "proposal_reference": "ref",
                    "current_confidence_class": "F",
                    "decision": "REJECT",
                    "reason_codes": "",
                    "required_evidence": "",
                    "reviewer": "test_reviewer",
                    "reviewed_at": "2026-07-13T17:00:00Z",
                    "review_notes": "",
                    "next_action": "",
                    "human_confirmation": "I_REVIEWED_THIS_PROPOSAL"
                })
            with open(decisions_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)

            sys_argv = sys.argv
            try:
                from scripts.fase0e2.validate_human_decisions import main as val_main
                sys.argv = ["validate_human_decisions.py", "--decisions", decisions_path, "--source", source_dir]
                with self.assertRaises(SystemExit) as cm:
                    val_main()
                self.assertEqual(cm.exception.code, 1)
            finally:
                sys.argv = sys_argv
        finally:
            shutil.rmtree(tmp_dir)


class TestDecisionsValidReasonCodesPerDecision(unittest.TestCase):
    """21. Todos os reason codes estão presentes e corretos"""

    def test_all_reject_reasons_present(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        expected = {
            "NO_EXPLICIT_RELATION", "INSUFFICIENT_EVIDENCE", "AMBIGUOUS_IDENTITY",
            "AMBIGUOUS_OPERATIONAL_SCOPE", "INACTIVE_OR_OBSOLETE_RECORD",
            "DUPLICATE_OR_CONFLICTING_RECORD", "NOT_A_VALID_OPERATIONAL_USER",
            "NOT_A_VALID_OPERATIONAL_CLIENT"
        }
        self.assertEqual(ALLOWED_REASONS["REJECT"], expected)

    def test_all_pending_reasons_present(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        expected = {
            "WAITING_HUMAN_CONTEXT", "WAITING_BUSINESS_VALIDATION",
            "WAITING_ROLE_CONFIRMATION", "WAITING_FARM_CONFIRMATION",
            "INSUFFICIENT_INFORMATION", "CONFLICT_REQUIRES_REVIEW"
        }
        self.assertEqual(ALLOWED_REASONS["PENDING"], expected)

    def test_all_evidence_reasons_present(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        expected = {
            "REQUIRE_ACCOUNT_OWNER_CONFIRMATION", "REQUIRE_EMPLOYMENT_CONFIRMATION",
            "REQUIRE_CLIENT_RELATION_CONFIRMATION", "REQUIRE_ROLE_CONFIRMATION",
            "REQUIRE_FARM_ACCESS_CONFIRMATION", "REQUIRE_OPERATIONAL_RESPONSIBILITY_CONFIRMATION"
        }
        self.assertEqual(ALLOWED_REASONS["REQUEST_OPERATIONAL_EVIDENCE"], expected)

    def test_all_manual_reasons_present(self):
        from scripts.fase0e2.validate_human_decisions import ALLOWED_REASONS
        expected = {
            "LEGACY_MAPPING_NOT_SAFE", "MANUAL_ONBOARDING_PREFERRED",
            "NEW_IDENTITY_REQUIRED", "NEW_ORGANIZATION_REQUIRED",
            "NEW_MEMBERSHIP_REQUIRED", "NEW_FARM_ACCESS_REQUIRED",
            "LEGACY_DATA_NOT_AUTHORITATIVE"
        }
        self.assertEqual(ALLOWED_REASONS["MANUAL_REGISTRATION_FUTURE"], expected)


if __name__ == '__main__':
    unittest.main()
