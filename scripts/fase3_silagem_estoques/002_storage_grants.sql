-- 002_storage_grants.sql — Grants mínimos para o módulo de Silagem e Estoques
-- PUBLIC sem CREATE; app com DML; readonly somente SELECT.
BEGIN;

SET client_min_messages = warning;

-- App precisa de USAGE no schema
GRANT USAGE ON SCHEMA storage TO wins_agro_app;

-- DML completo nas tabelas do módulo
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA storage TO wins_agro_app;

-- Sequences para INSERT
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA storage TO wins_agro_app;

-- Readonly apenas SELECT
GRANT USAGE ON SCHEMA storage TO wins_agro_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA storage TO wins_agro_readonly;

-- Migrador pode criar/modificar no schema
GRANT USAGE, CREATE ON SCHEMA storage TO wins_agro_migrator;

-- Garantir que futures tabelas recebam grants automaticamente
ALTER DEFAULT PRIVILEGES IN SCHEMA storage
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wins_agro_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA storage
    GRANT SELECT ON TABLES TO wins_agro_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA storage
    GRANT USAGE, SELECT ON SEQUENCES TO wins_agro_app;

COMMIT;
