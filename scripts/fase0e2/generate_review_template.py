#!/usr/bin/env python3
# generate_review_template.py — Gera o template para revisão humana da Fase 0E2
import os
import sys
import json
import csv
import datetime
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Geração de Template de Revisão - Fase 0E2")
    parser.add_argument("--source", required=True, help="Diretório do pacote de origem da Fase 0E1")
    parser.add_argument("--output-root", required=True, help="Diretório raiz para salvar a revisão (Fase 0E2)")
    return parser.parse_args()

def check_security(path):
    if os.path.islink(path):
        print(f"ERRO: Symlink detectado em {path}", file=sys.stderr)
        sys.exit(2)
    real_path = os.path.realpath(path)
    if not (real_path.startswith("/root/.config/wins_agro/") or real_path.startswith("/tmp/")):
        print(f"ERRO: Acesso fora do diretório permitido para {path}", file=sys.stderr)
        sys.exit(2)

def write_atomic(filepath, content_list, fieldnames):
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(content_list)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp_path, filepath)
    os.chmod(filepath, 0o600)

def main():
    args = parse_args()
    source_dir = os.path.abspath(args.source)
    output_root = os.path.abspath(args.output_root)

    # 1. Valida o pacote de origem (chama validação básica)
    if not os.path.isdir(source_dir):
        print(f"ERRO: Origem inválida: {source_dir}", file=sys.stderr)
        sys.exit(1)

    check_security(source_dir)

    proposals_path = os.path.join(source_dir, "mapping_proposals_private.json")
    if not os.path.exists(proposals_path):
        print(f"ERRO: mapping_proposals_private.json ausente", file=sys.stderr)
        sys.exit(1)

    check_security(proposals_path)

    with open(proposals_path, "r") as f:
        proposals = json.load(f)

    if len(proposals) != 5:
        print(f"ERRO: Esperado exatamente 5 propostas, obtido {len(proposals)}", file=sys.stderr)
        sys.exit(1)

    # 2. Cria diretório de revisão da Fase 0E2
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    target_dir = os.path.join(output_root, timestamp)
    os.makedirs(target_dir, mode=0o700, exist_ok=True)
    os.chmod(target_dir, 0o700)

    check_security(target_dir)

    # 3. Cria o checklist privado de revisão para orientar o operador
    checklist_src = os.path.join(source_dir, "mapping_review_checklist_private.csv")
    check_security(checklist_src)

    proposal_refs = {}
    with open(checklist_src, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pid = row["proposal_id"]
            ref = f"{row['display_user']} / {row['display_client']}"
            proposal_refs[pid] = ref

    # 4. Constrói a lista de linhas para o template de decisões
    fieldnames = [
        "proposal_id",
        "proposal_reference",
        "current_confidence_class",
        "decision",
        "reason_codes",
        "required_evidence",
        "reviewer",
        "reviewed_at",
        "review_notes",
        "next_action",
        "human_confirmation"
    ]

    template_rows = []
    for prop in proposals:
        pid = prop["proposal_id"]
        ref = proposal_refs.get(pid, "Unknown Client / User")

        template_rows.append({
            "proposal_id": pid,
            "proposal_reference": ref,
            "current_confidence_class": "F",
            "decision": "",
            "reason_codes": "",
            "required_evidence": "",
            "reviewer": "",
            "reviewed_at": "",
            "review_notes": "",
            "next_action": "",
            "human_confirmation": ""
        })

    # 5. Salva o template atomicamente
    target_template = os.path.join(target_dir, "human_decisions_template_private.csv")
    write_atomic(target_template, template_rows, fieldnames)

    # Salva manifesto da Fase 0E2 com o source ID mapeado
    manifest_data = {
        "timestamp": timestamp,
        "source_execution_id": os.path.basename(source_dir),
        "status": "AWAITING_HUMAN_REVIEW",
        "files": {
            "human_decisions_template_private.csv": "template_only"
        }
    }
    manifest_path = os.path.join(target_dir, "review_manifest_private.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest_data, f, indent=2)
    os.chmod(manifest_path, 0o600)

    # README_PRIVATE.txt
    readme_path = os.path.join(target_dir, "README_PRIVATE.txt")
    with open(readme_path, "w") as f:
        f.write("Fase 0E2 — Revisão Humana Offline\n")
        f.write(f"Gerado em: {timestamp}\n")
        f.write("Instruções:\n")
        f.write("1. Abra o arquivo human_decisions_template_private.csv\n")
        f.write("2. Preencha os campos decision (REJECT, PENDING, REQUEST_OPERATIONAL_EVIDENCE, MANUAL_REGISTRATION_FUTURE)\n")
        f.write("3. Preencha reason_codes com motivos permitidos\n")
        f.write("4. Preencha reviewer, reviewed_at, review_notes e human_confirmation (I_REVIEWED_THIS_PROPOSAL)\n")
        f.write("5. Salve o arquivo como human_decisions_private.csv e execute validate-decisions\n")
    os.chmod(readme_path, 0o600)

    print(f"template_created=true")
    print(f"output_path={target_template}")
    sys.exit(0)

if __name__ == '__main__':
    main()
