#!/usr/bin/env bash
# Harness orquestrador da homologação restaurável Fase 0C
# Autor: Antigravity AI
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TS="$(date +%Y%m%d_%H%M%S)"
EVIDENCE_DIR="/tmp/wins_agro_fase0c_${TS}"
mkdir -p "$EVIDENCE_DIR"

# 1. Definição de Nomes dos Objetos Temporários
NETWORK_NAME="wins_agro_fase0c_net_${TS}_$$"
SOURCE_CONTAINER="wins_agro_fase0c_source_${TS}_$$"
RESTORE_CONTAINER="wins_agro_fase0c_restore_${TS}_$$"
SOURCE_VOLUME="wins_agro_fase0c_source_data_${TS}_$$"
RESTORE_VOLUME="wins_agro_fase0c_restore_data_${TS}_$$"

DB_USER="fase0_test"
DB_NAME="fase0_test"
DB_PASS="fase0_test_password_synthetic"
IMAGE="postgres:16-alpine"

echo "==========================================================="
echo "INICIANDO HARNESS DE HOMOLOGAÇÃO FASE 0C: $TS"
echo "==========================================================="
echo "Container de Origem:   $SOURCE_CONTAINER"
echo "Container Restaurado:  $RESTORE_CONTAINER"
echo "Rede Temporária:       $NETWORK_NAME"
echo "Pasta de Evidências:   $EVIDENCE_DIR"
echo "==========================================================="

# 2. Configuração de Cleanup Automático em caso de erro ou saída
cleanup() {
  echo "--- Executando trap de cleanup ---"
  bash "$ROOT/scripts/fase0c/cleanup_homologation.sh" \
    "$SOURCE_CONTAINER" \
    "$RESTORE_CONTAINER" \
    "$NETWORK_NAME" \
    "$SOURCE_VOLUME" \
    "$RESTORE_VOLUME"
}
trap cleanup EXIT INT TERM

# 3. Criação da Rede Exclusiva
docker network create "$NETWORK_NAME" >/dev/null

# 4. Inicialização do Banco de Origem
docker volume create "$SOURCE_VOLUME" >/dev/null
docker run -d \
  --name "$SOURCE_CONTAINER" \
  --network "$NETWORK_NAME" \
  -v "$SOURCE_VOLUME":/var/lib/postgresql/data \
  --memory 768m \
  --cpus 1 \
  -e POSTGRES_USER="$DB_USER" \
  -e POSTGRES_PASSWORD="$DB_PASS" \
  -e POSTGRES_DB="$DB_NAME" \
  "$IMAGE" >/dev/null

# Aguarda inicialização
echo "Aguardando inicialização do banco de origem..."
ready=0
for _attempt in $(seq 1 30); do
  if docker exec "$SOURCE_CONTAINER" psql -X -U "$DB_USER" -d "$DB_NAME" -Atc 'SELECT 1' >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "ERRO: O banco de origem não inicializou a tempo." >&2
  docker logs --tail=100 "$SOURCE_CONTAINER"
  exit 1
fi

SOURCE_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$SOURCE_CONTAINER")"
echo "Banco de origem pronto no IP: $SOURCE_IP"

# 5. Aplicação dos Scripts de Inicialização e Fundação
echo "Aplicando roles e legado sintético..."
PGPASSWORD="$DB_PASS" psql -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/scripts/fase0c/seed_synthetic_legacy.sql"

echo "Aplicando scripts da fundação..."
PGPASSWORD="$DB_PASS" psql -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/scripts/fase0/001_foundation_schema.sql"

# Concede USAGE e CREATE ao migrator no schema foundation da origem
PGPASSWORD="$DB_PASS" psql -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" \
  -c "GRANT USAGE, CREATE ON SCHEMA foundation TO wins_agro_migrator;"

PGPASSWORD="$DB_PASS" psql -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/scripts/fase0/002_reference_units.sql"
PGPASSWORD="$DB_PASS" psql -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/scripts/fase0/020_legacy_mapping_schema.sql"
PGPASSWORD="$DB_PASS" psql -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/scripts/fase0/030_legacy_bootstrap_idempotent.sql"
PGPASSWORD="$DB_PASS" psql -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/scripts/fase0/040_legacy_bootstrap_rollback.sql"

echo "Aplicando grants..."
PGPASSWORD="$DB_PASS" psql -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" \
  -v foundation_app_role=wins_agro_app -v foundation_readonly_role=wins_agro_readonly \
  -f "$ROOT/scripts/fase0/090_foundation_grants.sql"

# 6. Testes do CLI Python Ponta a Ponta
PYTHON_BIN="/root/.venv-wins-tools/bin/python"
SOURCE_DSN="postgresql://$DB_USER:$DB_PASS@$SOURCE_IP:5432/$DB_NAME"

echo "--- CLI: Teste 1 - Dry-run de mapping válido (1001) ---"
$PYTHON_BIN "$ROOT/scripts/fase0/bootstrap_legacy.py" \
  --input "$ROOT/scripts/fase0c/mapping_1001.json" \
  --dsn "$SOURCE_DSN"

echo "--- CLI: Teste 2 - Apply sem confirmação (espera rejeição) ---"
if $PYTHON_BIN "$ROOT/scripts/fase0/bootstrap_legacy.py" \
  --input "$ROOT/scripts/fase0c/mapping_1001.json" \
  --dsn "$SOURCE_DSN" \
  --apply >/dev/null 2>&1; then
    echo "ERRO: O CLI deveria ter rejeitado o apply sem confirmação explícita!" >&2
    exit 1
else
    echo "Sucesso: CLI rejeitou o apply sem confirmação explícita."
fi

echo "--- CLI: Teste 3 - Apply com confirmação explícita (1001) ---"
$PYTHON_BIN "$ROOT/scripts/fase0/bootstrap_legacy.py" \
  --input "$ROOT/scripts/fase0c/mapping_1001.json" \
  --dsn "$SOURCE_DSN" \
  --apply \
  --confirm APPLY_EXPLICIT_LEGACY_MAPPING

echo "--- CLI: Teste 4 - Re-apply idempotente (1001) ---"
reapply_out=$($PYTHON_BIN "$ROOT/scripts/fase0/bootstrap_legacy.py" \
  --input "$ROOT/scripts/fase0c/mapping_1001.json" \
  --dsn "$SOURCE_DSN" \
  --apply \
  --confirm APPLY_EXPLICIT_LEGACY_MAPPING)
echo "Retorno do Re-apply: $reapply_out"

# 7. Teste de Outros Mappings e Conflitos
echo "--- CLI: Teste 5 - Apply com confirmação explícita (2001) ---"
$PYTHON_BIN "$ROOT/scripts/fase0/bootstrap_legacy.py" \
  --input "$ROOT/scripts/fase0c/mapping_2001.json" \
  --dsn "$SOURCE_DSN" \
  --apply \
  --confirm APPLY_EXPLICIT_LEGACY_MAPPING

echo "--- CLI: Teste 6 - Conflito de organização para mesmo cliente (1001) ---"
if $PYTHON_BIN "$ROOT/scripts/fase0/bootstrap_legacy.py" \
  --input "$ROOT/scripts/fase0c/mapping_conflict_org.json" \
  --dsn "$SOURCE_DSN" \
  --apply \
  --confirm APPLY_EXPLICIT_LEGACY_MAPPING >/dev/null 2>&1; then
    echo "ERRO: O CLI deveria ter rejeitado o mapping conflituoso!" >&2
    exit 1
else
    echo "Sucesso: CLI rejeitou o mapping conflituoso com rollback automático."
fi

echo "--- CLI: Teste 7 - Rejeição de origem inválida ---"
set +e
invalid_out=$($PYTHON_BIN "$ROOT/scripts/fase0/bootstrap_legacy.py" \
  --input "$ROOT/scripts/fase0c/mapping_invalid_source.json" \
  --dsn "$SOURCE_DSN" 2>&1)
exit_code=$?
set -e
if [[ $exit_code -ne 2 ]]; then
    echo "ERRO: O CLI deveria ter falhado com código 2 para origem inválida, mas saiu com $exit_code" >&2
    exit 1
else
    echo "Sucesso: CLI detectou a origem inválida com saída: $invalid_out"
fi

# 8. Validações da Origem (validate_roles e validate_foundation)
echo "Executando validações SQL de papéis e integridade na Origem..."
PGPASSWORD="$DB_PASS" psql -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/scripts/fase0c/validate_roles.sql"
PGPASSWORD="$DB_PASS" psql -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/scripts/fase0c/validate_foundation.sql"

# 9. Backup Lógico (pg_dump)
BACKUP_PATH="${EVIDENCE_DIR}/wins_agro_fase0c_backup.dump"
echo "Executando pg_dump..."
PGPASSWORD="$DB_PASS" pg_dump -h "$SOURCE_IP" -U "$DB_USER" -d "$DB_NAME" \
  --format=custom --no-owner --no-acl > "$BACKUP_PATH"

BACKUP_SIZE=$(stat -c%s "$BACKUP_PATH")
BACKUP_SHA=$(sha256sum "$BACKUP_PATH" | awk '{print $1}')
echo "Backup criado: $BACKUP_PATH"
echo "Tamanho: $BACKUP_SIZE bytes"
echo "SHA256:  $BACKUP_SHA"

# 10. Destruição do Banco de Origem
echo "Destruindo container de origem..."
docker rm -f "$SOURCE_CONTAINER" >/dev/null
docker volume rm "$SOURCE_VOLUME" >/dev/null
SOURCE_CONTAINER="" # Evita remoção duplicada no trap
SOURCE_VOLUME=""

# 11. Inicialização do Banco de Restauração
docker volume create "$RESTORE_VOLUME" >/dev/null
docker run -d \
  --name "$RESTORE_CONTAINER" \
  --network "$NETWORK_NAME" \
  -v "$RESTORE_VOLUME":/var/lib/postgresql/data \
  --memory 768m \
  --cpus 1 \
  -e POSTGRES_USER="$DB_USER" \
  -e POSTGRES_PASSWORD="$DB_PASS" \
  -e POSTGRES_DB="$DB_NAME" \
  "$IMAGE" >/dev/null

# Aguarda inicialização do de restauração
echo "Aguardando inicialização do banco de restauração..."
ready=0
for _attempt in $(seq 1 30); do
  if docker exec "$RESTORE_CONTAINER" psql -X -U "$DB_USER" -d "$DB_NAME" -Atc 'SELECT 1' >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  echo "ERRO: O banco de restauração não inicializou." >&2
  exit 1
fi

RESTORE_IP="$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$RESTORE_CONTAINER")"
echo "Banco de restauração pronto no IP: $RESTORE_IP"

# 12. Procedimento de recriação de Roles (necessário antes de restaurar)
echo "Recriando roles globais no banco de restauração..."
PGPASSWORD="$DB_PASS" psql -h "$RESTORE_IP" -U "$DB_USER" -d "$DB_NAME" <<'SQL'
CREATE ROLE wins_agro_migrator WITH LOGIN PASSWORD 'migrator_synthetic_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE wins_agro_app WITH LOGIN PASSWORD 'app_synthetic_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE wins_agro_readonly WITH LOGIN PASSWORD 'readonly_synthetic_pass' NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT wins_agro_migrator, wins_agro_app, wins_agro_readonly TO CURRENT_USER;
SQL

# 13. Restauração (pg_restore)
echo "Executando pg_restore..."
PGPASSWORD="$DB_PASS" pg_restore -h "$RESTORE_IP" -U "$DB_USER" -d "$DB_NAME" \
  --no-owner --no-acl --exit-on-error "$BACKUP_PATH"

# Re-aplica os grants (visto que --no-acl foi usado no dump/restore)
echo "Re-aplicando grants pós-restore..."
PGPASSWORD="$DB_PASS" psql -h "$RESTORE_IP" -U "$DB_USER" -d "$DB_NAME" \
  -v foundation_app_role=wins_agro_app -v foundation_readonly_role=wins_agro_readonly \
  -f "$ROOT/scripts/fase0/090_foundation_grants.sql"

# Concede USAGE e CREATE ao migrator no schema foundation da restauração
PGPASSWORD="$DB_PASS" psql -h "$RESTORE_IP" -U "$DB_USER" -d "$DB_NAME" <<'SQL'
GRANT USAGE ON SCHEMA fazenda TO wins_agro_migrator;
GRANT SELECT, REFERENCES ON TABLE fazenda.cliente TO wins_agro_migrator;
GRANT USAGE, CREATE ON SCHEMA foundation TO wins_agro_migrator;
SQL

# 14. Validação do Banco de Restauração
echo "Validando banco de restauração..."
PGPASSWORD="$DB_PASS" psql -h "$RESTORE_IP" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/scripts/fase0c/validate_restore.sql"
PGPASSWORD="$DB_PASS" psql -h "$RESTORE_IP" -U "$DB_USER" -d "$DB_NAME" -f "$ROOT/scripts/fase0c/validate_roles.sql"

# 15. Comparação Origem x Restauração
echo "Executando comparação lógica e física dos bancos..."
RESTORE_DSN="postgresql://$DB_USER:$DB_PASS@$RESTORE_IP:5432/$DB_NAME"
bash "$ROOT/scripts/fase0c/compare_databases.sh" "$SOURCE_DSN" "$RESTORE_DSN" "$EVIDENCE_DIR"

echo "==========================================================="
echo "HOMOLOGAÇÃO FASE 0C CONCLUÍDA COM SUCESSO!"
echo "Evidências salvas em: $EVIDENCE_DIR"
echo "==========================================================="
