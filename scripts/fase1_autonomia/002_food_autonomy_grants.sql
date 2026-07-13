-- 002_food_autonomy_grants.sql — Grants mínimos para o módulo de Autonomia Alimentar
-- PUBLIC sem CREATE; app com DML; readonly somente SELECT.
BEGIN;

SET client_min_messages = warning;

-- App precisa de USAGE no schema
GRANT USAGE ON SCHEMA nutrition TO wins_agro_app;

-- DML completo nas tabelas do módulo
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA nutrition TO wins_agro_app;

-- Sequences para INSERT
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA nutrition TO wins_agro_app;

-- Readonly apenas SELECT
GRANT USAGE ON SCHEMA nutrition TO wins_agro_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA nutrition TO wins_agro_readonly;

-- Migrador pode criar/modificar no schema
GRANT USAGE, CREATE ON SCHEMA nutrition TO wins_agro_migrator;

-- Garantir que futures tabelas recebam grants automaticamente
ALTER DEFAULT PRIVILEGES IN SCHEMA nutrition
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wins_agro_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA nutrition
    GRANT SELECT ON TABLES TO wins_agro_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA nutrition
    GRANT USAGE, SELECT ON SEQUENCES TO wins_agro_app;

COMMIT;
