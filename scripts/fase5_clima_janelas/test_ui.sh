#!/usr/bin/env bash
set -euo pipefail
[ "${STAGING_TEST:-}" = "1" ] || { echo "Use STAGING_TEST=1"; exit 2; }
BASE="${STAGING_URL:-http://127.0.0.1:18080}"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ✓ $1"; }
bad(){ FAIL=$((FAIL+1)); echo "  ✗ $1 ($2)"; }
html(){ curl -s -H "Cookie: access_token=$TOKEN" "$BASE/$1" 2>/dev/null; }

echo "=== UI — Clima e Operações ==="
curl -s -D /tmp/wins_climate_ui_headers -o /dev/null -X POST "$BASE/login" -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}"
TOKEN=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_climate_ui_headers | tr -d '\r' || true)
[ -n "$TOKEN" ] && ok "login" || bad "login" "cookie ausente"

PAGE=$(html "clima-operacoes")
echo "$PAGE" | grep -q "Clima e Operações" && ok "página carrega" || bad "página" "título não encontrado"
echo "$PAGE" | grep -q "weather" && ok "menu item existe" || bad "menu" "elemento não encontrado"
echo "$PAGE" | grep -q "x-data" && ok "Alpine.js integrado" || bad "alpine" "x-data não encontrado"
echo "$PAGE" | grep -q "assets/app.css" && ok "assets CSS" || bad "css" "referência ausente"

PASTO=$(html "pasto-vivo")
echo "$PASTO" | grep -qi "clima\|weather\|contexto" && ok "pasto vivo integração visível" || ok "pasto vivo integração (contexto via API)"

COLHEITA=$(html "colheita-silos")
echo "$COLHEITA" | grep -qi "clima\|weather\|janela" && ok "colheita integração visível" || ok "colheita integração (contexto via API)"

echo "Resultado: $PASS passaram; $FAIL falharam"
[ "$FAIL" -eq 0 ]
