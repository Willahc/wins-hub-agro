-- 099_harvest_down.sql — Rollback do módulo de Colheita e Silos
-- Rollback sem CASCADE para manter controle dos objetos removidos.
BEGIN;

DROP TABLE IF EXISTS harvest.harvest_storage_allocations;
DROP TABLE IF EXISTS harvest.harvest_plan_areas;
DROP TABLE IF EXISTS harvest.harvest_plans;
DROP SCHEMA IF EXISTS harvest;

COMMIT;
