-- 001_pasture_schema.sql — Schema do módulo de Pasto Vivo
-- Migration idempotente, transacional, sem CASCADE no rollback.
BEGIN;

SET client_min_messages = warning;

CREATE SCHEMA IF NOT EXISTS pasture;

-- ============================================================
-- Tabela principal: piquetes
-- ============================================================
CREATE TABLE IF NOT EXISTS pasture.paddocks (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id               uuid NOT NULL DEFAULT gen_random_uuid(),
    organization_id         bigint NOT NULL REFERENCES foundation.organizations(id),
    farm_id                 bigint NOT NULL REFERENCES foundation.operational_farms(id),
    name                    text NOT NULL,
    code                    text NOT NULL DEFAULT '',
    forage_species          text NOT NULL DEFAULT '',
    cultivar                text NOT NULL DEFAULT '',
    area_ha                 numeric(10,4) NOT NULL CHECK (area_ha > 0),
    target_entry_height_cm  numeric(6,2) CHECK (target_entry_height_cm IS NULL OR target_entry_height_cm > 0),
    target_exit_height_cm   numeric(6,2) CHECK (target_exit_height_cm IS NULL OR target_exit_height_cm > 0),
    planned_rest_days       integer NOT NULL DEFAULT 0 CHECK (planned_rest_days >= 0),
    default_utilization_pct numeric(5,2) NOT NULL DEFAULT 50
                            CHECK (default_utilization_pct >= 0 AND default_utilization_pct <= 100),
    manual_status           text NOT NULL DEFAULT 'no_measurement'
                            CHECK (manual_status IN ('ready','grazing','resting','attention','unavailable','inactive','no_measurement')),
    active                  boolean NOT NULL DEFAULT true,
    notes                   text NOT NULL DEFAULT '',
    created_by_user_id      bigint NOT NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    archived_at             timestamptz,

    CONSTRAINT uq_paddock_public_id UNIQUE (public_id)
);

CREATE UNIQUE INDEX uq_paddock_code_per_farm
    ON pasture.paddocks (farm_id, code) WHERE code != '' AND archived_at IS NULL;

CREATE INDEX ix_paddock_farm
    ON pasture.paddocks (farm_id, active);
CREATE INDEX ix_paddock_org
    ON pasture.paddocks (organization_id, active);
CREATE INDEX ix_paddock_status
    ON pasture.paddocks (manual_status) WHERE archived_at IS NULL;

-- ============================================================
-- Medições de piquete
-- ============================================================
CREATE TABLE IF NOT EXISTS pasture.paddock_measurements (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id               uuid NOT NULL DEFAULT gen_random_uuid(),
    paddock_id              bigint NOT NULL REFERENCES pasture.paddocks(id) ON DELETE CASCADE,
    organization_id         bigint NOT NULL,
    farm_id                 bigint NOT NULL,
    measured_at             timestamptz NOT NULL DEFAULT now(),
    average_height_cm       numeric(6,2) CHECK (average_height_cm IS NULL OR (average_height_cm >= 0 AND average_height_cm <= 500)),
    available_dm_kg_ha      numeric(10,2) NOT NULL CHECK (available_dm_kg_ha >= 0),
    utilization_pct         numeric(5,2) NOT NULL DEFAULT 50
                            CHECK (utilization_pct >= 0 AND utilization_pct <= 100),
    calculated_total_dm_kg  numeric(12,2) NOT NULL DEFAULT 0,
    calculated_usable_dm_kg numeric(12,2) NOT NULL DEFAULT 0,
    measurement_method      text NOT NULL DEFAULT 'visual'
                            CHECK (measurement_method IN ('visual','ruler','rising_plate','field_sampling','external','other')),
    rule_version            text NOT NULL DEFAULT 'pasture_live.v1',
    notes                   text NOT NULL DEFAULT '',
    measured_by_user_id     bigint NOT NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    archived_at             timestamptz,

    CONSTRAINT uq_measurement_public_id UNIQUE (public_id)
);

CREATE INDEX ix_measurement_paddock
    ON pasture.paddock_measurements (paddock_id, measured_at DESC);
CREATE INDEX ix_measurement_farm
    ON pasture.paddock_measurements (farm_id, measured_at DESC);

-- ============================================================
-- Eventos de piquete (ciclos de pastejo/descanso)
-- ============================================================
CREATE TABLE IF NOT EXISTS pasture.paddock_events (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id               uuid NOT NULL DEFAULT gen_random_uuid(),
    paddock_id              bigint NOT NULL REFERENCES pasture.paddocks(id) ON DELETE CASCADE,
    organization_id         bigint NOT NULL,
    farm_id                 bigint NOT NULL,
    event_type              text NOT NULL CHECK (event_type IN (
                                'grazing_started','grazing_finished',
                                'rest_started','released',
                                'marked_unavailable','reactivated','status_adjusted')),
    event_at                timestamptz NOT NULL DEFAULT now(),
    expected_end_at         timestamptz,
    actual_end_at           timestamptz,
    head_count              integer CHECK (head_count IS NULL OR head_count >= 0),
    average_weight_kg       numeric(8,2) CHECK (average_weight_kg IS NULL OR average_weight_kg > 0),
    management_group_name   text NOT NULL DEFAULT '',
    notes                   text NOT NULL DEFAULT '',
    created_by_user_id      bigint NOT NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    archived_at             timestamptz,

    CONSTRAINT uq_event_public_id UNIQUE (public_id)
);

CREATE INDEX ix_event_paddock
    ON pasture.paddock_events (paddock_id, event_at DESC);
CREATE INDEX ix_event_farm
    ON pasture.paddock_events (farm_id, event_at DESC);

COMMIT;
