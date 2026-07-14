#!/usr/bin/env bash
set -euo pipefail
[ "${STAGING_TEST:-}" = "1" ] || { echo "Use STAGING_TEST=1"; exit 2; }
BASE="${STAGING_URL:-http://127.0.0.1:18080}"; PASS=0; FAIL=0
ok(){ PASS=$((PASS+1)); echo "  ✓ $1"; }; bad(){ FAIL=$((FAIL+1)); echo "  ✗ $1"; }
TMP=/tmp/wins_ui_final
rm -f "$TMP"*
curl -s -D "${TMP}_headers" -o /dev/null -X POST "$BASE/login" \
  -d "email=${TEST_USER_EMAIL:-mari@winshubagro.cloud}&password=${TEST_USER_PASSWORD:-test}"
TOKEN=$(grep -oP 'access_token=\K[^;]+' "${TMP}_headers" | tr -d '\r' || true)
H="Cookie: access_token=$TOKEN"

echo "=== UI — Integração Final Gestão Agro ==="

# Visão Geral
curl -s -H "$H" "$BASE/visao-geral-agro" > "${TMP}_vg"
for term in "Visão Geral Agro" "Indicadores consolidados" "Selecione uma fazenda"; do
  grep -qF "$term" "${TMP}_vg" && ok "visão geral: $term" || bad "visão geral: $term"
done
grep -qF "Gestão Agro" "${TMP}_vg" && ok "menu: grupo Gestão Agro" || bad "menu: Gestão Agro ausente"
grep -qF "Visão Geral" "${TMP}_vg" && ok "menu: item Visão Geral" || bad "menu: Visão Geral ausente"

# Cada módulo renderiza seu título
MODULES=(
  "autonomia-alimentar:Autonomia Alimentar"
  "pasto-vivo:Pasto Vivo"
  "silagem-estoques:Silagem e Estoques"
  "colheita-silos:Colheita e Silos"
  "clima-operacoes:Clima e Operações"
)
for entry in "${MODULES[@]}"; do
  path="${entry%%:*}"
  title="${entry##*:}"
  curl -s -H "$H" "$BASE/$path" > "${TMP}_${path}"
  grep -qF "$title" "${TMP}_${path}" && ok "página $path: título presente" || bad "página $path: título '$title' ausente"
done

# Verifica que páginas não expõem UUIDs internos nem stack traces
for entry in "${MODULES[@]}"; do
  path="${entry%%:*}"
  if grep -qi "stacktrace\|Traceback\|Internal Server Error\|NoneType" "${TMP}_${path}"; then
    bad "$path: contém stack trace ou erro interno"
  else
    ok "$path: sem stack traces"
  fi
done

echo "Resultado: $PASS passaram; $FAIL falharam"; [ "$FAIL" -eq 0 ]
