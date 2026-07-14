#!/usr/bin/env bash
# apply_staging.sh — Aplica migration do módulo de Clima e Janelas Operacionais no staging
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DB_CONTAINER="wins_agro_fase0d_db"
DB_NAME="fase0d_staging"
DB_USER="fase0_test"

echo "=== Aplicando Migration: Clima e Janelas Operacionais ==="

if ! docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
  echo "ERRO: Container ${DB_CONTAINER} não está rodando." >&2
  echo "Execute: bash scripts/fase0d/start_staging.sh" >&2
  exit 1
fi

echo "Criando schema climate e tabelas..."
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -f - < "$ROOT/scripts/fase5_clima_janelas/001_climate_schema.sql"

echo "Aplicando grants..."
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -v foundation_app_role=wins_agro_app -v foundation_readonly_role=wins_agro_readonly \
  -f - < "$ROOT/scripts/fase5_clima_janelas/002_climate_grants.sql"

echo "Populando dados sintéticos de clima..."
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -f - < "$ROOT/scripts/fase5_clima_janelas/090_climate_seed_staging.sql"

echo "Validando migration..."
docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -c "
  SELECT table_name FROM information_schema.tables
   WHERE table_schema = 'climate' ORDER BY table_name;
" 2>&1

echo "=========================================================="
echo "MIGRATION DE CLIMA APLICADA COM SUCESSO!"
echo "=========================================================="
