#!/bin/bash
# cleanup_review_outputs.sh — Limpa diretórios temporários de homologação e dry-run da Fase 0E2
set -euo pipefail

echo "=== Limpando arquivos temporários da Fase 0E2 ==="

# Remove backups temporários em /tmp pertencentes à Fase 0E2
rm -rf /tmp/wins_agro_fase0e2_*

# Remove arquivos temporários .tmp no diretório de scripts
find /root/wins_agro_v1/scripts/fase0e2 -name "*.tmp" -delete

# Procura arquivos .tmp temporários no diretório de configuração do usuário para esta fase
find /root/.config/wins_agro/fase0e2 -name "*.tmp" -delete || true

echo "Limpeza concluída com sucesso!"
