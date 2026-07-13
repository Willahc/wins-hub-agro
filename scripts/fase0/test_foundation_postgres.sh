#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
TEST_DB="wins_agro_fase0b_test_db_${TIMESTAMP}_$$"
DB_USER="fase0_test"
DB_NAME="fase0_test"
IMAGE="${FASE0_TEST_POSTGRES_IMAGE:-}"

cleanup() {
  docker rm -f "$TEST_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

if [[ -z "$IMAGE" ]]; then
  IMAGE="$(docker inspect wins_agro_v1-db-1 --format '{{.Config.Image}}')"
fi
docker image inspect "$IMAGE" >/dev/null
if [[ "$IMAGE" != *"16"* ]]; then
  echo "ERRO: o harness exige uma imagem PostgreSQL 16 local" >&2
  exit 2
fi

docker run -d --rm \
  --name "$TEST_DB" \
  --network none \
  --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=512m \
  --memory 768m \
  --cpus 1 \
  -e POSTGRES_USER="$DB_USER" \
  -e POSTGRES_PASSWORD=fase0_test_password_synthetic \
  -e POSTGRES_DB="$DB_NAME" \
  "$IMAGE" >/dev/null

ready=0
for _attempt in $(seq 1 30); do
  if docker exec "$TEST_DB" psql -X -U "$DB_USER" -d "$DB_NAME" -Atc 'SELECT 1' >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 1
done
if [[ "$ready" -ne 1 ]]; then
  docker logs --tail=100 "$TEST_DB"
  exit 3
fi

network_mode="$(docker inspect "$TEST_DB" --format '{{.HostConfig.NetworkMode}}')"
port_bindings="$(docker inspect "$TEST_DB" --format '{{json .HostConfig.PortBindings}}')"
persistent_mounts="$(docker inspect "$TEST_DB" --format '{{json .Mounts}}')"
tmpfs_config="$(docker inspect "$TEST_DB" --format '{{json .HostConfig.Tmpfs}}')"
[[ "$network_mode" == "none" ]] || { echo "ERRO: rede Docker inválida" >&2; exit 4; }
[[ "$port_bindings" == "null" || "$port_bindings" == "{}" ]] || { echo "ERRO: porta publicada" >&2; exit 4; }
[[ "$persistent_mounts" == "[]" ]] || { echo "ERRO: volume persistente detectado" >&2; exit 4; }
[[ "$tmpfs_config" == *"/var/lib/postgresql/data"* ]] || { echo "ERRO: tmpfs ausente" >&2; exit 4; }

psql_admin() {
  docker exec -i "$TEST_DB" psql -X -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" "$@"
}
psql_owner() {
  docker exec -e PGOPTIONS='-c role=phase0_owner' -i "$TEST_DB" \
    psql -X -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" "$@"
}
apply_owner_file() {
  psql_owner < "$ROOT/scripts/fase0/$1"
}
mapping_call() {
  local mapping_json="$1"
  local apply_value="$2"
  printf 'SELECT foundation.process_legacy_mapping(:\047mapping_json\047::jsonb, %s);\n' "$apply_value" \
    | psql_owner -At -v mapping_json="$mapping_json"
}

psql_admin <<'SQL'
CREATE ROLE phase0_owner NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE phase0_app NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE phase0_readonly NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
GRANT phase0_owner, phase0_app, phase0_readonly TO fase0_test;
GRANT CREATE ON DATABASE fase0_test TO phase0_owner;
SET ROLE phase0_owner;
CREATE SCHEMA fazenda;
-- Os SQL versionados existentes referenciam fazenda.cliente(id) como integer.
CREATE TABLE fazenda.cliente (id integer PRIMARY KEY, nome text NOT NULL);
INSERT INTO fazenda.cliente VALUES
  (1001, 'Cliente Legado 1001'),
  (2001, 'Cliente Legado 2001');
CREATE SCHEMA external_synthetic;
CREATE TABLE external_synthetic.sentinel (id integer PRIMARY KEY);
INSERT INTO external_synthetic.sentinel VALUES (1);
RESET ROLE;
SQL

apply_owner_file 001_foundation_schema.sql
apply_owner_file 002_reference_units.sql
apply_owner_file 020_legacy_mapping_schema.sql
apply_owner_file 030_legacy_bootstrap_idempotent.sql
apply_owner_file 040_legacy_bootstrap_rollback.sql
psql_owner -v foundation_app_role=phase0_app -v foundation_readonly_role=phase0_readonly \
  < "$ROOT/scripts/fase0/090_foundation_grants.sql"
if apply_owner_file 001_foundation_schema.sql >/dev/null 2>&1; then
  echo "ERRO: migration estrutural reaplicada" >&2
  exit 5
fi
apply_owner_file 002_reference_units.sql >/dev/null
[[ "$(psql_owner -Atc 'SELECT count(*) FROM foundation.units')" == "23" ]]

MAPPING="$(jq -c '. + {audit_public_ids:{
  user:"81000000-0000-4000-8000-000000000001",
  organization:"82000000-0000-4000-8000-000000000001",
  membership:"83000000-0000-4000-8000-000000000001",
  farm:"84000000-0000-4000-8000-000000000001",
  access:"85000000-0000-4000-8000-000000000001",
  link:"86000000-0000-4000-8000-000000000001"
}}' "$ROOT/scripts/fase0/examples/legacy_mapping.synthetic.json")"

count_before="$(psql_owner -Atc "SELECT count(*) FROM foundation.organizations")"
dry_report="$(mapping_call "$MAPPING" false)"
[[ "$(jq -r '.status' <<<"$dry_report")" == "ready" ]]
[[ "$(psql_owner -Atc "SELECT count(*) FROM foundation.organizations")" == "$count_before" ]]

apply_report="$(mapping_call "$MAPPING" true)"
[[ "$(jq -r '.status' <<<"$apply_report")" == "applied" ]]
reapply_report="$(mapping_call "$MAPPING" true)"
[[ "$(jq -r '.created | to_entries | map(.value) | add' <<<"$reapply_report")" == "0" ]]

role_conflict="$(jq -c '.role="admin"' <<<"$MAPPING")"
blocked_report="$(mapping_call "$role_conflict" false)"
[[ "$(jq -r '.status' <<<"$blocked_report")" == "blocked" ]]
if mapping_call "$role_conflict" true >/dev/null 2>&1; then
  echo "ERRO: elevação de papel deveria falhar" >&2
  exit 5
fi
[[ "$(psql_owner -Atc "SELECT role FROM foundation.organization_memberships WHERE public_id='30000000-0000-4000-8000-000000000001'")" == "owner" ]]

org_conflict="$(jq -c '.organization_public_id="20000000-0000-4000-8000-000000000099" | .organization_slug="organizacao-beta" | .organization_name="Organização Beta"' <<<"$MAPPING")"
if mapping_call "$org_conflict" true >/dev/null 2>&1; then
  echo "ERRO: troca de organização deveria falhar" >&2
  exit 6
fi

psql_owner <<'SQL'
INSERT INTO foundation.app_users(public_id,auth_subject,display_name)
VALUES ('10000000-0000-4000-8000-000000000002','synthetic-user-b','Usuário Sintético B');
INSERT INTO foundation.organizations(public_id,name,slug,created_by)
SELECT '20000000-0000-4000-8000-000000000002','Organização Beta','organizacao-beta',id
FROM foundation.app_users WHERE public_id='10000000-0000-4000-8000-000000000002';
INSERT INTO foundation.organization_memberships(public_id,organization_id,user_id,role,status,created_by)
SELECT '30000000-0000-4000-8000-000000000002',o.id,u.id,'owner','active',u.id
FROM foundation.organizations o CROSS JOIN foundation.app_users u
WHERE o.public_id='20000000-0000-4000-8000-000000000002'
  AND u.public_id='10000000-0000-4000-8000-000000000002';
INSERT INTO foundation.operational_farms(public_id,organization_id,name,created_by)
SELECT '40000000-0000-4000-8000-000000000002',o.id,'Fazenda Sintética B',u.id
FROM foundation.organizations o CROSS JOIN foundation.app_users u
WHERE o.public_id='20000000-0000-4000-8000-000000000002'
  AND u.public_id='10000000-0000-4000-8000-000000000002';

DO $$
BEGIN
  BEGIN
    INSERT INTO foundation.organization_memberships
      (public_id, organization_id, user_id, role, status)
    SELECT '91000000-0000-4000-8000-000000000001', o.id, u.id, 'invalid', 'active'
      FROM foundation.organizations o CROSS JOIN foundation.app_users u LIMIT 1;
    RAISE EXCEPTION 'invalid role accepted';
  EXCEPTION WHEN check_violation THEN NULL; END;
  BEGIN
    INSERT INTO foundation.farm_access
      (public_id, organization_id, farm_id, membership_id, access_level, status)
    SELECT '92000000-0000-4000-8000-000000000001', ob.id, fa.id, ma.id, 'read', 'active'
      FROM foundation.organizations oa
      JOIN foundation.organization_memberships ma ON ma.organization_id=oa.id
      CROSS JOIN foundation.organizations ob
      JOIN foundation.operational_farms fa ON fa.organization_id=ob.id
     WHERE oa.id<>ob.id LIMIT 1;
    RAISE EXCEPTION 'cross organization farm access accepted';
  EXCEPTION WHEN foreign_key_violation THEN NULL; END;
  BEGIN
    INSERT INTO foundation.technical_parameters
      (public_id,code,name,description,value_numeric,unit_code,value_type,origin,scope,
       valid_from,valid_to,version,status,created_by)
    SELECT '93000000-0000-4000-8000-000000000001','synthetic.invalid','Inválido',
      'Somente teste sintético',1,'fraction','decimal','synthetic','global',now(),now(),1,'draft',id
      FROM foundation.app_users LIMIT 1;
    RAISE EXCEPTION 'invalid validity accepted';
  EXCEPTION WHEN check_violation THEN NULL; END;
  BEGIN
    INSERT INTO foundation.audit_events
      (public_id,occurred_at,request_id,action,entity_type,result,source,metadata)
    VALUES ('93500000-0000-4000-8000-000000000001',now(),'synthetic-sensitive',
            'synthetic.invalid','synthetic','failed','synthetic_test','{"token":"blocked"}');
    RAISE EXCEPTION 'sensitive audit metadata accepted';
  EXCEPTION WHEN check_violation THEN NULL; END;
END;
$$;

SELECT foundation.assert_compatible_units('kg','t');
DO $$ BEGIN
  BEGIN
    PERFORM foundation.assert_compatible_units('kg_green_mass','kg_dm');
    RAISE EXCEPTION 'incompatible units accepted';
  EXCEPTION WHEN invalid_parameter_value THEN NULL; END;
END $$;

INSERT INTO foundation.formula_definitions (public_id,code,name,domain,description)
VALUES ('94000000-0000-4000-8000-000000000001','synthetic.formula','Fórmula Sintética','financeiro','Somente teste sintético');
INSERT INTO foundation.formula_versions
  (public_id,formula_id,version,implementation_id,input_units,output_unit,assumptions,
   valid_from,status,created_by,checksum)
SELECT '95000000-0000-4000-8000-000000000001',f.id,1,'synthetic.v1','{}','brl',
  'Somente teste sintético',now(),'published',u.id,repeat('a',64)
FROM foundation.formula_definitions f CROSS JOIN foundation.app_users u
WHERE f.code='synthetic.formula' LIMIT 1;
DO $$ BEGIN
  BEGIN
    UPDATE foundation.formula_versions SET implementation_id='changed' WHERE version=1;
    RAISE EXCEPTION 'published formula updated';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM = 'published formula updated' THEN RAISE; END IF;
  END;
END $$;
INSERT INTO foundation.formula_versions
  (public_id,formula_id,version,implementation_id,input_units,output_unit,assumptions,
   valid_from,status,created_by,checksum)
SELECT '95000000-0000-4000-8000-000000000002',f.id,2,'synthetic.v2','{}','brl',
  'Somente teste sintético versão dois',now(),'draft',u.id,repeat('b',64)
FROM foundation.formula_definitions f CROSS JOIN foundation.app_users u
WHERE f.code='synthetic.formula' LIMIT 1;
SQL

psql_admin <<'SQL'
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_namespace n,
      LATERAL aclexplode(coalesce(n.nspacl,acldefault('n',n.nspowner))) acl
    WHERE n.nspname='foundation' AND acl.grantee=0
  ) THEN
    RAISE EXCEPTION 'PUBLIC privilege detected';
  END IF;
  IF EXISTS (
    SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace,
      LATERAL aclexplode(coalesce(c.relacl,acldefault('r',c.relowner))) acl
    WHERE n.nspname='foundation' AND c.relkind IN ('r','S') AND acl.grantee=0
  ) THEN RAISE EXCEPTION 'PUBLIC table privilege detected'; END IF;
  IF EXISTS (
    SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace,
      LATERAL aclexplode(coalesce(p.proacl,acldefault('f',p.proowner))) acl
    WHERE n.nspname='foundation' AND acl.grantee=0
  ) THEN RAISE EXCEPTION 'PUBLIC function privilege detected'; END IF;
  IF has_schema_privilege('phase0_app','foundation','CREATE') THEN RAISE EXCEPTION 'app can create'; END IF;
  IF NOT has_table_privilege('phase0_app','foundation.audit_events','INSERT') THEN RAISE EXCEPTION 'app lacks audit insert'; END IF;
  IF has_table_privilege('phase0_app','foundation.audit_events','UPDATE') THEN RAISE EXCEPTION 'app can update audit'; END IF;
  IF NOT has_table_privilege('phase0_readonly','foundation.organizations','SELECT') THEN RAISE EXCEPTION 'readonly lacks select'; END IF;
  IF has_table_privilege('phase0_readonly','foundation.organizations','INSERT') THEN RAISE EXCEPTION 'readonly can insert'; END IF;
  IF has_function_privilege('phase0_app','foundation.process_legacy_mapping(jsonb,boolean)','EXECUTE') THEN
    RAISE EXCEPTION 'app can execute bootstrap';
  END IF;
  IF has_function_privilege('phase0_app','foundation.revoke_legacy_mapping(uuid,uuid,uuid,text,uuid,uuid,boolean)','EXECUTE') THEN
    RAISE EXCEPTION 'app can execute bootstrap rollback';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname IN ('phase0_app','phase0_readonly')
             AND (rolsuper OR rolcreatedb OR rolcreaterole)) THEN RAISE EXCEPTION 'excess role attribute'; END IF;
END $$;
SQL

rollback_dry="$(psql_owner -Atc "SELECT foundation.revoke_legacy_mapping(
 '60000000-0000-4000-8000-000000000001','70000000-0000-4000-8000-000000000001',
 '10000000-0000-4000-8000-000000000001','Rollback exclusivamente sintético e revisado.',
 '87000000-0000-4000-8000-000000000001','88000000-0000-4000-8000-000000000001',false)")"
[[ "$(jq -r '.mode' <<<"$rollback_dry")" == "dry-run" ]]
[[ "$(psql_owner -Atc "SELECT status FROM foundation.legacy_farm_links WHERE public_id='60000000-0000-4000-8000-000000000001'")" == "active" ]]
rollback_apply="$(psql_owner -Atc "SELECT foundation.revoke_legacy_mapping(
 '60000000-0000-4000-8000-000000000001','70000000-0000-4000-8000-000000000001',
 '10000000-0000-4000-8000-000000000001','Rollback exclusivamente sintético e revisado.',
 '87000000-0000-4000-8000-000000000001','88000000-0000-4000-8000-000000000001',true)")"
[[ "$(jq -r '.status' <<<"$rollback_apply")" == "revoked" ]]
[[ "$(psql_owner -Atc "SELECT status FROM foundation.legacy_farm_links WHERE public_id='60000000-0000-4000-8000-000000000001'")" == "revoked" ]]

# Volume moderado exclusivamente sintético.
psql_owner <<'SQL'
INSERT INTO fazenda.cliente(id,nome)
SELECT 100000+i, 'Cliente Legado Sintético '||i FROM generate_series(1,5000) i;
INSERT INTO foundation.app_users(public_id,auth_subject,display_name)
SELECT ('a2000000-0000-4000-8000-'||lpad(i::text,12,'0'))::uuid,
       'synthetic-load-user-'||i, 'Usuário Sintético '||i FROM generate_series(1,500) i;
INSERT INTO foundation.organizations(public_id,name,slug)
SELECT ('a1000000-0000-4000-8000-'||lpad(i::text,12,'0'))::uuid,
       'Organização Sintética '||i, 'organizacao-sintetica-'||i FROM generate_series(1,100) i;
INSERT INTO foundation.organization_memberships(public_id,organization_id,user_id,role,status)
SELECT ('a3000000-0000-4000-8000-'||lpad(i::text,12,'0'))::uuid, o.id, u.id, 'technician','active'
FROM generate_series(1,1000) i
JOIN foundation.app_users u ON u.public_id=('a2000000-0000-4000-8000-'||lpad((((i-1)%500)+1)::text,12,'0'))::uuid
JOIN foundation.organizations o ON o.public_id=('a1000000-0000-4000-8000-'||lpad(((((i-1)%100)+((i-1)/500))%100+1)::text,12,'0'))::uuid;
INSERT INTO foundation.operational_farms(public_id,organization_id,name)
SELECT ('a4000000-0000-4000-8000-'||lpad(i::text,12,'0'))::uuid, o.id, 'Fazenda Sintética '||i
FROM generate_series(1,5000) i
JOIN foundation.organizations o ON o.public_id=('a1000000-0000-4000-8000-'||lpad((((i-1)%100)+1)::text,12,'0'))::uuid;
INSERT INTO foundation.farm_access(public_id,organization_id,farm_id,membership_id,access_level,status)
SELECT ('a5000000-0000-4000-8000-'||lpad(row_number() OVER (ORDER BY f.id)::text,12,'0'))::uuid,
       f.organization_id,f.id,m.id,'read','active'
FROM foundation.operational_farms f
JOIN LATERAL (
  SELECT id FROM foundation.organization_memberships m
   WHERE m.organization_id=f.organization_id AND m.status='active' ORDER BY id LIMIT 1
) m ON true
WHERE f.public_id::text LIKE 'a4000000-%';
INSERT INTO foundation.legacy_farm_links
  (public_id,source_schema,source_table,legacy_client_id,organization_id,operational_farm_id,
   granted_farm_access_id,mapping_version,idempotency_key,origin,justification,approved_by,approved_at)
SELECT ('a6000000-0000-4000-8000-'||lpad(row_number() OVER (ORDER BY f.id)::text,12,'0'))::uuid,
       'fazenda','cliente',100000+row_number() OVER (ORDER BY f.id),f.organization_id,f.id,a.id,1,
       ('a6100000-0000-4000-8000-'||lpad(row_number() OVER (ORDER BY f.id)::text,12,'0'))::uuid,
       'explicit_synthetic_review','Justificativa sintética para ensaio de volume',u.id,now()
FROM foundation.operational_farms f
JOIN foundation.farm_access a ON a.farm_id=f.id AND a.status='active'
JOIN LATERAL (SELECT user_id id FROM foundation.organization_memberships m
               WHERE m.organization_id=f.organization_id ORDER BY id LIMIT 1) u ON true
WHERE f.public_id::text LIKE 'a4000000-%';
INSERT INTO foundation.audit_events
  (public_id,occurred_at,request_id,organization_id,action,entity_type,result,source)
SELECT ('a7000000-0000-4000-8000-'||lpad(i::text,12,'0'))::uuid, now()-(i||' seconds')::interval,
       'synthetic-load-'||i,o.id,'synthetic.load','synthetic_entity','success','synthetic_test'
FROM generate_series(1,10000) i
JOIN foundation.organizations o ON o.public_id=('a1000000-0000-4000-8000-'||lpad((((i-1)%100)+1)::text,12,'0'))::uuid;
ANALYZE foundation.organization_memberships;
ANALYZE foundation.operational_farms;
ANALYZE foundation.farm_access;
ANALYZE foundation.legacy_farm_links;
ANALYZE foundation.audit_events;
SQL

psql_owner <<'SQL'
EXPLAIN (COSTS OFF) SELECT m.id FROM foundation.organization_memberships m
JOIN foundation.organizations o ON o.id=m.organization_id
WHERE m.user_id=42 AND o.public_id='a1000000-0000-4000-8000-000000000001' AND m.status='active';
EXPLAIN (COSTS OFF) SELECT id FROM foundation.farm_access
WHERE membership_id=42 AND farm_id=42 AND status='active';
EXPLAIN (COSTS OFF) SELECT f.id FROM foundation.operational_farms f
JOIN foundation.farm_access a ON a.farm_id=f.id WHERE a.membership_id=42 AND a.status='active';
EXPLAIN (COSTS OFF) SELECT id FROM foundation.legacy_farm_links
WHERE source_schema='fazenda' AND source_table='cliente' AND legacy_client_id=100042;
EXPLAIN (COSTS OFF) SELECT * FROM foundation.audit_events
WHERE organization_id=2 AND occurred_at>=now()-interval '1 day' ORDER BY occurred_at DESC;
EXPLAIN (COSTS OFF) SELECT * FROM foundation.technical_parameters
WHERE code='synthetic.rate' AND status='published' ORDER BY valid_from DESC LIMIT 1;
EXPLAIN (COSTS OFF) SELECT * FROM foundation.formula_versions
WHERE formula_id=1 AND status='published' ORDER BY version DESC LIMIT 1;
SQL

psql_owner -Atc "SELECT jsonb_build_object(
 'organizations',(SELECT count(*) FROM foundation.organizations),
 'users',(SELECT count(*) FROM foundation.app_users),
 'memberships',(SELECT count(*) FROM foundation.organization_memberships),
 'farms',(SELECT count(*) FROM foundation.operational_farms),
 'farm_accesses',(SELECT count(*) FROM foundation.farm_access),
 'legacy_links',(SELECT count(*) FROM foundation.legacy_farm_links),
 'audit_events',(SELECT count(*) FROM foundation.audit_events));"

psql_owner <<'SQL'
CREATE VIEW external_synthetic.foundation_probe AS SELECT count(*) n FROM foundation.organizations;
SQL
if apply_owner_file 099_foundation_schema_down.sql >/dev/null 2>&1; then
  echo "ERRO: rollback deveria recusar dependência externa" >&2
  exit 7
fi
[[ "$(psql_owner -Atc "SELECT count(*) FROM information_schema.schemata WHERE schema_name='foundation'")" == "1" ]]
psql_owner -c 'DROP VIEW external_synthetic.foundation_probe' >/dev/null
apply_owner_file 099_foundation_schema_down.sql
[[ "$(psql_admin -Atc "SELECT count(*) FROM information_schema.schemata WHERE schema_name='foundation'")" == "0" ]]
[[ "$(psql_admin -Atc "SELECT count(*) FROM external_synthetic.sentinel")" == "1" ]]
[[ "$(psql_admin -Atc "SELECT count(*) FROM fazenda.cliente")" -ge "2" ]]

cleanup
trap - EXIT INT TERM
if docker inspect "$TEST_DB" >/dev/null 2>&1; then
  echo "ERRO: container descartável não foi removido" >&2
  exit 8
fi
echo "FASE0B_POSTGRES_OK image=$IMAGE isolation=network-none,tmpfs,no-published-port container_removed=true"
