#!/usr/bin/env bash
# status_staging.sh — Exibe o status do ambiente de staging
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT/scripts/fase0d/docker-compose.staging.yml"
PROJECT_NAME="wins_agro_fase0d"
ENV_FILE="/root/.config/wins_agro/fase0d/staging.env"

echo "=== Status do Staging Persistente (Fase 0D) ==="

if ! docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps >/dev/null 2>&1; then
    echo "Staging está DESLIGADO ou não iniciado."
    exit 0
fi

# Exibe container ps
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps

# Informações de versão e porta
echo ""
echo "Commit Atual: $(git rev-parse --short HEAD)"
echo "Porta Local API: 127.0.0.1:18080"
echo "Porta PostgreSQL: Não publicada (Acesso interno apenas)"
echo "Configuração: $ENV_FILE (Protegido)"
echo ""
