#!/usr/bin/env bash
# destroy_staging.sh — Apaga totalmente o ambiente de staging
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$ROOT/scripts/fase0d/docker-compose.staging.yml"
PROJECT_NAME="wins_agro_fase0d"
ENV_FILE="/root/.config/wins_agro/fase0d/staging.env"

CONFIRMED=0
REMOVE_ENV=0

for arg in "$@"; do
  if [[ "$arg" == "--confirm-destroy-fase0d" ]]; then
    CONFIRMED=1
  fi
  if [[ "$arg" == "--remove-env" ]]; then
    REMOVE_ENV=1
  fi
done

if [[ "$CONFIRMED" -ne 1 ]]; then
    echo "ERRO: Este comando destrói todos os dados de staging." >&2
    echo "Execute novamente com a flag de confirmação:" >&2
    echo "  bash scripts/fase0d/destroy_staging.sh --confirm-destroy-fase0d" >&2
    exit 1
fi

echo "=== Destruindo Staging Persistente (Fase 0D) ==="

# Derruba containers e volumes rotulados
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v

# Remove imagem de staging local
if docker image inspect wins_agro_fase0d_api:staging >/dev/null 2>&1; then
    echo "Removendo imagem de staging..."
    docker rmi -f wins_agro_fase0d_api:staging || true
fi

# Opcional: remove arquivo env sintético
if [[ "$REMOVE_ENV" -eq 1 ]]; then
    if [[ -f "$ENV_FILE" ]]; then
        echo "Removendo arquivo env: $ENV_FILE"
        rm -f "$ENV_FILE"
    fi
fi

echo "Staging destruído com sucesso!"
