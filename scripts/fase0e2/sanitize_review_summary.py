#!/usr/bin/env python3
# sanitize_review_summary.py — Gera relatório sanitizado público a partir do pacote privado de decisões
import os
import sys
import json
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Sanitização de Resumo - Fase 0E2")
    parser.add_argument("--review-dir", required=True, help="Diretório da revisão da Fase 0E2 com decisões finalizadas")
    parser.add_argument("--output", required=True, help="Caminho do arquivo Markdown de saída sanitizado")
    return parser.parse_args()

def check_security(path):
    if os.path.islink(path):
        print(f"ERRO: Symlink detectado em {path}", file=sys.stderr)
        sys.exit(2)
    real_path = os.path.realpath(path)
    if not (real_path.startswith("/root/.config/wins_agro/") or real_path.startswith("/tmp/")):
        print(f"ERRO: Acesso fora do diretório permitido para {path}", file=sys.stderr)
        sys.exit(2)

def main():
    args = parse_args()
    review_dir = os.path.abspath(args.review_dir)
    output_path = os.path.abspath(args.output)

    check_security(review_dir)
    check_security(output_path)

    summary_path = os.path.join(review_dir, "review_summary_private.json")
    if not os.path.exists(summary_path):
        print(f"ERRO: review_summary_private.json não encontrado em {review_dir}", file=sys.stderr)
        sys.exit(1)

    check_security(summary_path)

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    decisions_by_category = summary.get("decisions_by_category", {})
    reasons_by_code = summary.get("reasons_by_code", {})
    reviewed_total = summary.get("reviewed_total", 0)
    approved_total = summary.get("approved_total", 0)
    eligible_bootstrap = summary.get("eligible_for_bootstrap", 0)
    eligible_phase_0e3 = summary.get("eligible_for_phase_0e3", 0)
    source_exec = summary.get("source_execution_id", "unknown")
    batch_ts = summary.get("timestamp", "unknown")

    md_lines = []
    md_lines.append("# Evidências Sanitizadas da Revisão Humana — Fase 0E2")
    md_lines.append("")
    md_lines.append("Este relatório resume os resultados e métricas sanitizadas da revisão humana offline.")
    md_lines.append("")
    md_lines.append("## 1. Estatísticas de Execução da Revisão")
    md_lines.append(f"* **Lote de Revisão**: `review-batch-{batch_ts}`")
    md_lines.append(f"* **Lote de Origem da Fase 0E1**: `{source_exec}`")
    md_lines.append(f"* **Total de Propostas Avaliadas**: {reviewed_total}")
    md_lines.append(f"* **Classe de Confiança de Partida**: F (todas)")
    md_lines.append("")
    md_lines.append("## 2. Decisões por Categoria")
    md_lines.append(f"* **REJECT** (Rejeitadas): {decisions_by_category.get('REJECT', 0)}")
    md_lines.append(f"* **PENDING** (Pendentes): {decisions_by_category.get('PENDING', 0)}")
    md_lines.append(f"* **REQUEST_OPERATIONAL_EVIDENCE** (Exige Evidências): {decisions_by_category.get('REQUEST_OPERATIONAL_EVIDENCE', 0)}")
    md_lines.append(f"* **MANUAL_REGISTRATION_FUTURE** (Cadastro Manual Futuro): {decisions_by_category.get('MANUAL_REGISTRATION_FUTURE', 0)}")
    md_lines.append("")
    md_lines.append("## 3. Indicadores de Segurança e Integridade")
    md_lines.append(f"* **Total de Propostas Aprovadas (approved=true)**: {approved_total}")
    md_lines.append(f"* **Total de Propostas Elegíveis para Bootstrap**: {eligible_bootstrap}")
    md_lines.append(f"* **Total de Propostas Elegíveis para Backfill**: 0")
    md_lines.append(f"* **Total de Propostas Elegíveis para Fase 0E3**: {eligible_phase_0e3}")
    md_lines.append("")
    md_lines.append("## 4. Distribuição de Motivos (Reason Codes)")
    for rc, count in sorted(reasons_by_code.items()):
        md_lines.append(f"* `{rc}`: {count}")
    md_lines.append("")
    md_lines.append("## 5. Garantia de Privacidade")
    md_lines.append("Conforme requisitos da Fase 0E2, este documento não contém nomes reais de clientes,")
    md_lines.append("nomes de propriedades, endereços de e-mail, nomes de usuários, caminhos privados")
    md_lines.append("ou detalhes sobre observações internas das decisões.")
    md_lines.append("")

    content = "\n".join(md_lines)

    tmp_path = output_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp_path, output_path)
    os.chmod(output_path, 0o600)

    print(f"sanitized_report=true")
    print(f"output_path={output_path}")
    sys.exit(0)

if __name__ == '__main__':
    main()
