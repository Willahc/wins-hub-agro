-- 001_climate_schema.sql — Schema do módulo de Clima e Janelas Operacionais
-- Migration idempotente, transacional, sem CASCADE no rollback.
BEGIN;

SET client_min_messages = warning;

CREATE SCHEMA IF NOT EXISTS climate;

-- ============================================================
-- Perfil climático da fazenda
-- ============================================================
CREATE TABLE IF NOT EXISTS climate.farm_weather_profiles (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    organization_id             bigint NOT NULL REFERENCES foundation.organizations(id),
    farm_id                     bigint NOT NULL REFERENCES foundation.operational_farms(id),
    latitude                    numeric(9,6) NOT NULL CHECK (latitude >= -90 AND latitude <= 90),
    longitude                   numeric(9,6) NOT NULL CHECK (longitude >= -180 AND longitude <= 180),
    timezone                    text NOT NULL DEFAULT 'America/Sao_Paulo',
    provider                    text NOT NULL DEFAULT 'open-meteo',
    enabled                     boolean NOT NULL DEFAULT true,
    refresh_interval_minutes    integer NOT NULL DEFAULT 20 CHECK (refresh_interval_minutes >= 10 AND refresh_interval_minutes <= 360),
    forecast_days               integer NOT NULL DEFAULT 7 CHECK (forecast_days >= 1 AND forecast_days <= 16),
    status                      text NOT NULL DEFAULT 'not_configured' CHECK (status IN ('active','stale','error','disabled','not_configured')),
    last_attempt_at             timestamptz,
    last_success_at             timestamptz,
    last_error_at               timestamptz,
    last_error_code             varchar(50),
    notes                       text NOT NULL DEFAULT '',
    created_by_user_id          bigint NOT NULL REFERENCES foundation.app_users(id),
    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now(),
    archived_at                 timestamptz,

    CONSTRAINT uq_climate_profile_public_id UNIQUE (public_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_climate_profile_farm
    ON climate.farm_weather_profiles (farm_id) WHERE archived_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_climate_profile_org
    ON climate.farm_weather_profiles (organization_id);

-- ============================================================
-- Snapshots climáticos normalizados
-- ============================================================
CREATE TABLE IF NOT EXISTS climate.weather_snapshots (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    organization_id             bigint NOT NULL REFERENCES foundation.organizations(id),
    farm_id                     bigint NOT NULL REFERENCES foundation.operational_farms(id),
    profile_id                  bigint NOT NULL REFERENCES climate.farm_weather_profiles(id),
    snapshot_type               text NOT NULL CHECK (snapshot_type IN ('current','hourly_forecast','daily_forecast','recent_history')),
    period_start                timestamptz,
    period_end                  timestamptz,
    payload_normalized          jsonb NOT NULL,
    provider                    text NOT NULL,
    provider_reference          varchar(200),
    normalization_version       text NOT NULL DEFAULT 'weather_normalization.v1',
    fetched_at                  timestamptz NOT NULL DEFAULT now(),
    expires_at                  timestamptz NOT NULL,
    stale_after                 timestamptz NOT NULL,
    checksum                    char(32) NOT NULL,
    created_at                  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_climate_snapshot_public_id UNIQUE (public_id)
);

CREATE INDEX IF NOT EXISTS ix_climate_snapshot_farm_type
    ON climate.weather_snapshots (farm_id, snapshot_type, fetched_at DESC);

CREATE INDEX IF NOT EXISTS ix_climate_snapshot_expires
    ON climate.weather_snapshots (expires_at);

CREATE INDEX IF NOT EXISTS ix_climate_snapshot_org
    ON climate.weather_snapshots (organization_id);

-- ============================================================
-- Avaliações de janelas operacionais
-- ============================================================
CREATE TABLE IF NOT EXISTS climate.operational_window_evaluations (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    organization_id             bigint NOT NULL REFERENCES foundation.organizations(id),
    farm_id                     bigint NOT NULL REFERENCES foundation.operational_farms(id),
    window_type                 text NOT NULL CHECK (window_type IN ('harvest_cut','ensiling','haymaking','pasture_management','field_operation','heat_attention')),
    period_start                timestamptz NOT NULL,
    period_end                  timestamptz NOT NULL,
    score                       numeric(5,1) NOT NULL CHECK (score >= 0 AND score <= 100),
    classification              text NOT NULL CHECK (classification IN ('favorable','attention','unfavorable','insufficient_data')),
    positive_factors            jsonb NOT NULL DEFAULT '[]'::jsonb,
    risk_factors                jsonb NOT NULL DEFAULT '[]'::jsonb,
    data_snapshot_ids           jsonb NOT NULL DEFAULT '[]'::jsonb,
    rule_version                text NOT NULL DEFAULT 'operational_windows.v1',
    evaluated_at                timestamptz NOT NULL DEFAULT now(),
    expires_at                  timestamptz,
    related_harvest_plan_id     bigint REFERENCES harvest.harvest_plans(id),
    created_at                  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_climate_evaluation_public_id UNIQUE (public_id)
);

CREATE INDEX IF NOT EXISTS ix_climate_eval_farm_type
    ON climate.operational_window_evaluations (farm_id, window_type, evaluated_at DESC);

CREATE INDEX IF NOT EXISTS ix_climate_eval_plan
    ON climate.operational_window_evaluations (related_harvest_plan_id);

CREATE INDEX IF NOT EXISTS ix_climate_eval_org
    ON climate.operational_window_evaluations (organization_id);

COMMIT;
