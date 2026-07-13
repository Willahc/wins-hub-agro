#!/usr/bin/env bash
# Script para comparação lógica e física dos bancos de Origem e Restauração
set -Eeuo pipefail

SOURCE_DSN="$1"
RESTORE_DSN="$2"
EVIDENCE_DIR="$3"

echo "=== Iniciando comparação de bancos de dados ==="

# 1. Extração do schema físico + grants (omitindo owner para evitar ruído)
pg_dump -s --no-owner --dbname="$SOURCE_DSN" > "${EVIDENCE_DIR}/source_schema_raw.sql"
pg_dump -s --no-owner --dbname="$RESTORE_DSN" > "${EVIDENCE_DIR}/restore_schema_raw.sql"

# Sanitiza nomes de bancos específicos e remove assinaturas dinâmicas \restrict / \unrestrict
sed -E '/^\\restrict/d; /^\\unrestrict/d; s/fase0_test_source_[0-9_]+/database_placeholder/g' "${EVIDENCE_DIR}/source_schema_raw.sql" > "${EVIDENCE_DIR}/source_schema.sql"
sed -E '/^\\restrict/d; /^\\unrestrict/d; s/fase0_test_restore_[0-9_]+/database_placeholder/g' "${EVIDENCE_DIR}/restore_schema_raw.sql" > "${EVIDENCE_DIR}/restore_schema.sql"

echo "--- Comparando schemas físicos e grants ---"
if diff -u "${EVIDENCE_DIR}/source_schema.sql" "${EVIDENCE_DIR}/restore_schema.sql" > "${EVIDENCE_DIR}/schema_diff.patch"; then
    echo "FÍSICO/GRANTS: MATCH (Os schemas e grants físicos são idênticos)"
else
    echo "FÍSICO/GRANTS: DIVERGÊNCIA ENCONTRADA! Verifique o diff em ${EVIDENCE_DIR}/schema_diff.patch"
    cat "${EVIDENCE_DIR}/schema_diff.patch"
    exit 10
fi

# 2. Comparação lógica de contagens e dados sintéticos
echo "--- Comparando contagens e dados lógicos ---"
run_query() {
    local dsn="$1"
    local sql="$2"
    psql -At -d "$dsn" -c "$sql"
}

# Consultas para comparar
QUERIES=(
  "SELECT count(*) FROM foundation.organizations"
  "SELECT count(*) FROM foundation.app_users"
  "SELECT count(*) FROM foundation.organization_memberships"
  "SELECT count(*) FROM foundation.operational_farms"
  "SELECT count(*) FROM foundation.farm_access"
  "SELECT count(*) FROM foundation.legacy_farm_links"
  "SELECT count(*) FROM foundation.audit_events"
  "SELECT count(*) FROM foundation.units"
  "SELECT count(*) FROM foundation.technical_parameters"
  "SELECT count(*) FROM foundation.formula_definitions"
  "SELECT count(*) FROM foundation.formula_versions"
)

diverged=0
for q in "${QUERIES[@]}"; do
    val_src=$(run_query "$SOURCE_DSN" "$q")
    val_rst=$(run_query "$RESTORE_DSN" "$q")
    if [ "$val_src" != "$val_rst" ]; then
        echo "LÓGICO: Divergência na query [$q]: Origem=$val_src, Restauração=$val_rst"
        diverged=1
    else
        echo "LÓGICO: Match na query [$q] -> Valor: $val_src"
    fi
done

if [ "$diverged" -eq 0 ]; then
    echo "LÓGICO: MATCH (Todas as contagens lógicas conferem perfeitamente)"
else
    echo "LÓGICO: DIVERGÊNCIA ENCONTRADA nas contagens lógicas!"
    exit 11
fi

echo "=== Fim da comparação: MATCH TOTAL ==="
exit 0
