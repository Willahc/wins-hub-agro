#!/usr/bin/env python3
# finalize_review.py — Consolida e empacota as decisões humanas validadas
import os
import sys
import json
import csv
import hashlib
import uuid
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Finalização de Revisão - Fase 0E2")
    parser.add_argument("--decisions", required=True, help="Caminho do arquivo human_decisions_private.csv preenchido")
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

def compute_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def write_atomic_json(filepath, data):
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp_path, filepath)
    os.chmod(filepath, 0o600)

def write_atomic_csv(filepath, content_list, fieldnames):
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
    decisions_path = os.path.abspath(args.decisions)
    source_dir = os.path.abspath(args.source)

    if not os.path.exists(decisions_path):
        print(f"ERRO: Arquivo de decisões não encontrado: {decisions_path}", file=sys.stderr)
        sys.exit(1)

    check_security(decisions_path)
    check_security(source_dir)

    target_dir = os.path.dirname(decisions_path)
    check_security(target_dir)

    # Carrega propostas de origem
    props_json = os.path.join(source_dir, "mapping_proposals_private.json")
    if not os.path.exists(props_json):
        print(f"ERRO: mapping_proposals_private.json ausente", file=sys.stderr)
        sys.exit(1)

    with open(props_json, "r") as f:
        proposals = json.load(f)

    # Lê decisões preenchidas pelo operador
    decisions_rows = []
    with open(decisions_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            decisions_rows.append(row)

    # Validações internas
    if len(decisions_rows) != 5:
        print(f"ERRO: Esperado exatamente 5 decisões", file=sys.stderr)
        sys.exit(1)

    final_decisions = []
    dec_csv_rows = []

    dec_counts = {"REJECT": 0, "PENDING": 0, "REQUEST_OPERATIONAL_EVIDENCE": 0, "MANUAL_REGISTRATION_FUTURE": 0}
    reason_counts = {}

    source_execution_id = os.path.basename(source_dir)

    for row in decisions_rows:
        pid = row["proposal_id"]
        matching_prop = next((p for p in proposals if p["proposal_id"] == pid), None)
        if not matching_prop:
            print(f"ERRO: proposal_id desconhecido: {pid}", file=sys.stderr)
            sys.exit(1)

        # Determina o checksum da proposta original
        prop_str = json.dumps(matching_prop, sort_keys=True).encode("utf-8")
        prop_hash = hashlib.sha256(prop_str).hexdigest()

        # Gera ID único de decisão de forma determinística
        dec_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"wins-agro.review.{pid}.{row['reviewed_at']}"))

        dec_counts[row["decision"]] += 1
        for rc in [r.strip() for r in row["reason_codes"].split(",") if r.strip()]:
            reason_counts[rc] = reason_counts.get(rc, 0) + 1

        decision_entry = {
            "decision_id": dec_id,
            "proposal_id": pid,
            "source_execution_id": source_execution_id,
            "source_proposal_checksum": prop_hash,
            "original_confidence_class": "F",
            "decision": row["decision"],
            "reason_codes": row["reason_codes"],
            "required_evidence": row["required_evidence"],
            "reviewer": row["reviewer"],
            "reviewed_at": row["reviewed_at"],
            "review_notes": row["review_notes"],
            "next_action": row["next_action"],
            "approved": False,
            "eligible_for_bootstrap": False,
            "eligible_for_backfill": False,
            "eligible_for_phase_0e3": False,
            "human_confirmation": row["human_confirmation"],
            "decision_version": 1
        }
        final_decisions.append(decision_entry)
        dec_csv_rows.append(decision_entry)

    # 1. Salva human_decisions_private.json
    json_dest = os.path.join(target_dir, "human_decisions_private.json")
    write_atomic_json(json_dest, final_decisions)

    # 2. Salva human_decisions_private.csv
    csv_fieldnames = [
        "decision_id", "proposal_id", "source_execution_id", "source_proposal_checksum",
        "original_confidence_class", "decision", "reason_codes", "required_evidence",
        "reviewer", "reviewed_at", "review_notes", "next_action", "approved",
        "eligible_for_bootstrap", "eligible_for_backfill", "eligible_for_phase_0e3",
        "human_confirmation", "decision_version"
    ]
    csv_dest = os.path.join(target_dir, "human_decisions_private.csv")
    write_atomic_csv(csv_dest, dec_csv_rows, csv_fieldnames)

    # 3. Salva review_summary_private.json
    summary_data = {
        "timestamp": os.path.basename(target_dir),
        "source_execution_id": source_execution_id,
        "reviewed_total": len(final_decisions),
        "decisions_by_category": dec_counts,
        "reasons_by_code": reason_counts,
        "approved_total": 0,
        "eligible_for_bootstrap": 0,
        "eligible_for_phase_0e3": 0
    }
    summary_dest = os.path.join(target_dir, "review_summary_private.json")
    write_atomic_json(summary_dest, summary_data)

    # 4. Salva review_manifest_private.json
    manifest_data = {
        "timestamp": os.path.basename(target_dir),
        "source_execution_id": source_execution_id,
        "status": "REVIEW_COMPLETED",
        "files": {
            "human_decisions_private.json": compute_sha256(json_dest),
            "human_decisions_private.csv": compute_sha256(csv_dest),
            "review_summary_private.json": compute_sha256(summary_dest)
        }
    }
    manifest_dest = os.path.join(target_dir, "review_manifest_private.json")
    write_atomic_json(manifest_dest, manifest_data)

    # 5. Gera checksums.sha256 para todos os arquivos criados
    checksums_dest = os.path.join(target_dir, "checksums.sha256")
    files_to_hash = [
        "README_PRIVATE.txt",
        "human_decisions_template_private.csv",
        "human_decisions_private.csv",
        "human_decisions_private.json",
        "review_summary_private.json",
        "review_manifest_private.json"
    ]

    checksum_lines = []
    for f in files_to_hash:
        f_path = os.path.join(target_dir, f)
        if os.path.exists(f_path):
            h = compute_sha256(f_path)
            checksum_lines.append(f"{h}  {f}\n")

    tmp_chk = checksums_dest + ".tmp"
    with open(tmp_chk, "w", encoding="utf-8") as f:
        f.writelines(checksum_lines)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp_chk, checksums_dest)
    os.chmod(checksums_dest, 0o600)

    # 6. Atualiza o relatório sanitizado docs/fase0_fundacoes/41_EVIDENCIAS_SANITIZADAS_FASE0E2.md
    md_dest = "/root/wins_agro_v1/docs/fase0_fundacoes/41_EVIDENCIAS_SANITIZADAS_FASE0E2.md"

    md_content = f"""# Evidências Sanitizadas da Revisão Humana — Fase 0E2

Este relatório resume os resultados e métricas sanitizadas da revisão humana offline.

## 1. Estatísticas de Execução da Revisão
* **Lote de Revisão**: `review-batch-{os.path.basename(target_dir)}`
* **Lote de Origem da Fase 0E1**: `{source_execution_id}`
* **Data da Revisão**: {final_decisions[0]['reviewed_at'][:10]}
* **Estado Final da Revisão**: REVIEW_COMPLETED
* **Total de Propostas Evaluadas**: 5
* **Classe de Confiança de Partida**: F (todas)

## 2. Decisões por Categoria
* **REJECT** (Rejeitadas): {dec_counts['REJECT']}
* **PENDING** (Pendentes): {dec_counts['PENDING']}
* **REQUEST_OPERATIONAL_EVIDENCE** (Exige Evidências): {dec_counts['REQUEST_OPERATIONAL_EVIDENCE']}
* **MANUAL_REGISTRATION_FUTURE** (Cadastro Manual Futuro): {dec_counts['MANUAL_REGISTRATION_FUTURE']}

## 3. Indicadores de Segurança e Integridade
* **Total de Propostas Aprovadas (approved=true)**: 0
* **Total de Propostas Elegíveis para Bootstrap**: 0
* **Total de Propostas Elegíveis para Backfill**: 0
* **Total de Propostas Elegíveis para Fase 0E3**: 0

## 4. Distribuição de Motivos (Reason Codes)
"""
    for rc, count in sorted(reason_counts.items()):
        md_content += f"* `{rc}`: {count}\n"

    md_content += """
## 5. Garantia de Privacidade
Conforme requisitos da Fase 0E2, este documento não contém nomes reais de clientes, nomes de propriedades, endereços de e-mail, nomes de usuários, caminhos privados ou detalhes sobre observações internas das decisões.
"""

    tmp_md = md_dest + ".tmp"
    with open(tmp_md, "w", encoding="utf-8") as f:
        f.write(md_content)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp_md, md_dest)

    print("review_finalized=true")
    sys.exit(0)

if __name__ == '__main__':
    main()
