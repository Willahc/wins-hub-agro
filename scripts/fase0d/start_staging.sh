#!/usr/bin/env bash
# start_staging.sh — Inicia o ambiente de staging persistente para a Fase 0D
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="/root/.config/wins_agro/fase0d/staging.env"
COMPOSE_FILE="$ROOT/scripts/fase0d/docker-compose.staging.yml"
PROJECT_NAME="wins_agro_fase0d"

echo "=== Iniciando Staging Persistente (Fase 0D) ==="

# 1. Validações Iniciais
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERRO: Arquivo de configuração $ENV_FILE não encontrado." >&2
    exit 1
fi

# Valida se a porta 18080 está livre
if lsof -Pi :18080 -sTCP:LISTEN -t >/dev/null ; then
    echo "Aviso: A porta 18080 já está respondendo. Pode ser que o staging já esteja ativo." >&2
fi

# 2. Build local e startup
echo "Construindo imagem de staging local..."
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --pull=false

echo "Subindo containers do Staging..."
docker compose -p "$PROJECT_NAME" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d

# 3. Aguarda o Banco de Dados estar Saudável
echo "Aguardando inicialização do PostgreSQL de Staging..."
ready=0
for _attempt in $(seq 1 30); do
  if docker exec wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -c "SELECT 1" >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done

if [[ "$ready" -ne 1 ]]; then
  echo "ERRO: O banco de staging não inicializou a tempo." >&2
  exit 1
fi
echo "PostgreSQL de Staging pronto!"

# 4. Criação do Schema Legado Sintético e Roles Globais
echo "Limpar schemas anteriores e provisionar roles/schema legado..."
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging <<'SQL'
-- Drop schemas para garantir re-criação limpa e idempotente
DROP SCHEMA IF EXISTS foundation CASCADE;
DROP SCHEMA IF EXISTS fazenda CASCADE;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'wins_agro_migrator') THEN
        CREATE ROLE wins_agro_migrator WITH LOGIN PASSWORD 'migrator_synthetic_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'wins_agro_app') THEN
        CREATE ROLE wins_agro_app WITH LOGIN PASSWORD 'app_synthetic_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'wins_agro_readonly') THEN
        CREATE ROLE wins_agro_readonly WITH LOGIN PASSWORD 'readonly_synthetic_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
    END IF;
END
$$;
GRANT wins_agro_migrator, wins_agro_app, wins_agro_readonly TO CURRENT_USER;

-- Pre-cria o schema legado para que os DDLs da fundação possam adicionar a FK
CREATE SCHEMA IF NOT EXISTS fazenda;
CREATE TABLE IF NOT EXISTS fazenda.cliente (
  id integer PRIMARY KEY,
  nome text NOT NULL
);
GRANT USAGE ON SCHEMA fazenda TO wins_agro_migrator;
GRANT SELECT, REFERENCES ON TABLE fazenda.cliente TO wins_agro_migrator;
SQL

echo "Aplicando DDLs da fundação..."
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -f - < "$ROOT/scripts/fase0/001_foundation_schema.sql"
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -f - < "$ROOT/scripts/fase0/002_reference_units.sql"
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -f - < "$ROOT/scripts/fase0/020_legacy_mapping_schema.sql"
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -f - < "$ROOT/scripts/fase0/030_legacy_bootstrap_idempotent.sql"
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -f - < "$ROOT/scripts/fase0/040_legacy_bootstrap_rollback.sql"

echo "Aplicando grants de segurança..."
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging \
  -v foundation_app_role=wins_agro_app -v foundation_readonly_role=wins_agro_readonly \
  -f - < "$ROOT/scripts/fase0/090_foundation_grants.sql"

docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging <<'SQL'
GRANT USAGE, CREATE ON SCHEMA foundation TO wins_agro_migrator;
SQL

# 5. Carga de Seed Sintético
echo "Populando base de staging com dados sintéticos..."
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -f - < "$ROOT/scripts/fase0d/seed_staging.sql"

# 6. Aguarda a API estar Saudável
echo "Aguardando inicialização da API de Staging..."
api_ready=0
for _attempt in $(seq 1 30); do
  # Usa curl local na porta mapeada 18080 do host
  if curl -s -f http://127.0.0.1:18080/healthz >/dev/null 2>&1; then
    api_ready=1
    break
  fi
  sleep 1
done

if [[ "$api_ready" -ne 1 ]]; then
  echo "ERRO: A API de staging não respondeu na porta 18080." >&2
  exit 1
fi

echo "=========================================================="
echo "STAGING INICIALIZADO COM SUCESSO!"
echo "API de Staging rodando em: http://127.0.0.1:18080"
echo "=========================================================="
