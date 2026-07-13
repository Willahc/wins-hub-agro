-- 099_pasture_down.sql — Rollback do módulo de Pasto Vivo
-- Sem CASCADE; remove em ordem inversa de dependência.
BEGIN;

SET client_min_messages = warning;

DROP TABLE IF EXISTS pasture.paddock_events;
DROP TABLE IF EXISTS pasture.paddock_measurements;
DROP TABLE IF EXISTS pasture.paddocks;

DROP SCHEMA IF EXISTS pasture;

COMMIT;
