#!/usr/bin/env bash
# test_authorization.sh — Valida políticas de autorização dinâmicas e concorrência
set -euo pipefail

API_URL="http://127.0.0.1:18080/api/v2/farms"

echo "=== Iniciando Testes de Autorização Dinâmica (Fase 0D) ==="

generate_token() {
  docker exec wins_agro_fase0d_api python -c "import jwt; print(jwt.encode({'sub': '$1'}, 'staging_jwt_secret_synthetic_64_characters_long_for_security_reasons', algorithm='HS256'))"
}

T_TECH_ALFA=$(generate_token "usr_tech_alfa")

# 1. Valida acesso inicial do Technician Alfa (vê 1 fazenda)
echo -n "Teste 1: Acesso inicial do Technician Alfa (espera 1 fazenda)... "
body=$(curl -s --cookie "access_token=$T_TECH_ALFA" "$API_URL")
count=$(echo "$body" | docker exec -i wins_agro_fase0d_api python -c "import sys, json; print(len(json.load(sys.stdin)['items']))")
if [[ "$count" -eq 1 ]]; then echo "OK"; else echo "FALHA (count=$count)"; exit 1; fi

# 2. Revogação de farm access dinamicamente no banco
echo "Modificando banco: revogando farm access..."
docker exec wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -c "UPDATE foundation.farm_access SET status = 'revoked', revoked_at = now() WHERE id = 1;" >/dev/null

# 3. Valida que Technician Alfa agora vê 0 fazendas
echo -n "Teste 2: Acesso após revogação de farm_access (espera 0 fazendas)... "
body=$(curl -s --cookie "access_token=$T_TECH_ALFA" "$API_URL")
count=$(echo "$body" | docker exec -i wins_agro_fase0d_api python -c "import sys, json; print(len(json.load(sys.stdin)['items']))")
if [[ "$count" -eq 0 ]]; then echo "OK"; else echo "FALHA (count=$count)"; exit 1; fi

# 4. Restaura farm access
echo "Modificando banco: restaurando farm access..."
docker exec wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -c "UPDATE foundation.farm_access SET status = 'active', revoked_at = NULL WHERE id = 1;" >/dev/null

# 5. Revogação de membership dinamicamente
echo "Modificando banco: revogando membership..."
docker exec wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -c "UPDATE foundation.organization_memberships SET status = 'revoked', revoked_at = now() WHERE id = 3;" >/dev/null

# 6. Valida que Technician Alfa agora recebe HTTP 403 (revogado)
echo -n "Teste 3: Acesso após revogação de membership (espera 403)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_TECH_ALFA" "$API_URL")
if [[ "$code" -eq 403 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 7. Restaura membership
echo "Modificando banco: restaurando membership..."
docker exec wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging -c "UPDATE foundation.organization_memberships SET status = 'active', revoked_at = NULL WHERE id = 3;" >/dev/null

# 8. Valida que Technician Alfa recupera acesso
echo -n "Teste 4: Acesso após restaurar membership (espera 200, 1 fazenda)... "
body=$(curl -s --cookie "access_token=$T_TECH_ALFA" "$API_URL")
count=$(echo "$body" | docker exec -i wins_agro_fase0d_api python -c "import sys, json; print(len(json.load(sys.stdin)['items']))")
if [[ "$count" -eq 1 ]]; then echo "OK"; else echo "FALHA (count=$count)"; exit 1; fi

echo "=========================================================="
echo "TODOS OS TESTES DE AUTORIZAÇÃO DINÂMICA PASSARAM!"
echo "=========================================================="
