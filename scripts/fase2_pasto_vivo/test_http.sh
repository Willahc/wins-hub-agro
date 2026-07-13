#!/usr/bin/env bash
# test_http.sh — Testes HTTP de integração do módulo de Pasto Vivo
set -euo pipefail

BASE_URL="${STAGING_URL:-http://127.0.0.1:18080}"
FARM_UUID="f0000000-0000-4000-8000-000000000001"
PASS=0
FAIL=0
TOTAL=0

ok() { TOTAL=$((TOTAL+1)); PASS=$((PASS+1)); echo "  ✓ $1"; }
fail() { TOTAL=$((TOTAL+1)); FAIL=$((FAIL+1)); echo "  ✗ $1: $2"; }

echo "=== Testes HTTP — Pasto Vivo ==="
echo "Base: $BASE_URL"

# 1. Autenticação
echo "--- 1. Autenticação ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/pasto-vivo")
[ "$CODE" = "302" ] || [ "$CODE" = "307" ] && ok "Página redireciona para login" || fail "Página sem auth" "HTTP $CODE"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/paddocks")
[ "$CODE" = "401" ] && ok "List paddocks sem auth retorna 401" || fail "List sem auth" "HTTP $CODE"

# 2. Login
echo "--- 2. Login ---"
LOGIN_RESP=$(curl -s -D /tmp/wins_pasture_headers.txt -c /tmp/wins_pasture_cookies.txt -w "\n%{http_code}" \
  -X POST "$BASE_URL/login" \
  -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}" 2>&1)
LOGIN_CODE=$(echo "$LOGIN_RESP" | tail -1)
[ "$LOGIN_CODE" = "303" ] || [ "$LOGIN_CODE" = "200" ] && ok "Login bem-sucedido" || fail "Login" "HTTP $LOGIN_CODE"

JWT=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_pasture_headers.txt 2>/dev/null || true)
AUTH_HEADER=""
[ -n "$JWT" ] && AUTH_HEADER="Cookie: access_token=$JWT"

# 3. Criar piquete
echo "--- 3. Criar Piquete ---"
CREATE_RESP=$(curl -s -H "$AUTH_HEADER" \
  -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/paddocks" \
  -H "Content-Type: application/json" \
  -d '{"name":"Piquete Teste HTTP","code":"PTH99","forage_species":"brachiaria_brizantha","cultivar":"Marandu","area_ha":"4.5","target_entry_height_cm":"25","target_exit_height_cm":"8","planned_rest_days":"20","default_utilization_pct":"50","manual_status":"ready","notes":"Teste HTTP"}')
echo "$CREATE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['name']=='Piquete Teste HTTP'" 2>/dev/null \
  && ok "Piquete criado" || fail "Criar piquete" "resposta inválida"

PADDOCK_UUID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['public_id'])" 2>/dev/null || true)

# 4. Listar piquetes
echo "--- 4. Listar Piquetes ---"
LIST_RESP=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/paddocks")
echo "$LIST_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items',d.get('paddocks',[])); assert len(items) >= 4" 2>/dev/null \
  && ok "Listagem retorna ≥4 piquetes" || fail "Listar piquetes" "count < 4"

# 5. Obter piquete
echo "--- 5. Obter Piquete ---"
if [ -n "$PADDOCK_UUID" ]; then
  GET_RESP=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/paddocks/$PADDOCK_UUID")
  echo "$GET_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['public_id']=='$PADDOCK_UUID'" 2>/dev/null \
    && ok "Piquete obtido" || fail "Obter piquete" "UUID não confere"
fi

# 6. Atualizar piquete
echo "--- 6. Atualizar Piquete ---"
if [ -n "$PADDOCK_UUID" ]; then
  UPD_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X PUT "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/paddocks/$PADDOCK_UUID" \
    -H "Content-Type: application/json" \
    -d '{"name":"Piquete Teste HTTP","area_ha":"4.5","forage_species":"brachiaria_brizantha","planned_rest_days":"20","default_utilization_pct":"50","manual_status":"ready","active":true,"notes":"Atualizado via teste HTTP"}')
  echo "$UPD_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['notes']=='Atualizado via teste HTTP'" 2>/dev/null \
    && ok "Piquete atualizado" || fail "Atualizar piquete" "resposta inválida"
fi

# 7. Criar medição
echo "--- 7. Criar Medição ---"
if [ -n "$PADDOCK_UUID" ]; then
  MEAS_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/paddocks/$PADDOCK_UUID/measurements" \
    -H "Content-Type: application/json" \
    -d '{"average_height_cm":"22","available_dm_kg_ha":"1600","utilization_pct":"55","measurement_method":"ruler","notes":"Medição teste"}')
  echo "$MEAS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'calculated_total_dm_kg' in d" 2>/dev/null \
    && ok "Medição criada" || fail "Criar medição" "resposta: $(echo "$MEAS_RESP" | head -c 200)"
fi

# 8. Iniciar pastejo
echo "--- 8. Iniciar Pastejo ---"
if [ -n "$PADDOCK_UUID" ]; then
  GRAZE_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/paddocks/$PADDOCK_UUID/events" \
    -H "Content-Type: application/json" \
    -d '{"event_type":"grazing_started","head_count":30,"average_weight_kg":"420","management_group_name":"Vacada","notes":"Pastejo teste"}')
  echo "$GRAZE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='grazing'" 2>/dev/null \
    && ok "Pastejo iniciado" || fail "Iniciar pastejo" "resposta: $GRAZE_RESP"
fi

# 9. Bloquear pastejo duplo
echo "--- 9. Bloquear Pastejo Duplo ---"
if [ -n "$PADDOCK_UUID" ]; then
  DOUBLE_RESP=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/paddocks/$PADDOCK_UUID/events" \
    -H "Content-Type: application/json" \
    -d '{"event_type":"grazing_started","head_count":10,"average_weight_kg":"400","management_group_name":"Teste","notes":"Tentativa dupla"}')
  [ "$DOUBLE_RESP" = "403" ] || [ "$DOUBLE_RESP" = "409" ] || [ "$DOUBLE_RESP" = "422" ] && ok "Pastejo duplo bloqueado (HTTP $DOUBLE_RESP)" || fail "Pastejo duplo" "HTTP $DOUBLE_RESP"
fi

# 10. Finalizar pastejo
echo "--- 10. Finalizar Pastejo ---"
if [ -n "$PADDOCK_UUID" ]; then
  FINISH_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/paddocks/$PADDOCK_UUID/events" \
    -H "Content-Type: application/json" \
    -d '{"event_type":"grazing_finished","notes":"Fim do pastejo teste"}')
  echo "$FINISH_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='resting'" 2>/dev/null \
    && ok "Pastejo finalizado" || fail "Finalizar pastejo" "resposta: $FINISH_RESP"
fi

# 11. Dashboard
echo "--- 11. Dashboard ---"
DASH_RESP=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
  "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/dashboard")
[ "$DASH_RESP" = "200" ] && ok "Dashboard retorna 200" || fail "Dashboard" "HTTP $DASH_RESP"

# 12. Fontes de autonomia
echo "--- 12. Fontes de Autonomia ---"
AUTO_RESP=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
  "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/autonomy-sources")
[ "$AUTO_RESP" = "200" ] && ok "Autonomy sources retorna 200" || fail "Autonomy sources" "HTTP $AUTO_RESP"

# 13. Arquivar piquete
echo "--- 13. Arquivar Piquete ---"
if [ -n "$PADDOCK_UUID" ]; then
  ARCH_RESP=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
    -X DELETE "$BASE_URL/api/v2/farms/$FARM_UUID/pasture-live/paddocks/$PADDOCK_UUID")
  [ "$ARCH_RESP" = "200" ] || [ "$ARCH_RESP" = "204" ] && ok "Piquete arquivado (HTTP $ARCH_RESP)" || fail "Arquivar piquete" "HTTP $ARCH_RESP"
fi

# 14. Feature flag
echo "--- 14. Feature Flag ---"
FLAG=$(docker inspect wins_agro_fase0d_api --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "ENABLE_PASTURE_LIVE=true" || true)
[ -n "$FLAG" ] && ok "Feature flag ENABLE_PASTURE_LIVE ativa" || fail "Flag" "não configurada"

echo ""
echo "=== Resultado: $PASS/$TOTAL passaram, $FAIL falharam ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
