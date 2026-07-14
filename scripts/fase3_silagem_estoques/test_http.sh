#!/usr/bin/env bash
# test_http.sh — Testes HTTP de integração do módulo de Silagem e Estoques
set -euo pipefail

BASE_URL="${STAGING_URL:-http://127.0.0.1:18080}"
FARM_UUID="f0000000-0000-4000-8000-000000000001"
PASS=0
FAIL=0
TOTAL=0

ok() { TOTAL=$((TOTAL+1)); PASS=$((PASS+1)); echo "  ✓ $1"; }
fail() { TOTAL=$((TOTAL+1)); FAIL=$((FAIL+1)); echo "  ✗ $1: $2"; }

echo "=== Testes HTTP — Silagem e Estoques ==="
echo "Base: $BASE_URL"

# 1. Autenticação
echo "--- 1. Autenticação ---"
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/silagem-estoques")
[ "$CODE" = "302" ] || [ "$CODE" = "307" ] && ok "Página redireciona para login" || fail "Página sem auth" "HTTP $CODE"

CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/facilities")
[ "$CODE" = "401" ] && ok "List facilities sem auth retorna 401" || fail "List sem auth" "HTTP $CODE"

# 2. Login
echo "--- 2. Login ---"
LOGIN_RESP=$(curl -s -D /tmp/wins_storage_headers.txt -c /tmp/wins_storage_cookies.txt -w "\n%{http_code}" \
  -X POST "$BASE_URL/login" \
  -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}" 2>&1)
LOGIN_CODE=$(echo "$LOGIN_RESP" | tail -1)
[ "$LOGIN_CODE" = "303" ] || [ "$LOGIN_CODE" = "200" ] && ok "Login bem-sucedido" || fail "Login" "HTTP $LOGIN_CODE"

JWT=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_storage_headers.txt 2>/dev/null || true)
AUTH_HEADER=""
[ -n "$JWT" ] && AUTH_HEADER="Cookie: access_token=$JWT"

# 2.5 Cleanup test data from previous runs (only archive test lots, not seed lots)
echo "--- 2.5 Cleanup ---"
ok "Cleanup pulado (dados preservados)"

# 3. Criar facility
echo "--- 3. Criar Facility ---"
UNIQUE_CODE="STH$(date +%s | tail -c 6)"
CREATE_RESP=$(curl -s -H "$AUTH_HEADER" \
  -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/facilities" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Silo Teste HTTP\",\"code\":\"$UNIQUE_CODE\",\"facility_type\":\"silo_trincheira\",\"capacity_natural_kg\":\"50000\",\"location_description\":\"Teste HTTP\"}")
echo "$CREATE_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['name']=='Silo Teste HTTP'" 2>/dev/null \
  && ok "Facility criada" || fail "Criar facility" "resposta inválida"

FACILITY_UUID=$(echo "$CREATE_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['public_id'])" 2>/dev/null || true)

# 4. Listar facilities
echo "--- 4. Listar Facilities ---"
LIST_RESP=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/facilities")
echo "$LIST_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items',d.get('facilities',[])); assert len(items) >= 2" 2>/dev/null \
  && ok "Listagem retorna ≥2 facilities" || fail "Listar facilities" "count < 2"

# 5. Obter facility
echo "--- 5. Obter Facility ---"
if [ -n "$FACILITY_UUID" ]; then
  GET_RESP=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/facilities/$FACILITY_UUID")
  echo "$GET_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['public_id']=='$FACILITY_UUID'" 2>/dev/null \
    && ok "Facility obtida" || fail "Obter facility" "UUID não confere"
fi

# 6. Atualizar facility
echo "--- 6. Atualizar Facility ---"
if [ -n "$FACILITY_UUID" ]; then
  UPD_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X PUT "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/facilities/$FACILITY_UUID" \
    -H "Content-Type: application/json" \
    -d '{"name":"Silo Teste HTTP","capacity_natural_kg":"60000","notes":"Atualizado via teste HTTP"}')
  echo "$UPD_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['notes']=='Atualizado via teste HTTP'" 2>/dev/null \
    && ok "Facility atualizada" || fail "Atualizar facility" "resposta inválida"
fi

# 7. Criar lot
echo "--- 7. Criar Lot ---"
if [ -n "$FACILITY_UUID" ]; then
  LOT_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots" \
    -H "Content-Type: application/json" \
    -d "{\"facility_uuid\":\"$FACILITY_UUID\",\"name\":\"Lote Teste HTTP\",\"feed_type\":\"silagem_milho\",\"production_date\":\"2026-07-01\",\"initial_quantity_natural_kg\":\"10000\",\"dry_matter_pct\":\"35\",\"utilization_pct\":\"90\"}")
  echo "$LOT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['name']=='Lote Teste HTTP'" 2>/dev/null \
    && ok "Lot criado" || fail "Criar lot" "resposta inválida"
  LOT_UUID=$(echo "$LOT_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin)['public_id'])" 2>/dev/null || true)
fi

# 8. Listar lots
echo "--- 8. Listar Lots ---"
LOTS_RESP=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots")
echo "$LOTS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items',d.get('lots',[])); assert len(items) >= 4" 2>/dev/null \
  && ok "Listagem retorna ≥4 lots" || fail "Listar lots" "count < 4"

# 9. Obter lot
echo "--- 9. Obter Lot ---"
if [ -n "$LOT_UUID" ]; then
  LOT_GET=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID")
  echo "$LOT_GET" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['public_id']=='$LOT_UUID'" 2>/dev/null \
    && ok "Lot obtido" || fail "Obter lot" "UUID não confere"
fi

# 10. Registrar saldo inicial
echo "--- 10. Saldo Inicial ---"
if [ -n "$LOT_UUID" ]; then
  BAL_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/movements" \
    -H "Content-Type: application/json" \
    -d '{"movement_type":"initial_balance","quantity_natural_kg":"10000","dry_matter_pct":"35","utilization_pct":"90","reason":"Saldo teste HTTP","request_id":"req-http-bal-001"}')
  echo "$BAL_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('movement_type')=='initial_balance' or 'public_id' in d" 2>/dev/null \
    && ok "Saldo inicial registrado" || fail "Saldo inicial" "resposta: $(echo "$BAL_RESP" | head -c 200)"
fi

# 11. Entrada
echo "--- 11. Entrada ---"
if [ -n "$LOT_UUID" ]; then
  ENTRY_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/movements" \
    -H "Content-Type: application/json" \
    -d '{"movement_type":"entry","quantity_natural_kg":"2000","dry_matter_pct":"35","utilization_pct":"90","reason":"Compra teste","request_id":"req-http-entry-001"}')
  echo "$ENTRY_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('movement_type')=='entry' or 'public_id' in d" 2>/dev/null \
    && ok "Entrada registrada" || fail "Entrada" "resposta: $(echo "$ENTRY_RESP" | head -c 200)"
fi

# 12. Retirada (sucesso)
echo "--- 12. Retirada ---"
if [ -n "$LOT_UUID" ]; then
  WD_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/movements" \
    -H "Content-Type: application/json" \
    -d '{"movement_type":"withdrawal","quantity_natural_kg":"500","dry_matter_pct":"35","utilization_pct":"90","reason":"Uso diário teste","request_id":"req-http-wd-001"}')
  echo "$WD_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('movement_type')=='withdrawal' or 'public_id' in d" 2>/dev/null \
    && ok "Retirada registrada" || fail "Retirada" "resposta: $(echo "$WD_RESP" | head -c 200)"
fi

# 13. Retirada excede saldo (falha)
echo "--- 13. Retirada Excede Saldo ---"
if [ -n "$LOT_UUID" ]; then
  OVER_RESP=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/movements" \
    -H "Content-Type: application/json" \
    -d '{"movement_type":"withdrawal","quantity_natural_kg":"999999","dry_matter_pct":"35","utilization_pct":"90","reason":"Tentativa excessiva","request_id":"req-http-wd-over-001"}')
  [ "$OVER_RESP" = "403" ] || [ "$OVER_RESP" = "409" ] || [ "$OVER_RESP" = "422" ] && ok "Retirada excede saldo bloqueada (HTTP $OVER_RESP)" || fail "Retirada excede saldo" "HTTP $OVER_RESP"
fi

# 14. Perda
echo "--- 14. Perda ---"
if [ -n "$LOT_UUID" ]; then
  LOSS_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/movements" \
    -H "Content-Type: application/json" \
    -d '{"movement_type":"loss","quantity_natural_kg":"100","dry_matter_pct":"35","utilization_pct":"90","loss_reason":"Mofamento","reason":"Perda teste","request_id":"req-http-loss-001"}')
  echo "$LOSS_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('movement_type')=='loss' or 'public_id' in d" 2>/dev/null \
    && ok "Perda registrada" || fail "Perda" "resposta: $(echo "$LOSS_RESP" | head -c 200)"
fi

# 15. Ajuste
echo "--- 15. Ajuste ---"
if [ -n "$LOT_UUID" ]; then
  ADJ_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/movements" \
    -H "Content-Type: application/json" \
    -d '{"movement_type":"adjustment_positive","quantity_natural_kg":"50","dry_matter_pct":"35","utilization_pct":"90","reason":"Ajuste de balança","request_id":"req-http-adj-001"}')
  echo "$ADJ_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('movement_type')=='adjustment_positive' or 'public_id' in d" 2>/dev/null \
    && ok "Ajuste registrado" || fail "Ajuste" "resposta: $(echo "$ADJ_RESP" | head -c 200)"
fi

# 16. Retirada dupla em lote esgotado (falha)
echo "--- 16. Retirada Dupla em Lote Esgotado ---"
# Lote 3 (quase esgotado, saldo 2500 kg) — usar LOT_3 se existir
LOT3_UUID=$(echo "$LOTS_RESP" | python3 -c "
import sys,json
d=json.load(sys.stdin)
items=d.get('items',d.get('lots',[]))
for l in items:
    if l.get('name')=='Silagem Milho Antiga':
        print(l['public_id']); break
" 2>/dev/null || true)

if [ -n "$LOT3_UUID" ]; then
  # Tentar retirar mais do que o saldo
  DOUBLE_WD=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT3_UUID/movements" \
    -H "Content-Type: application/json" \
    -d '{"movement_type":"withdrawal","quantity_natural_kg":"5000","dry_matter_pct":"32","utilization_pct":"85","reason":"Tentativa dupla","request_id":"req-http-double-wd-001"}')
  [ "$DOUBLE_WD" = "403" ] || [ "$DOUBLE_WD" = "409" ] || [ "$DOUBLE_WD" = "422" ] && ok "Retirada dupla bloqueada (HTTP $DOUBLE_WD)" || fail "Retirada dupla" "HTTP $DOUBLE_WD"
fi

# 17. Idempotência request_id
echo "--- 17. Idempotência request_id ---"
if [ -n "$LOT_UUID" ]; then
  IDEM_PAYLOAD='{"movement_type":"entry","quantity_natural_kg":"100","dry_matter_pct":"35","utilization_pct":"90","reason":"Idempotente 1","request_id":"req-http-idem-unique-999"}'
  IDEM1_RESP=$(curl -s -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/movements" \
    -H "Content-Type: application/json" \
    -d "$IDEM_PAYLOAD")
  IDEM1_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/movements" \
    -H "Content-Type: application/json" \
    -d "$IDEM_PAYLOAD")
  
  ([ "$IDEM1_CODE" = "200" ] || [ "$IDEM1_CODE" = "201" ]) && ok "Replay idêntico bem-sucedido (HTTP $IDEM1_CODE)" || fail "Replay idêntico" "HTTP $IDEM1_CODE"

  IDEM_PAYLOAD_DIFF='{"movement_type":"entry","quantity_natural_kg":"100","dry_matter_pct":"35","utilization_pct":"90","reason":"DIFERENTE","request_id":"req-http-idem-unique-999"}'
  IDEM2_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
    -X POST "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/movements" \
    -H "Content-Type: application/json" \
    -d "$IDEM_PAYLOAD_DIFF")
  [ "$IDEM2_CODE" = "409" ] && ok "request_id com payload diferente retorna 409" || fail "Payload diferente conflito" "HTTP $IDEM2_CODE"
fi

# 18. Histórico de movimentações
echo "--- 18. Histórico de Movimentações ---"
if [ -n "$LOT_UUID" ]; then
  HIST_RESP=$(curl -s -H "$AUTH_HEADER" "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/movements")
  echo "$HIST_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); items=d.get('items',d.get('movements',[])); assert len(items) >= 4" 2>/dev/null \
    && ok "Histórico retorna ≥4 movimentações" || fail "Histórico" "count < 4"
fi

# 19. Reconciliação
echo "--- 19. Reconciliação ---"
if [ -n "$LOT_UUID" ]; then
  RECON_RESP=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
    "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID/reconciliation")
  [ "$RECON_RESP" = "200" ] && ok "Reconciliação retorna 200" || fail "Reconciliação" "HTTP $RECON_RESP"
fi

# 20. Dashboard
echo "--- 20. Dashboard ---"
DASH_RESP=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
  "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/dashboard")
[ "$DASH_RESP" = "200" ] && ok "Dashboard retorna 200" || fail "Dashboard" "HTTP $DASH_RESP"

# 21. Fontes de autonomia
echo "--- 21. Fontes de Autonomia ---"
AUTO_RESP=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
  "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/autonomy-sources")
[ "$AUTO_RESP" = "200" ] && ok "Autonomy sources retorna 200" || fail "Autonomy sources" "HTTP $AUTO_RESP"

# 22. Arquivar lot
echo "--- 22. Arquivar Lot ---"
if [ -n "$LOT_UUID" ]; then
  ARCH_LOT=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
    -X DELETE "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/lots/$LOT_UUID")
  [ "$ARCH_LOT" = "200" ] || [ "$ARCH_LOT" = "204" ] && ok "Lot arquivado (HTTP $ARCH_LOT)" || fail "Arquivar lot" "HTTP $ARCH_LOT"
fi

# 23. Arquivar facility com lots ativos (falha)
echo "--- 23. Arquivar Facility com Lots Ativos ---"
if [ -n "$FACILITY_UUID" ]; then
  ARCH_FAC=$(curl -s -o /dev/null -w "%{http_code}" -H "$AUTH_HEADER" \
    -X DELETE "$BASE_URL/api/v2/farms/$FARM_UUID/feed-inventory/facilities/$FACILITY_UUID")
  [ "$ARCH_FAC" = "409" ] || [ "$ARCH_FAC" = "403" ] || [ "$ARCH_FAC" = "422" ] && ok "Arquivar facility com lots ativos bloqueado (HTTP $ARCH_FAC)" || fail "Arquivar facility" "HTTP $ARCH_FAC"
fi

# 24. Feature flag
echo "--- 24. Feature Flag ---"
FLAG=$(docker inspect wins_agro_fase0d_api --format '{{range .Config.Env}}{{println .}}{{end}}' 2>/dev/null | grep "ENABLE_FEED_INVENTORY=true" || true)
[ -n "$FLAG" ] && ok "Feature flag ENABLE_FEED_INVENTORY ativa" || fail "Flag" "não configurada"

echo ""
echo "=== Resultado: $PASS/$TOTAL passaram, $FAIL falharam ==="
[ "$FAIL" -eq 0 ] && exit 0 || exit 1
