#!/usr/bin/env bash
# run_staging_rehearsal.sh — Executa o ensaio de inventário no ambiente de staging sintético
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "=== Iniciando Ensaio no Staging Sintético ==="

# 1. Inicia o Staging se não estiver ativo
bash "$ROOT/scripts/fase0d/start_staging.sh"

# 2. Registra contagens antes de rodar a ferramenta
echo "Obtendo contagens antes da execução..."
before_cnt=$(docker exec wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -t -A -c "
  SELECT
    (SELECT count(*) FROM fazenda.cliente) +
    (SELECT count(*) FROM foundation.app_users) +
    (SELECT count(*) FROM foundation.organizations) +
    (SELECT count(*) FROM foundation.organization_memberships) +
    (SELECT count(*) FROM foundation.operational_farms) +
    (SELECT count(*) FROM foundation.farm_access) +
    (SELECT count(*) FROM foundation.audit_events);
")

# 3. Executa a ferramenta dentro do container de staging
echo "Copiando e executando a ferramenta de inventário no container de staging..."
docker exec wins_agro_fase0d_api mkdir -p /tmp/fase0e1/outputs
docker cp "$ROOT/scripts/fase0e1/inventory_readonly.py" wins_agro_fase0d_api:/tmp/fase0e1/inventory_readonly.py
docker exec wins_agro_fase0d_api python /tmp/fase0e1/inventory_readonly.py --staging --output-dir /tmp/fase0e1/outputs

# 4. Copia os resultados gerados de volta para o host
timestamp="$(date +%Y%m%d_%H%M%S)"
target_dir="/root/.config/wins_agro/fase0e1/${timestamp}_staging"
mkdir -p "$target_dir"
docker cp wins_agro_fase0d_api:/tmp/fase0e1/outputs/. "$target_dir"

# Limpa o container de staging
docker exec wins_agro_fase0d_api rm -rf /tmp/fase0e1

# Ajusta permissões no host
chmod 700 "$target_dir"
chmod 600 "$target_dir"/*

echo "Resultados gerados no host em: $target_dir"

# 5. Registra contagens depois de rodar a ferramenta
echo "Obtendo contagens pós-execução..."
after_cnt=$(docker exec wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -t -A -c "
  SELECT
    (SELECT count(*) FROM fazenda.cliente) +
    (SELECT count(*) FROM foundation.app_users) +
    (SELECT count(*) FROM foundation.organizations) +
    (SELECT count(*) FROM foundation.organization_memberships) +
    (SELECT count(*) FROM foundation.operational_farms) +
    (SELECT count(*) FROM foundation.farm_access) +
    (SELECT count(*) FROM foundation.audit_events);
")

# 6. Validação de Ausência de Escrita
if [[ "$before_cnt" -eq "$after_cnt" ]]; then
    echo "=========================================================="
    echo "ENSAIO DE STAGING BEM-SUCEDIDO!"
    echo "Garantia de escrita nula confirmada (contagens batem: $before_cnt)."
    echo "=========================================================="
else
    echo "ERRO: Houve modificação no banco de staging durante a execução!" >&2
    echo "Antes: $before_cnt, Depois: $after_cnt" >&2
    exit 1
fi
