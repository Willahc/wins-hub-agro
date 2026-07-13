#!/usr/bin/env python3
# validate_human_decisions.py — Valida o arquivo CSV de decisões humanas preenchido
import os
import sys
import json
import csv
import datetime
import argparse

# Configuração permitida
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

def parse_args():
    parser = argparse.ArgumentParser(description="Validação de Decisões Humanas - Fase 0E2")
    parser.add_argument("--decisions", required=True, help="Caminho do arquivo human_decisions_private.csv")
    parser.add_argument("--source", required=True, help="Diretório do pacote de origem da Fase 0E1")
    return parser.parse_args()

def check_security(path):
    if os.path.islink(path):
        print(f"ERRO: Symlink detectado em {path}", file=sys.stderr)
        sys.exit(2)
    real_path = os.path.realpath(path)
    if not (real_path.startswith("/root/.config/wins_agro/") or real_path.startswith("/tmp/")):
        print(f"ERRO: Acesso fora do diretório permitido para {path}", file=sys.stderr)
        sys.exit(2)

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

def main():
    args = parse_args()
    decisions_path = os.path.abspath(args.decisions)
    source_dir = os.path.abspath(args.source)

    if not os.path.exists(decisions_path):
        print(f"ERRO: Arquivo de decisões não encontrado: {decisions_path}", file=sys.stderr)
        sys.exit(1)

    check_security(decisions_path)
    check_security(source_dir)

    # Carrega propostas de origem
    props_json = os.path.join(source_dir, "mapping_proposals_private.json")
    if not os.path.exists(props_json):
        print(f"ERRO: mapping_proposals_private.json ausente na origem", file=sys.stderr)
        sys.exit(1)

    with open(props_json, "r") as f:
        proposals = json.load(f)

    # Processa e valida decisões
    rows = []
    with open(decisions_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    if len(rows) != 5:
        print(f"ERRO: Esperado exatamente 5 decisões, obtido {len(rows)}", file=sys.stderr)
        sys.exit(1)

    pids_found = set()
    for row in rows:
        pid = row.get("proposal_id")
        if not pid:
            print("ERRO: proposal_id vazio detectado", file=sys.stderr)
            sys.exit(1)
        if pid in pids_found:
            print(f"ERRO: proposal_id duplicado: {pid}", file=sys.stderr)
            sys.exit(1)
        pids_found.add(pid)

        # Procura original
        matching_prop = next((p for p in proposals if p["proposal_id"] == pid), None)
        if not matching_prop:
            print(f"ERRO: proposal_id desconhecido no lote: {pid}", file=sys.stderr)
            sys.exit(1)

        decision = row.get("decision", "").strip()
        if decision not in ALLOWED_REASONS:
            print(f"ERRO: Decisão não permitida para {pid}: '{decision}'", file=sys.stderr)
            sys.exit(1)

        reason_codes = [r.strip() for r in row.get("reason_codes", "").split(",") if r.strip()]
        if not reason_codes:
            print(f"ERRO: reason_codes vazio para {pid}", file=sys.stderr)
            sys.exit(1)

        for rc in reason_codes:
            if rc not in ALLOWED_REASONS[decision]:
                print(f"ERRO: reason_code '{rc}' incompatível com decisão '{decision}' para {pid}", file=sys.stderr)
                sys.exit(1)

        reviewer = row.get("reviewer", "").strip()
        if not reviewer:
            print(f"ERRO: reviewer vazio para {pid}", file=sys.stderr)
            sys.exit(1)

        ts_ok, ts_err = validate_iso_timestamp(row.get("reviewed_at", "").strip())
        if not ts_ok:
            print(f"ERRO: reviewed_at inválido para {pid}: {ts_err}", file=sys.stderr)
            sys.exit(1)

        notes = row.get("review_notes", "").strip()
        notes_ok, notes_err = validate_notes(notes)
        if not notes_ok:
            print(f"ERRO: review_notes inválido para {pid}: {notes_err}", file=sys.stderr)
            sys.exit(1)

        conf = row.get("human_confirmation", "").strip()
        if conf != "I_REVIEWED_THIS_PROPOSAL":
            print(f"ERRO: human_confirmation inválida para {pid}: '{conf}'", file=sys.stderr)
            sys.exit(1)

    print("decisions_valid=true")
    sys.exit(0)

if __name__ == '__main__':
    main()
