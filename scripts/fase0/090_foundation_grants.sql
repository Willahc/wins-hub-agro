-- Grants separados: exige nomes de papéis explicitamente revisados.
\set ON_ERROR_STOP on
\if :{?foundation_app_role}
\else
  \echo 'foundation_app_role is required'
  \quit 3
\endif
\if :{?foundation_readonly_role}
\else
  \echo 'foundation_readonly_role is required'
  \quit 3
\endif

BEGIN;
SET LOCAL lock_timeout = '5s';

REVOKE ALL ON SCHEMA foundation FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA foundation FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA foundation FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA foundation FROM PUBLIC;

GRANT USAGE ON SCHEMA foundation TO :"foundation_app_role", :"foundation_readonly_role";
GRANT SELECT ON ALL TABLES IN SCHEMA foundation TO :"foundation_app_role", :"foundation_readonly_role";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA foundation TO :"foundation_app_role";

GRANT INSERT, UPDATE, DELETE ON
    foundation.app_users,
    foundation.organizations,
    foundation.organization_memberships,
    foundation.operational_farms,
    foundation.farm_access,
    foundation.technical_parameters,
    foundation.formula_definitions,
    foundation.formula_versions
TO :"foundation_app_role";
GRANT INSERT ON foundation.audit_events TO :"foundation_app_role";

COMMIT;
