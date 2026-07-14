-- 002_climate_grants.sql — Grants mínimos para o módulo de Clima e Janelas Operacionais
BEGIN;

SET client_min_messages = warning;

GRANT USAGE ON SCHEMA climate TO wins_agro_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA climate TO wins_agro_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA climate TO wins_agro_app;

GRANT USAGE ON SCHEMA climate TO wins_agro_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA climate TO wins_agro_readonly;

GRANT USAGE, CREATE ON SCHEMA climate TO wins_agro_migrator;

ALTER DEFAULT PRIVILEGES IN SCHEMA climate
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO wins_agro_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA climate
    GRANT SELECT ON TABLES TO wins_agro_readonly;

ALTER DEFAULT PRIVILEGES IN SCHEMA climate
    GRANT USAGE, SELECT ON SEQUENCES TO wins_agro_app;

COMMIT;
