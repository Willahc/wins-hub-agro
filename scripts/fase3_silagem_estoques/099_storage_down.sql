-- 099_storage_down.sql — Rollback do módulo de Silagem e Estoques
-- Sem CASCADE; remove em ordem inversa de dependência.
BEGIN;

SET client_min_messages = warning;

DROP TABLE IF EXISTS storage.feed_stock_movements;
DROP TABLE IF EXISTS storage.feed_lots;
DROP TABLE IF EXISTS storage.feed_storage_facilities;

DROP SCHEMA IF EXISTS storage;

COMMIT;
