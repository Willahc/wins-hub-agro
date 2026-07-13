#!/usr/bin/env bash
# stop_staging.sh — Para containers do staging sem apagar os dados persistentes
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT/scripts/fase0d/docker-compose.staging.yml"
PROJECT_NAME="wins_agro_fase0d"
ENV_FILE="/root/.config/wins_agro/fase0d/staging.env"

echo "=== Parando Staging Persistente (Fase 0D) ==="

docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" stop
echo "Staging parado com sucesso. Dados preservados no volume Docker."
