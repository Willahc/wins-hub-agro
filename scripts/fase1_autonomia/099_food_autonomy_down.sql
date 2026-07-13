-- 099_food_autonomy_down.sql — Rollback do módulo de Autonomia Alimentar
-- Sem CASCADE; remove em ordem inversa de dependência.
BEGIN;

SET client_min_messages = warning;

DROP TABLE IF EXISTS nutrition.food_autonomy_feed_items;
DROP TABLE IF EXISTS nutrition.food_autonomy_pasture_items;
DROP TABLE IF EXISTS nutrition.food_autonomy_herd_items;
DROP TABLE IF EXISTS nutrition.food_autonomy_scenarios;

DROP SCHEMA IF EXISTS nutrition;

COMMIT;
