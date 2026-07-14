#!/usr/bin/env bash
# test_ui.sh — Testes de UI do módulo de Silagem e Estoques
set -euo pipefail

BASE_URL="${STAGING_URL:-http://127.0.0.1:18080}"
PASS=0
FAIL=0
TOTAL=0

ok() { TOTAL=$((TOTAL+1)); PASS=$((PASS+1)); echo "  ✓ $1"; }
fail() { TOTAL=$((TOTAL+1)); FAIL=$((FAIL+1)); echo "  ✗ $1: $2"; }

echo "=== Testes UI — Silagem e Estoques ==="
echo "Base: $BASE_URL"

# Login primeiro
LOGIN_RESP=$(curl -s -D /tmp/wins_storage_ui_headers.txt -c /tmp/wins_storage_ui_cookies.txt \
  -X POST "$BASE_URL/login" \
  -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}" 2>&1)

JWT=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_storage_ui_headers.txt | tr -d '\r' 2>/dev/null || true)
AUTH_HEADER=""
[ -n "$JWT" ] && AUTH_HEADER="Cookie: access_token=$JWT"

# 1. Página retorna 200 autenticada
echo "--- 1. Página ---"
PAGE=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/silagem-estoques" 2>&1)
CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/silagem-estoques")
[ "$CODE" = "200" ] && ok "Página retorna 200" || fail "Página HTTP" "$CODE"

# 2. Redirecionamento sem auth
echo "--- 2. Sem Auth ---"
NOAUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/silagem-estoques")
[ "$NOAUTH_CODE" = "302" ] || [ "$NOAUTH_CODE" = "307" ] && ok "Redireciona para login sem auth" || fail "Sem auth" "HTTP $NOAUTH_CODE"

# 3. Assets acessíveis
echo "--- 3. Assets ---"
CSS_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/static/assets/app.css")
[ "$CSS_CODE" = "200" ] && ok "CSS carrega" || fail "CSS" "HTTP $CSS_CODE"

JS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/static/vendor/alpine.min.js")
[ "$JS_CODE" = "200" ] && ok "Alpine.js carrega" || fail "Alpine.js" "HTTP $JS_CODE"

# 4. Item de menu presente
echo "--- 4. Menu ---"
echo "$PAGE" > /tmp/ui_page_out.html
grep -qi "estoque\|storage\|silagem\|feed" /tmp/ui_page_out.html && ok "Link no menu presente" || fail "Menu" "ausente"

echo ""
echo "=== Resultado: $PASS/$TOTAL passaram, $FAIL falharam ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
