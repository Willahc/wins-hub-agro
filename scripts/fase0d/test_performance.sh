#!/usr/bin/env bash
# test_performance.sh — Carrega volume de dados e mede latência e planos de execução
set -euo pipefail

API_URL="http://127.0.0.1:18080/api/v2/farms"

echo "=== Iniciando Teste de Performance (Fase 0D) ==="

# 1. Carregar volume de dados moderado via SQL rápido
echo "Populando banco de staging com volume de performance..."
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging <<'SQL'
BEGIN;
-- Insere 100 organizações
INSERT INTO foundation.organizations (id, public_id, name, slug, status)
OVERRIDING SYSTEM VALUE
SELECT i, gen_random_uuid(), 'Org Perf ' || i, 'org-perf-' || i, 'active'
  FROM generate_series(4, 103) as i
ON CONFLICT (id) DO NOTHING;

-- Insere 1,000 usuários
INSERT INTO foundation.app_users (id, public_id, auth_subject, status)
OVERRIDING SYSTEM VALUE
SELECT i, gen_random_uuid(), 'usr_subject_' || i, 'active'
  FROM generate_series(11, 1010) as i
ON CONFLICT (id) DO NOTHING;

-- Insere 10,000 fazendas
INSERT INTO foundation.operational_farms (id, public_id, organization_id, name, state, municipality_code, area_ha, status)
OVERRIDING SYSTEM VALUE
SELECT i, gen_random_uuid(), 4 + (i % 100), 'Fazenda Perf ' || i, 'SP', '3550308', 100.00, 'active'
  FROM generate_series(10, 10009) as i
ON CONFLICT (id) DO NOTHING;

-- Insere 20,000 memberships (ignora conflitos de par ativo)
INSERT INTO foundation.organization_memberships (id, public_id, organization_id, user_id, role, status)
OVERRIDING SYSTEM VALUE
SELECT i, gen_random_uuid(), 4 + (i % 100), 11 + (i % 1000), 'technician', 'active'
  FROM generate_series(11, 20010) as i
ON CONFLICT (organization_id, user_id) WHERE status = 'active' DO NOTHING;

-- Insere 30,000 farm accesses respeitando a FK composta
INSERT INTO foundation.farm_access (id, public_id, organization_id, farm_id, membership_id, access_level, status)
OVERRIDING SYSTEM VALUE
SELECT i, gen_random_uuid(), f.organization_id, f.id, m.id, 'operate', 'active'
  FROM generate_series(11, 30010) as i
  JOIN foundation.operational_farms f ON f.id = 10 + (i % 10000)
  JOIN foundation.organization_memberships m ON m.organization_id = f.organization_id AND m.id = 1 + (i % 10)
ON CONFLICT (farm_id, membership_id) WHERE status = 'active' DO NOTHING;

COMMIT;
ANALYZE;
SQL

# 2. Executar EXPLAIN ANALYZE e exibir planos resumidos
echo "=== Planos de Execução (EXPLAIN ANALYZE) ==="
docker exec -i wins_agro_fase0d_db psql -U fase0_test -d fase0d_staging <<'SQL'
-- Exemplo de listagem para Técnico (Filtro farm_access)
EXPLAIN ANALYZE
SELECT DISTINCT f.id, f.public_id, f.name, f.state, f.municipality_code, f.area_ha::text as area_ha, f.status,
       a.access_level
  FROM foundation.operational_farms f
  LEFT JOIN foundation.farm_access a ON a.farm_id = f.id
                                    AND a.membership_id = 15
                                    AND a.status = 'active'
                                    AND (a.expires_at IS NULL OR a.expires_at > now())
 WHERE f.organization_id = 5
   AND f.status = 'active'
   AND (FALSE OR a.id IS NOT NULL)
 ORDER BY f.name ASC, f.public_id ASC
 LIMIT 26 OFFSET 0;
SQL

# 3. Teste de latência (50 chamadas HTTP locais)
echo "=== Medindo Latência HTTP (50 chamadas locais) ==="
T_OWNER_ALFA=$(docker exec wins_agro_fase0d_api python -c "import jwt; print(jwt.encode({'sub': 'usr_owner_alfa'}, 'staging_jwt_secret_synthetic_64_characters_long_for_security_reasons', algorithm='HS256'))")

# Cria arquivo temporário para tempos de resposta
durations_file=$(mktemp)

for i in $(seq 1 50); do
  # Mede tempo em segundos com 3 casas decimais
  duration=$(curl -s -o /dev/null -w "%{time_total}" --cookie "access_token=$T_OWNER_ALFA" "$API_URL")
  # Converte para milissegundos
  ms=$(python3 -c "print(int($duration * 1000))")
  echo "$ms" >> "$durations_file"
done

# Calcula mediana e p95
stats=$(python3 -c "
import sys
durations = sorted([int(line.strip()) for line in open('$durations_file')])
n = len(durations)
median = durations[n // 2]
p95 = durations[int(n * 0.95)]
print(f'median={median} ms; p95={p95} ms')
")

echo "Resultados de Latência: $stats"

rm -f "$durations_file"

median_val=$(echo "$stats" | cut -d';' -f1 | cut -d'=' -f2 | awk '{print $1}')
p95_val=$(echo "$stats" | cut -d';' -f2 | cut -d'=' -f2 | awk '{print $1}')

if [[ "$p95_val" -lt 300 ]]; then
  echo "Performance APROVADA (p95 = $p95_val ms < 300 ms)"
else
  echo "AVISO: p95 acima de 300 ms ($p95_val ms)"
fi
