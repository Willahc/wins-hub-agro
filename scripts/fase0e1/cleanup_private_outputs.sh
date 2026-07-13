#!/usr/bin/env bash
# cleanup_private_outputs.sh — Limpa artefatos temporários do container e do /tmp do host
set -euo pipefail

echo "=== Limpando Arquivos Temporários de Staging e Produção ==="

# Limpa no host
rm -rf /tmp/fase0e1

# Limpa nos containers se eles estiverem rodando
if docker ps -q -f name=wins_agro_fase0d_api >/dev/null; then
    docker exec wins_agro_fase0d_api rm -rf /tmp/fase0e1 || true
fi

if docker ps -q -f name=wins_agro_v1-api-1 >/dev/null; then
    docker exec wins_agro_v1-api-1 rm -rf /tmp/fase0e1 || true
fi

echo "Limpeza concluída com sucesso."
