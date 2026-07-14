#!/usr/bin/env bash
set -euo pipefail
[ "${STAGING_TEST:-}" = "1" ] || { echo "Use STAGING_TEST=1"; exit 2; }
BASE="${STAGING_URL:-http://127.0.0.1:18080}"
FARM="f0000000-0000-4000-8000-000000000001"
PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ✓ $1"; }
bad(){ FAIL=$((FAIL+1)); echo "  ✗ $1 ($2)"; }
code(){ curl -s -o /dev/null -w '%{http_code}' "$@"; }

echo "=== HTTP — Colheita e Silos ==="
[ "$(code "$BASE/colheita-silos")" = 307 ] && ok "página exige autenticação" || bad "autenticação da página" "HTTP inesperado"
[ "$(code "$BASE/api/v2/farms/$FARM/harvest-silos/dashboard")" = 401 ] && ok "API exige autenticação" || bad "autenticação da API" "HTTP inesperado"
curl -s -D /tmp/wins_harvest_headers -o /dev/null -X POST "$BASE/login" -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}"
TOKEN=$(grep -oP 'access_token=\K[^;]+' /tmp/wins_harvest_headers | tr -d '\r' || true)
H="Cookie: access_token=$TOKEN"
[ -n "$TOKEN" ] && ok "login" || bad "login" "cookie ausente"

R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/harvest-silos/dashboard")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert 'active_plans_count' in d" && ok "dashboard" || bad "dashboard" "$R"
R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/harvest-silos/plans?limit=100")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['total'] >= 4" && ok "listagem e seed" || bad "listagem" "$R"
P=$(echo "$R" | python3 -c "import json,sys; print(json.load(sys.stdin)['items'][0]['public_id'])")
R=$(curl -s -H "$H" "$BASE/api/v2/farms/$FARM/harvest-silos/plans/$P")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['areas']" && ok "detalhe com áreas" || bad "detalhe" "$R"

SIM='{"name":"Manual","main_crop":"milho","purpose":"silagem","expected_start_date":"2026-07-20","expected_end_date":"2026-07-22","expected_field_loss_pct":"5","expected_ensiling_loss_pct":"8","areas":[{"name":"Talhão A","crop":"milho","area_ha":"20","expected_yield_t_ha":"40","expected_dm_pct":"35"}],"allocations":[]}'
R=$(curl -s -H "$H" -H 'Content-Type: application/json' -X POST "$BASE/api/v2/farms/$FARM/harvest-silos/simulate" -d "$SIM")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['expected_net_natural_kg']=='699200.00'; assert d['expected_dm_kg']=='244720.00'" && ok "simulação manual" || bad "simulação" "$R"

RUN=$(date +%s%N)
FAC_A=$(curl -s -H "$H" -H 'Content-Type: application/json' -X POST "$BASE/api/v2/farms/$FARM/feed-inventory/facilities" -d "{\"name\":\"Silo HTTP A $RUN\",\"code\":\"H4A$RUN\",\"facility_type\":\"silo_trincheira\",\"capacity_natural_kg\":\"1000000\"}" | python3 -c "import json,sys; print(json.load(sys.stdin)['public_id'])")
FAC_B=$(curl -s -H "$H" -H 'Content-Type: application/json' -X POST "$BASE/api/v2/farms/$FARM/feed-inventory/facilities" -d "{\"name\":\"Silo HTTP B $RUN\",\"code\":\"H4B$RUN\",\"facility_type\":\"silo_trincheira\",\"capacity_natural_kg\":\"1000000\"}" | python3 -c "import json,sys; print(json.load(sys.stdin)['public_id'])")
CREATE=$(python3 -c 'import json,sys; p=json.loads(sys.argv[1]); p["name"]="Teste HTTP "+sys.argv[2]; p["allocations"]=[{"facility_uuid":sys.argv[3],"expected_natural_kg":"400000","percentage":"57.21"},{"facility_uuid":sys.argv[4],"expected_natural_kg":"299200","percentage":"42.79"}]; print(json.dumps(p))' "$SIM" "$RUN" "$FAC_A" "$FAC_B")
R=$(curl -s -H "$H" -H 'Content-Type: application/json' -X POST "$BASE/api/v2/farms/$FARM/harvest-silos/plans" -d "$CREATE")
PLAN=$(echo "$R" | python3 -c "import json,sys; print(json.load(sys.stdin).get('public_id',''))" 2>/dev/null || true)
[ -n "$PLAN" ] && ok "criação com múltiplos silos" || bad "criação" "$R"
R=$(curl -s -H "$H" -H 'Content-Type: application/json' -X POST "$BASE/api/v2/farms/$FARM/harvest-silos/plans/$PLAN/start" -d '{"actual_start_date":"2026-07-20"}')
echo "$R" | python3 -c "import json,sys; assert json.load(sys.stdin)['status']=='in_progress'" && ok "início" || bad "início" "$R"
RID="complete-$RUN"
DONE="{\"actual_start_date\":\"2026-07-20\",\"actual_end_date\":\"2026-07-22\",\"actual_natural_kg\":\"699200\",\"actual_dm_pct\":\"35\",\"actual_loss_pct\":\"12.6\",\"request_id\":\"$RID\",\"allocations\":[{\"facility_uuid\":\"$FAC_A\",\"actual_natural_kg\":\"400000\",\"lot_name\":\"Lote A $RUN\",\"feed_type\":\"silagem_milho\"},{\"facility_uuid\":\"$FAC_B\",\"actual_natural_kg\":\"299200\",\"lot_name\":\"Lote B $RUN\",\"feed_type\":\"silagem_milho\"}]}"
R=$(curl -s -H "$H" -H "X-Request-ID: $RID" -H 'Content-Type: application/json' -X POST "$BASE/api/v2/farms/$FARM/harvest-silos/plans/$PLAN/complete" -d "$DONE")
echo "$R" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['status']=='completed'; assert len([a for a in d['allocations'] if a['created_feed_lot_uuid']])==2; assert sum(float(a['actual_quantity_natural_kg']) for a in d['allocations'])==699200" && ok "conclusão cria dois lotes e vínculos" || bad "conclusão" "$R"
FIRST=$(echo "$R" | python3 -c "import json,sys; print(json.load(sys.stdin)['allocations'][0]['created_feed_lot_uuid'])" 2>/dev/null || true)
REPLAY=$(curl -s -H "$H" -H "X-Request-ID: $RID" -H 'Content-Type: application/json' -X POST "$BASE/api/v2/farms/$FARM/harvest-silos/plans/$PLAN/complete" -d "$DONE")
echo "$REPLAY" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['allocations'][0]['created_feed_lot_uuid']=='$FIRST'" && ok "replay idempotente mantém lote" || bad "replay" "$REPLAY"
CONFLICT=$(echo "$DONE" | sed 's/\"actual_loss_pct\":\"12.6\"/\"actual_loss_pct\":\"12.5\"/')
[ "$(curl -s -o /dev/null -w '%{http_code}' -H "$H" -H "X-Request-ID: $RID" -H 'Content-Type: application/json' -X POST "$BASE/api/v2/farms/$FARM/harvest-silos/plans/$PLAN/complete" -d "$CONFLICT")" = 409 ] && ok "request_id divergente retorna 409" || bad "conflito idempotente" "HTTP inesperado"

CROSS="ffffffff-ffff-4fff-8fff-ffffffffffff"
[ "$(code -H "$H" "$BASE/api/v2/farms/$CROSS/harvest-silos/plans")" = 404 ] && ok "cross-tenant oculto" || bad "cross-tenant" "não retornou 404"

echo "Resultado: $PASS passaram; $FAIL falharam"
[ "$FAIL" -eq 0 ]
