-- Rollback estrutural da Fase 0A. DESTRUTIVO: somente se a migration 001 falhar
-- antes de qualquer adoção ou dado real, com aprovação e backup.
-- Usa RESTRICT implicitamente: dependência externa aborta e preserva tudo.
\set ON_ERROR_STOP on
BEGIN;
SET LOCAL lock_timeout = '5s';
DROP FUNCTION foundation.revoke_legacy_mapping(uuid,uuid,uuid,text,uuid,uuid,boolean);
DROP FUNCTION foundation.process_legacy_mapping(jsonb, boolean);
DROP TABLE foundation.legacy_farm_links;
DROP TABLE foundation.formula_versions;
DROP TABLE foundation.formula_definitions;
DROP TABLE foundation.technical_parameters;
DROP FUNCTION foundation.assert_compatible_units(text, text);
DROP TABLE foundation.units;
DROP TABLE foundation.audit_events;
DROP TABLE foundation.farm_access;
DROP TABLE foundation.operational_farms;
DROP TABLE foundation.organization_memberships;
DROP TABLE foundation.organizations;
DROP TABLE foundation.app_users;
DROP FUNCTION foundation.prevent_published_version_mutation();
DROP SCHEMA foundation;
COMMIT;
