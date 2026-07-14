#!/usr/bin/env bash
set -euo pipefail
[ "${STAGING_TEST:-}" = "1" ] || { echo "Use STAGING_TEST=1"; exit 2; }
BASE="${STAGING_URL:-http://127.0.0.1:18080}"
FARM="f0000000-0000-4000-8000-000000000001"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ✓ $1"; }
bad(){ FAIL=$((FAIL+1)); echo "  ✗ $1 ($2)"; }
code(){ curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "=== HTTP — Integração Final Gestão Agro ==="

# Autenticação
[ "$(code "$BASE/visao-geral-agro")" = 307 ] && ok "visão geral exige autenticação" || bad "autenticação da página" "HTTP inesperado"
[ "$(code "$BASE/api/agro/overview")" = 401 ] && ok "API overview exige autenticação" || bad "autenticação da API" "HTTP inesperado"

curl -s -D /tmp/wins_final_headers -o /dev/null -X POST "$BASE/login" \
  -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}"
TOKEN=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_final_headers | tr -d '\r' || true)
H="Cookie: access_token=$TOKEN"
[ -n "$TOKEN" ] && ok "login" || bad "login" "cookie ausente"

# Visão Geral Agro — listagem de fazendas
R=$(curl -s -H "$H" "$BASE/api/agro/overview")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'farms' in d; assert len(d['farms']) > 0" && ok "overview lista fazendas" || bad "overview list" "$R"

# Visão Geral Agro — dados da fazenda
R=$(curl -s -H "$H" "$BASE/api/agro/overview?farm_uuid=$FARM")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'modules' in d" && ok "overview com farm_uuid" || bad "overview farm" "$R"

# Verifica módulos ativos
R=$(curl -s -H "$H" "$BASE/api/agro/overview?farm_uuid=$FARM")
echo "$R" | python3 -c "
import json,sys
d=json.load(sys.stdin)
mods = d.get('modules', {})
# Pelo menos 1 módulo deve estar disponível em staging
assert len(mods) >= 1, f'Nenhum módulo ativo: {mods}'
" && ok "pelo menos um módulo ativo" || bad "módulos ativos" "$R"

# Página visão geral carrega
PAGE=$(curl -s -H "$H" "$BASE/visao-geral-agro")
echo "$PAGE" | grep -q "Visão Geral Agro" && ok "página visão geral renderiza" || bad "página visão geral" "título não encontrado"

# Verifica acesso a cada módulo individual
MODULES=("autonomia-alimentar" "pasto-vivo" "silagem-estoques" "colheita-silos" "clima-operacoes")
for m in "${MODULES[@]}"; do
  HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' -H "$H" "$BASE/$m")
  if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "307" ] || [ "$HTTP_CODE" = "302" ]; then
    ok "módulo $m acessível (HTTP $HTTP_CODE)"
  else
    bad "módulo $m" "HTTP $HTTP_CODE"
  fi
done

# CSS e JS carregam
for asset in /static/assets/app.css /static/vendor/alpine.min.js; do
  [ "$(curl -s -o /dev/null -w '%{http_code}' "$BASE$asset")" = 200 ] && ok "$asset" || bad "$asset"
done

# Cross-tenant isolation
CROSS="ffffffff-ffff-4fff-8fff-ffffffffffff"
[ "$(code -H "$H" "$BASE/api/agro/overview?farm_uuid=$CROSS")" != 200 ] && ok "cross-tenant oculto" || bad "cross-tenant" "não foi ocultado"

echo "Resultado: $PASS passaram; $FAIL falharam"
[ "$FAIL" -eq 0 ]
