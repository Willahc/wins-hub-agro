-- 099_climate_down.sql — Rollback do módulo de Clima e Janelas Operacionais
BEGIN;

DROP TABLE IF EXISTS climate.operational_window_evaluations;
DROP TABLE IF EXISTS climate.weather_snapshots;
DROP TABLE IF EXISTS climate.farm_weather_profiles;
DROP SCHEMA IF EXISTS climate;

COMMIT;
