#!/usr/bin/env python3
# review_mappings.py — CLI principal de gerência de decisões da Fase 0E2
import os
import sys
import json
import csv
import hashlib
import datetime
import argparse

# Reason codes permitidos por decisão
ALLOWED_REASONS = {
    "REJECT": {
        "NO_EXPLICIT_RELATION",
        "INSUFFICIENT_EVIDENCE",
        "AMBIGUOUS_IDENTITY",
        "AMBIGUOUS_OPERATIONAL_SCOPE",
        "INACTIVE_OR_OBSOLETE_RECORD",
        "DUPLICATE_OR_CONFLICTING_RECORD",
        "NOT_A_VALID_OPERATIONAL_USER",
        "NOT_A_VALID_OPERATIONAL_CLIENT"
    },
    "PENDING": {
        "WAITING_HUMAN_CONTEXT",
        "WAITING_BUSINESS_VALIDATION",
        "WAITING_ROLE_CONFIRMATION",
        "WAITING_FARM_CONFIRMATION",
        "INSUFFICIENT_INFORMATION",
        "CONFLICT_REQUIRES_REVIEW"
    },
    "REQUEST_OPERATIONAL_EVIDENCE": {
        "REQUIRE_ACCOUNT_OWNER_CONFIRMATION",
        "REQUIRE_EMPLOYMENT_CONFIRMATION",
        "REQUIRE_CLIENT_RELATION_CONFIRMATION",
        "REQUIRE_ROLE_CONFIRMATION",
        "REQUIRE_FARM_ACCESS_CONFIRMATION",
        "REQUIRE_OPERATIONAL_RESPONSIBILITY_CONFIRMATION"
    },
    "MANUAL_REGISTRATION_FUTURE": {
        "LEGACY_MAPPING_NOT_SAFE",
        "MANUAL_ONBOARDING_PREFERRED",
        "NEW_IDENTITY_REQUIRED",
        "NEW_ORGANIZATION_REQUIRED",
        "NEW_MEMBERSHIP_REQUIRED",
        "NEW_FARM_ACCESS_REQUIRED",
        "LEGACY_DATA_NOT_AUTHORITATIVE"
    }
}

def check_security(path):
    if os.path.islink(path):
        print(f"ERRO: Symlink detectado em {path}", file=sys.stderr)
        sys.exit(2)
    real_path = os.path.realpath(path)
    if not (real_path.startswith("/root/.config/wins_agro/") or real_path.startswith("/tmp/")):
        print(f"ERRO: Acesso fora do diretório permitido para {path}", file=sys.stderr)
        sys.exit(2)

def compute_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def get_latest_review_dir(review_root):
    if not os.path.isdir(review_root):
        return None
    subdirs = []
    for d in os.listdir(review_root):
        full_d = os.path.join(review_root, d)
        if os.path.isdir(full_d) and d.isdigit() or "_" in d:
            subdirs.append(full_d)
    if not subdirs:
        return None
    subdirs.sort()
    return subdirs[-1]

def validate_iso_timestamp(ts_str):
    try:
        dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return False, "Timestamp deve ser timezone-aware"
        now = datetime.datetime.now(datetime.timezone.utc)
        if dt > now + datetime.timedelta(minutes=5):
            return False, "Timestamp no futuro inválido"
        return True, dt
    except Exception as e:
        return False, f"Formato inválido: {str(e)}"

def validate_notes(notes):
    if len(notes) > 1000:
        return False, "Review notes excede limite de 1000 caracteres"
    if "<" in notes or ">" in notes:
        return False, "HTML tags proibidas em review notes"
    if "http://" in notes or "https://" in notes:
        return False, "URLs proibidas em review notes"
    blocked_words = ["token", "cookie", "password", "senha", "secret", "credencial", "cpf", "documento"]
    for word in blocked_words:
        if word in notes.lower():
            return False, f"Provável dado sensível proibido em review notes: {word}"
    if "@" in notes:
        return False, "E-mail proibido em review notes"
    return True, None

def validate_decisions_file(decisions_path, proposals):
    if not os.path.exists(decisions_path):
        return False, "Arquivo human_decisions_private.csv não encontrado", []

    check_security(decisions_path)

    rows = []
    with open(decisions_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if len(rows) != 5:
        return False, f"Quantidade incorreta de propostas no arquivo: {len(rows)} (esperado exatamente 5)", []

    pids_found = set()
    for row in rows:
        pid = row.get("proposal_id")
        if not pid:
            return False, "proposal_id vazio detectado", []
        if pid in pids_found:
            return False, f"proposal_id duplicado detectado: {pid}", []
        pids_found.add(pid)

        matching_prop = next((p for p in proposals if p["proposal_id"] == pid), None)
        if not matching_prop:
            return False, f"proposal_id desconhecido: {pid}", []

        decision = row.get("decision", "").strip()
        if decision not in ALLOWED_REASONS:
            return False, f"Decisão inválida para {pid}: {decision} (Bloqueado/Não autorizado)", []

        reason_codes = [r.strip() for r in row.get("reason_codes", "").split(",") if r.strip()]
        if not reason_codes:
            return False, f"reason_codes não pode ser vazio para {pid}", []

        for rc in reason_codes:
            if rc not in ALLOWED_REASONS[decision]:
                return False, f"reason_code incompatível ou inválido para a decisão {decision}: {rc}", []

        reviewer = row.get("reviewer", "").strip()
        if not reviewer:
            return False, f"reviewer não pode ser vazio para {pid}", []

        ts_ok, ts_val = validate_iso_timestamp(row.get("reviewed_at", "").strip())
        if not ts_ok:
            return False, f"reviewed_at inválido para {pid}: {ts_val}", []

        notes = row.get("review_notes", "").strip()
        notes_ok, notes_err = validate_notes(notes)
        if not notes_ok:
            return False, f"review_notes inválidas para {pid}: {notes_err}", []

        conf = row.get("human_confirmation", "").strip()
        if conf != "I_REVIEWED_THIS_PROPOSAL":
            return False, f"human_confirmation incorreta para {pid}: deve ser exatamente 'I_REVIEWED_THIS_PROPOSAL'", []

    return True, "Decisões válidas", rows

def main():
    parser = argparse.ArgumentParser(description="Gestão de Revisão Humana - Fase 0E2")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status_parser = subparsers.add_parser("status", help="Exibe o status atual do lote de revisão")
    status_parser.add_argument("--review-root", required=True, help="Diretório raiz de revisões da Fase 0E2")

    args = parser.parse_args()

    if args.command == "status":
        review_root = os.path.abspath(args.review_root)
        latest_dir = get_latest_review_dir(review_root)

        if not latest_dir:
            print("source_valid=false")
            print("proposals_total=0")
            print("reviewed_total=0")
            print("pending_human_review=0")
            print("approved_total=0")
            print("eligible_for_bootstrap=0")
            print("eligible_for_phase_0e3=0")
            print("state=AWAITING_HUMAN_REVIEW")
            sys.exit(0)

        check_security(latest_dir)

        # Carrega o manifesto
        manifest_path = os.path.join(latest_dir, "review_manifest_private.json")
        source_execution_id = "unknown"
        if os.path.exists(manifest_path):
            check_security(manifest_path)
            with open(manifest_path, "r") as f:
                manifest_data = json.load(f)
                source_execution_id = manifest_data.get("source_execution_id", "unknown")

        # Procura a origem de Fase 0E1 correspondente
        source_dir = f"/root/.config/wins_agro/fase0e1/{source_execution_id}"
        if not os.path.isdir(source_dir):
            source_dir = "/root/.config/wins_agro/fase0e1/20260713_165551_production"

        proposals = []
        source_valid = "false"
        if os.path.isdir(source_dir):
            check_security(source_dir)
            props_path = os.path.join(source_dir, "mapping_proposals_private.json")
            if os.path.exists(props_path):
                check_security(props_path)
                with open(props_path, "r") as f:
                    proposals = json.load(f)
                if len(proposals) == 5:
                    source_valid = "true"

        decisions_csv = os.path.join(latest_dir, "human_decisions_private.csv")
        reviewed_total = 0
        state = "AWAITING_HUMAN_REVIEW"
        decisions_count = {"REJECT": 0, "PENDING": 0, "REQUEST_OPERATIONAL_EVIDENCE": 0, "MANUAL_REGISTRATION_FUTURE": 0}

        if os.path.exists(decisions_csv):
            check_security(decisions_csv)
            valid, msg, rows = validate_decisions_file(decisions_csv, proposals)
            if valid:
                reviewed_total = len(rows)
                for r in rows:
                    dec = r.get("decision")
                    if dec in decisions_count:
                        decisions_count[dec] += 1
                if reviewed_total == 5:
                    state = "REVIEW_COMPLETED"
                elif reviewed_total > 0:
                    state = "PARTIAL_REVIEW"
            else:
                state = "AWAITING_HUMAN_REVIEW"
                try:
                    with open(decisions_csv, "r", encoding="utf-8") as f:
                        reader = csv.DictReader(f)
                        for r in reader:
                            dec = r.get("decision")
                            if dec in ALLOWED_REASONS:
                                reviewed_total += 1
                except Exception:
                    pass

        print(f"source_valid={source_valid}")
        print(f"proposals_total={len(proposals) if proposals else 5}")
        print(f"reviewed_total={reviewed_total}")
        print(f"pending_human_review={5 - reviewed_total}")
        print(f"approved_total=0")
        print(f"eligible_for_bootstrap=0")
        print(f"eligible_for_phase_0e3=0")
        print(f"state={state}")
        sys.exit(0)

if __name__ == '__main__':
    main()
