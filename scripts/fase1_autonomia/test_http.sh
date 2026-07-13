#!/usr/bin/env bash
# test_http.sh — Testes HTTP de integração do módulo de Autonomia Alimentar
set -euo pipefail

BASE_URL="${STAGING_URL:-http://127.0.0.1:18080}"
PASS=0
FAIL=0
TOTAL=0

ok() { TOTAL=$((TOTAL+1)); PASS=$((PASS+1)); echo "  ✓ $1"; }
fail() { TOTAL=$((TOTAL+1)); FAIL=$((FAIL+1)); echo "  ✗ $1: $2"; }

echo "=== Testes HTTP — Autonomia Alimentar ==="
echo "Base: $BASE_URL"

# 1. Rota sem autenticação
echo "--- 1. Autenticação ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/autonomia-alimentar")
[ "$CODE" = "302" ] || [ "$CODE" = "307" ] && ok "Página redireciona para login" || fail "Página sem auth" "HTTP $CODE"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v2/farms/f0000000-0000-4000-8000-000000000001/food-autonomy/simulate")
[ "$CODE" = "401" ] && ok "Simulate sem auth retorna 401" || fail "Simulate sem auth" "HTTP $CODE"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v2/farms/f0000000-0000-4000-8000-000000000001/food-autonomy/scenarios")
[ "$CODE" = "401" ] && ok "List sem auth retorna 401" || fail "List sem auth" "HTTP $CODE"

# 2. Login
echo "--- 2. Login ---"
LOGIN_RESP=$(curl -s -D /tmp/wins_test_headers.txt -c /tmp/wins_test_cookies.txt -w "\n%{http_code}" \
  -X POST "$BASE_URL/login" \
  -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}" 2>&1)
LOGIN_CODE=$(echo "$LOGIN_RESP" | tail -1)
[ "$LOGIN_CODE" = "303" ] || [ "$LOGIN_CODE" = "200" ] && ok "Login bem-sucedido" || fail "Login" "HTTP $LOGIN_CODE"

# Extract JWT from Set-Cookie header (cookie has Secure flag, won't be sent over HTTP)
JWT=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_test_headers.txt 2>/dev/null || true)
AUTH_HEADER=""
[ -n "$JWT" ] && AUTH_HEADER="Cookie: access_token=$JWT"

# 3. Simulação Adequada
echo "--- 3. Simulação ---"
SIM_RESP=$(curl -s -H "$AUTH_HEADER" \
  -X POST "$BASE_URL/api/v2/farms/f0000000-0000-4000-8000-000000000001/food-autonomy/simulate" \
  -H "Content-Type: application/json" \
  -d '{"reference_date":"2026-07-01","target_days":90,"herd":[{"category":"lactating_cows","head_count":20,"average_weight_kg":"450","intake_pct_body_weight":"2.5"}],"feeds":[{"feed_type":"silage","name":"Silo","quantity_natural_kg":"100000","dry_matter_pct":"35","utilization_pct":"100"}]}')
echo "$SIM_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['daily_demand_dm_kg']=='225.00'" 2>/dev/null \
  && ok "Demanda = 225.00 kg MS/dia" || fail "Demanda" "valor incorreto"
echo "$SIM_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['formula_version']=='food_autonomy.v1'" 2>/dev/null \
  && ok "Versão da fórmula = food_autonomy.v1" || fail "Versão" "valor incorreto"

# 4. Headers de cache
echo "--- 4. Headers ---"
HEADERS=$(curl -s -D - -o /dev/null -H "$AUTH_HEADER" \
  "$BASE_URL/api/v2/farms/f0000000-0000-4000-8000-000000000001/food-autonomy/scenarios" 2>&1)
echo "$HEADERS" | grep -qi "no-store" && ok "Cache-Control: no-store" || fail "Cache" "ausente"

# 5. Feature flag (only in staging environment)
echo "--- 5. Feature Flag ---"
FLAG=$(docker inspect wins_agro_fase0d_api --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "ENABLE_FOOD_AUTONOMY=true" || true)
[ -n "$FLAG" ] && ok "Feature flag enabled in staging" || fail "Flag" "not set in container"

# 6. Decimal precision
echo "--- 6. Precisão Decimal ---"
echo "$SIM_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for k in ['daily_demand_dm_kg','autonomy_days','balance_dm_kg']:
    v=d[k]
    assert '.' in v, f'{k} sem casa decimal: {v}'
    assert 'e' not in v.lower(), f'{k} em notação científica: {v}'
" 2>/dev/null && ok "Decimais serializados como strings com ponto" || fail "Decimal" "formato inválido"

# 7. Ausência de IDs internos
echo "--- 7. Segurança ---"
echo "$SIM_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
for key in ['id','organization_id','farm_id','created_by']:
    assert key not in d, f'Campo interno {key} exposto'
" 2>/dev/null && ok "Nenhum ID interno na resposta" || fail "IDs internos" "expostos"

echo ""
echo "=== Resultado: $PASS/$TOTAL passaram, $FAIL falharam ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
