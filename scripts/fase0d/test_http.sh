#!/usr/bin/env bash
# test_http.sh — Executa testes de rota HTTP real contra o staging
set -euo pipefail

API_URL="http://127.0.0.1:18080/api/v2/farms"

echo "=== Iniciando Testes HTTP Reais (Fase 0D) ==="

# Helper para gerar token JWT usando o python de dentro do container de staging
generate_token() {
  docker exec wins_agro_fase0d_api python -c "import jwt; print(jwt.encode({'sub': '$1'}, 'staging_jwt_secret_synthetic_64_characters_long_for_security_reasons', algorithm='HS256'))"
}

# 1. Sem cookie -> 401
echo -n "Teste 1: Sem cookie de sessão (espera 401)... "
code=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL")
if [[ "$code" -eq 401 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 2. Cookie inválido -> 401
echo -n "Teste 2: Cookie com assinatura inválida (espera 401)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=invalid_token" "$API_URL")
if [[ "$code" -eq 401 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# Gerando tokens sintéticos reais
T_OWNER_ALFA=$(generate_token "usr_owner_alfa")
T_TECH_ALFA=$(generate_token "usr_tech_alfa")
T_VIEW_ALFA=$(generate_token "usr_viewer_alfa")
T_NO_MEM=$(generate_token "usr_no_mem")
T_REVOKED=$(generate_token "usr_revoked")
T_INACTIVE=$(generate_token "usr_inactive")
T_OPER_BETA=$(generate_token "usr_oper_beta")
T_MULTI_ORG=$(generate_token "usr_multi_org")

# 3. Usuário sem membership -> 403
echo -n "Teste 3: Usuário sem membership ativa (espera 403)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_NO_MEM" "$API_URL")
if [[ "$code" -eq 403 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 4. Membership revogada -> 403
echo -n "Teste 4: Usuário com membership revogada (espera 403)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_REVOKED" "$API_URL")
if [[ "$code" -eq 403 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 5. Membership inativa -> 403
echo -n "Teste 5: Usuário com membership inativa (espera 403)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_INACTIVE" "$API_URL")
if [[ "$code" -eq 403 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 6. Owner Alfa (Auto-resolução, deve ver as 3 fazendas)
echo -n "Teste 6: Owner Alfa auto-resolve (espera 200, 3 fazendas)... "
body=$(curl -s --cookie "access_token=$T_OWNER_ALFA" "$API_URL")
count=$(echo "$body" | docker exec -i wins_agro_fase0d_api python -c "import sys, json; print(len(json.load(sys.stdin)['items']))")
if [[ "$count" -eq 3 ]]; then echo "OK"; else echo "FALHA (count=$count)"; exit 1; fi

# 7. Technician Alfa (Auto-resolve, vê apenas 1 fazenda atribuída)
echo -n "Teste 7: Technician Alfa (espera 200, 1 fazenda)... "
body=$(curl -s --cookie "access_token=$T_TECH_ALFA" "$API_URL")
count=$(echo "$body" | docker exec -i wins_agro_fase0d_api python -c "import sys, json; print(len(json.load(sys.stdin)['items']))")
if [[ "$count" -eq 1 ]]; then echo "OK"; else echo "FALHA (count=$count)"; exit 1; fi

# 8. Viewer Alfa (Auto-resolve, vê apenas 1 fazenda atribuída)
echo -n "Teste 8: Viewer Alfa (espera 200, 1 fazenda)... "
body=$(curl -s --cookie "access_token=$T_VIEW_ALFA" "$API_URL")
count=$(echo "$body" | docker exec -i wins_agro_fase0d_api python -c "import sys, json; print(len(json.load(sys.stdin)['items']))")
if [[ "$count" -eq 1 ]]; then echo "OK"; else echo "FALHA (count=$count)"; exit 1; fi

# 9. Usuário Beta tentando Alfa (cross-tenant, deve retornar 404)
echo -n "Teste 9: Usuário Beta tenta acessar Alfa por UUID (espera 404)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_OPER_BETA" "${API_URL}?organization_uuid=a0000000-0000-4000-8000-00000000000a")
if [[ "$code" -eq 404 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 10. Organization UUID inexistente -> 404
echo -n "Teste 10: Organization UUID inexistente (espera 404)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_OWNER_ALFA" "${API_URL}?organization_uuid=00000000-0000-0000-0000-000000000000")
if [[ "$code" -eq 404 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 11. Usuário multi-org sem contexto -> 409
echo -n "Teste 11: Usuário multi-org sem organization_uuid (espera 409)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_MULTI_ORG" "$API_URL")
if [[ "$code" -eq 409 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 12. Usuário multi-org com Alfa -> 200
echo -n "Teste 12: Usuário multi-org com Alfa UUID (espera 200)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_MULTI_ORG" "${API_URL}?organization_uuid=a0000000-0000-4000-8000-00000000000a")
if [[ "$code" -eq 200 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 13. Paginação limit=1 -> has_more=true
echo -n "Teste 13: Limit=1 (espera 200, 1 item, has_more=true)... "
body=$(curl -s --cookie "access_token=$T_OWNER_ALFA" "${API_URL}?limit=1")
has_more=$(echo "$body" | docker exec -i wins_agro_fase0d_api python -c "import sys, json; print(json.load(sys.stdin)['pagination']['has_more'])")
if [[ "$has_more" == "True" ]]; then echo "OK"; else echo "FALHA (has_more=$has_more)"; exit 1; fi

# 14. Paginação limit=101 -> 422
echo -n "Teste 14: Limit=101 (espera 422)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_OWNER_ALFA" "${API_URL}?limit=101")
if [[ "$code" -eq 422 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 15. Offset negativo -> 422
echo -n "Teste 15: Offset negativo (espera 422)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_OWNER_ALFA" "${API_URL}?offset=-5")
if [[ "$code" -eq 422 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 16. Status inválido -> 422
echo -n "Teste 16: Status inválido (espera 422)... "
code=$(curl -s -o /dev/null -w "%{http_code}" --cookie "access_token=$T_OWNER_ALFA" "${API_URL}?status=invalid")
if [[ "$code" -eq 422 ]]; then echo "OK"; else echo "FALHA ($code)"; exit 1; fi

# 17. Verificação de cabeçalhos de resposta
echo -n "Teste 17: Verificação de cabeçalhos de cache (no-store)... "
headers=$(curl -s -D - -o /dev/null --cookie "access_token=$T_OWNER_ALFA" "$API_URL")
if echo "$headers" | grep -qi "Cache-Control: no-store, private" && echo "$headers" | grep -qi "Pragma: no-cache"; then
    echo "OK"
else
    echo "FALHA (headers incompletos)"
    exit 1
fi

echo "=========================================================="
echo "TODOS OS TESTES HTTP PASSARAM COM SUCESSO!"
echo "=========================================================="
