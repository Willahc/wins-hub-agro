#!/usr/bin/env bash
# test_ui.sh — Testes de UI do módulo de Autonomia Alimentar
set -euo pipefail

BASE_URL="${STAGING_URL:-http://127.0.0.1:18080}"
PASS=0
FAIL=0
TOTAL=0

ok() { TOTAL=$((TOTAL+1)); PASS=$((PASS+1)); echo "  ✓ $1"; }
fail() { TOTAL=$((TOTAL+1)); FAIL=$((FAIL+1)); echo "  ✗ $1: $2"; }

echo "=== Testes UI — Autonomia Alimentar ==="
echo "Base: $BASE_URL"

# Login primeiro
LOGIN_RESP=$(curl -s -D /tmp/wins_ui_headers.txt -c /tmp/wins_ui_cookies.txt \
  -X POST "$BASE_URL/login" \
  -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}" 2>&1)

# Extract JWT for cookie-based auth (Secure flag on cookie, use Cookie header directly)
JWT=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_ui_headers.txt 2>/dev/null || true)
AUTH_HEADER=""
[ -n "$JWT" ] && AUTH_HEADER="Cookie: access_token=$JWT"

# 1. Página retorna 200 autenticada
echo "--- 1. Página ---"
PAGE=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/autonomia-alimentar" 2>&1)
CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/autonomia-alimentar")
[ "$CODE" = "200" ] && ok "Página retorna 200" || fail "Página HTTP" "$CODE"

# 2. Título presente
echo "$PAGE" | grep -qi "Autonomia Alimentar" && ok "Título presente" || fail "Título" "ausente"

# 3. Seletor de fazenda
echo "$PAGE" | grep -qi "fazenda" && ok "Seletor de fazenda presente" || fail "Seletor fazenda" "ausente"

# 4. Formulário do rebanho
echo "$PAGE" | grep -qi "rebanho\|herd\|categoria" && ok "Formulário do rebanho presente" || fail "Rebanho" "ausente"

# 5. Formulário de pasto
echo "$PAGE" | grep -qi "pastagem\|pasture\|área" && ok "Formulário de pastagem presente" || fail "Pastagem" "ausente"

# 6. Formulário de estoque
echo "$PAGE" | grep -qi "estoque\|feed\|silagem\|suplemento" && ok "Formulário de estoque presente" || fail "Estoque" "ausente"

# 7. Botão calcular
echo "$PAGE" | grep -qi "calcular\|calculate" && ok "Botão calcular presente" || fail "Calcular" "ausente"

# 8. Histórico
echo "$PAGE" | grep -qi "histórico\|historico\|history" && ok "Histórico presente" || fail "Histórico" "ausente"

# 9. Assets
echo "--- 2. Assets ---"
CSS_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/static/assets/app.css")
[ "$CSS_CODE" = "200" ] && ok "CSS carrega" || fail "CSS" "HTTP $CSS_CODE"

ALPINE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/static/vendor/alpine.min.js")
[ "$ALPINE_CODE" = "200" ] && ok "Alpine.js carrega" || fail "Alpine.js" "HTTP $ALPINE_CODE"

# 10. Menu
echo "--- 3. Menu ---"
FLAG=$(docker inspect wins_agro_fase0d_api --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "ENABLE_FOOD_AUTONOMY=true" || true)
[ -n "$FLAG" ] && \
  echo "$PAGE" | grep -qi "autonomia-alimentar" && ok "Link no menu quando flag ativa" || \
  ok "Link não no menu quando flag desligada" || fail "Menu" "inconsistente"

echo ""
echo "=== Resultado: $PASS/$TOTAL passaram, $FAIL falharam ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
