#!/usr/bin/env bash
# test_ui.sh — Testes de UI do módulo de Pasto Vivo
set -euo pipefail

BASE_URL="${STAGING_URL:-http://127.0.0.1:18080}"
PASS=0
FAIL=0
TOTAL=0

ok() { TOTAL=$((TOTAL+1)); PASS=$((PASS+1)); echo "  ✓ $1"; }
fail() { TOTAL=$((TOTAL+1)); FAIL=$((FAIL+1)); echo "  ✗ $1: $2"; }

echo "=== Testes UI — Pasto Vivo ==="
echo "Base: $BASE_URL"

# Login primeiro
LOGIN_RESP=$(curl -s -D /tmp/wins_pasture_ui_headers.txt -c /tmp/wins_pasture_ui_cookies.txt \
  -X POST "$BASE_URL/login" \
  -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}" 2>&1)

JWT=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_pasture_ui_headers.txt 2>/dev/null || true)
AUTH_HEADER=""
[ -n "$JWT" ] && AUTH_HEADER="Cookie: access_token=$JWT"

# 1. Página retorna 200 autenticada
echo "--- 1. Página ---"
PAGE=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/pasto-vivo" 2>&1)
CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/pasto-vivo")
[ "$CODE" = "200" ] && ok "Página retorna 200" || fail "Página HTTP" "$CODE"

# 2. Título presente
echo "$PAGE" | grep -qi "Pasto Vivo" && ok "Título presente" || fail "Título" "ausente"

# 3. Seletor de fazenda
echo "$PAGE" | grep -qiE 'fazenda|farm' && ok "Seletor de fazenda presente" || fail "Seletor fazenda" "ausente"

# 4. KPIs
echo "$PAGE" | grep -qiE 'kpi|resumo|indicador|hectare|área|MS' && ok "KPIs presentes" || fail "KPIs" "ausentes"

# 5. Lista de piquetes
echo "$PAGE" | grep -qiE 'piquete|paddock' && ok "Lista de piquetes presente" || fail "Piquetes" "ausente"

# 6. Formulário de criação/edição
echo "$PAGE" | grep -qiE 'form|criar|editar|salvar' && ok "Formulário de piquete presente" || fail "Formulário" "ausente"

# 7. Botão de medição
echo "$PAGE" | grep -qiE 'medição|medir|measurement|altura' && ok "Formulário de medição presente" || fail "Medição" "ausente"

# 8. Botão de pastejo
echo "$PAGE" | grep -qiE 'pastejo|grazing|entrar|sair' && ok "Botão de pastejo presente" || fail "Pastejo" "ausente"

# 9. Status do piquete
echo "$PAGE" | grep -qiE 'status|pronto|pastejando|descanso|atenção' && ok "Indicadores de status presentes" || fail "Status" "ausente"

# 10. Assets
echo "--- 2. Assets ---"
CSS_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" "$BASE_URL/static/assets/app.css")
[ "$CSS_CODE" = "200" ] && ok "CSS carrega" || fail "CSS" "HTTP $CSS_CODE"

ALPINE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/static/vendor/alpine.min.js")
[ "$ALPINE_CODE" = "200" ] && ok "Alpine.js carrega" || fail "Alpine.js" "HTTP $ALPINE_CODE"

# 11. Menu
echo "--- 3. Menu ---"
FLAG=$(docker inspect wins_agro_fase0d_api --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "ENABLE_PASTURE_LIVE=true" || true)
[ -n "$FLAG" ] && \
  echo "$PAGE" | grep -qi "pasto-vivo" && ok "Link no menu quando flag ativa" || \
  ok "Link não no menu quando flag desligada" || fail "Menu" "inconsistente"

echo ""
echo "=== Resultado: $PASS/$TOTAL passaram, $FAIL falharam ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
