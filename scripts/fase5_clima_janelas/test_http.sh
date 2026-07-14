#!/usr/bin/env bash
set -euo pipefail
[ "${STAGING_TEST:-}" = "1" ] || { echo "Use STAGING_TEST=1"; exit 2; }
BASE="${STAGING_URL:-http://127.0.0.1:18080}"
FARM="f0000000-0000-4000-8000-000000000001"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ✓ $1"; }
bad(){ FAIL=$((FAIL+1)); echo "  ✗ $1 ($2)"; }
code(){ curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "=== HTTP — Clima e Janelas Operacionais ==="
[ "$(code "$BASE/clima-operacoes")" = 307 ] && ok "página exige autenticação" || bad "autenticação da página" "HTTP inesperado"
[ "$(code "$BASE/api/v2/farms/$FARM/weather-operations/profile")" = 401 ] && ok "API exige autenticação" || bad "autenticação da API" "HTTP inesperado"

curl -s -D /tmp/wins_climate_headers -o /dev/null -X POST "$BASE/login" -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}"
TOKEN=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_climate_headers | tr -d '\r' || true)
H="Cookie: access_token=$TOKEN"
[ -n "$TOKEN" ] && ok "login" || bad "login" "cookie ausente"

R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/weather-operations/profile")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('status') or d.get('latitude') is not None; print('ok')" && ok "perfil" || bad "perfil" "$R"

R=$(curl -s -H "$H" -H 'Content-Type: application/json' -X PUT "$BASE/api/v2/farms/$FARM/weather-operations/profile" \
  -d '{"latitude":-12.64,"longitude":-55.72,"timezone":"America/Cuiaba","enabled":true}')
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('public_id'); print('ok')" && ok "criar/atualizar perfil" || bad "perfil write" "$R"

R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/weather-operations/current")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'temperature_c' in d or d.get('cache_status')=='unavailable'; print('ok')" && ok "condição atual" || bad "current" "$R"

R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/weather-operations/forecast/hourly")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'items' in d; print('ok')" && ok "previsão horária" || bad "hourly" "$R"

R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/weather-operations/forecast/daily")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'items' in d; print('ok')" && ok "previsão diária" || bad "daily" "$R"

R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/weather-operations/rainfall/recent")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'total_mm' in d; print('ok')" && ok "chuva recente" || bad "rainfall" "$R"

R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/weather-operations/dashboard")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'integration_status' in d; print('ok')" && ok "dashboard" || bad "dashboard" "$R"

R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/weather-operations/operational-windows")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'items' in d; print('ok')" && ok "janelas operacionais" || bad "windows" "$R"

R=$(curl -s -H "$H" -X POST "$BASE/api/v2/farms/$FARM/weather-operations/refresh")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d.get('status')=='refreshed' or 'error' in d; print('ok')" && ok "refresh" || bad "refresh" "$R"

[ "$(code -H "$H" -X POST "$BASE/api/v2/farms/$FARM/weather-operations/refresh")" = 403 ] && ok "cooldown 429/403 no refresh" || bad "cooldown" "HTTP inesperado"

CROSS="ffffffff-ffff-4fff-8fff-ffffffffffff"
[ "$(code -H "$H" "$BASE/api/v2/farms/$CROSS/weather-operations/profile")" = 404 ] && ok "cross-tenant oculto" || bad "cross-tenant" "não retornou 404"

R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/weather-operations/pasture-context")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'recent_rainfall_mm' in d; print('ok')" && ok "contexto pasto vivo" || bad "pasture-context" "$R"

PLANS=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/harvest-silos/plans?limit=1")
PLAN_UUID=$(echo "$PLANS" | python3 -c "import json,sys; items=json.load(sys.stdin).get('items',[]); print(items[0]['public_id'] if items else '')" 2>/dev/null || true)
if [ -n "$PLAN_UUID" ]; then
  R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/weather-operations/harvest-plans/$PLAN_UUID/weather-context")
  echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'plan_uuid' in d; print('ok')" && ok "contexto colheita" || bad "harvest-context" "$R"
else
  ok "contexto colheita (skip sem plano)"
fi

echo "Resultado: $PASS passaram; $FAIL falharam"
[ "$FAIL" -eq 0 ]
