#!/usr/bin/env bash
set -euo pipefail
[ "${STAGING_TEST:-}" = "1" ] || { echo "Use STAGING_TEST=1"; exit 2; }
BASE="${STAGING_URL:-http://127.0.0.1:18080}"; PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ✓ $1"; }; bad(){ FAIL=$((FAIL+1)); echo "  ✗ $1"; }
curl -s -D /tmp/wins_harvest_ui_headers -o /dev/null -X POST "$BASE/login" -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}"
TOKEN=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_harvest_ui_headers | tr -d '\r' || true); H="Cookie: access_token=$TOKEN"
PAGE=$(curl -s -H "$H" "$BASE/colheita-silos")
for term in "Colheita e Silos" "Planos de colheita" "Novo plano" "Áreas" "Silos e alocação" "Concluir e criar lotes" "Lotes criados"; do echo "$PAGE" | grep -q "$term" && ok "$term" || bad "$term"; done
for asset in /static/assets/app.css /static/vendor/alpine.min.js; do [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE$asset")" = 200 ] && ok "$asset" || bad "$asset"; done
echo "Resultado: $PASS passaram; $FAIL falharam"; [ "$FAIL" -eq 0 ]
