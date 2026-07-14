-- 001_harvest_schema.sql — Schema do módulo de Colheita e Silos
-- Migration idempotente, transacional, sem CASCADE no rollback.
BEGIN;

SET client_min_messages = warning;

CREATE SCHEMA IF NOT EXISTS harvest;

-- ============================================================
-- Planos de colheita
-- ============================================================
CREATE TABLE IF NOT EXISTS harvest.harvest_plans (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    organization_id             bigint NOT NULL REFERENCES foundation.organizations(id),
    farm_id                     bigint NOT NULL REFERENCES foundation.operational_farms(id),
    name                        text NOT NULL,
    main_crop                   text NOT NULL CHECK (main_crop IN ('milho','sorgo','capim','cana-de-açúcar','aveia','azevém','outra')),
    purpose                     text NOT NULL CHECK (purpose IN ('silagem','feno','pré-secado','outro')),
    expected_start_date         date NOT NULL,
    expected_end_date           date NOT NULL,
    expected_field_loss_pct     numeric(5,2) NOT NULL CHECK (expected_field_loss_pct >= 0 AND expected_field_loss_pct <= 100),
    expected_ensiling_loss_pct  numeric(5,2) NOT NULL CHECK (expected_ensiling_loss_pct >= 0 AND expected_ensiling_loss_pct <= 100),
    expected_gross_natural_kg   numeric(12,2) NOT NULL DEFAULT 0 CHECK (expected_gross_natural_kg >= 0),
    expected_net_natural_kg     numeric(12,2) NOT NULL DEFAULT 0 CHECK (expected_net_natural_kg >= 0),
    expected_dm_kg              numeric(12,2) NOT NULL DEFAULT 0 CHECK (expected_dm_kg >= 0),
    actual_start_date           date,
    actual_end_date             date,
    actual_natural_kg           numeric(12,2) CHECK (actual_natural_kg IS NULL OR actual_natural_kg >= 0),
    actual_dm_pct               numeric(5,2) CHECK (actual_dm_pct IS NULL OR (actual_dm_pct >= 0 AND actual_dm_pct <= 100)),
    actual_loss_pct             numeric(5,2) CHECK (actual_loss_pct IS NULL OR (actual_loss_pct >= 0 AND actual_loss_pct <= 100)),
    status                      text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'planned', 'in_progress', 'completed', 'canceled', 'archived')),
    rule_version                text NOT NULL DEFAULT 'harvest_silos.v1',
    notes                       text NOT NULL DEFAULT '',
    completion_request_id       varchar(200) DEFAULT NULL,
    completion_payload_hash     char(64),
    completed_by_user_id        bigint REFERENCES foundation.app_users(id),
    completed_at                timestamptz,
    created_by_user_id          bigint NOT NULL REFERENCES foundation.app_users(id),
    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now(),
    archived_at                 timestamptz,

    CONSTRAINT uq_harvest_plan_public_id UNIQUE (public_id)
);

ALTER TABLE harvest.harvest_plans
    ADD COLUMN IF NOT EXISTS completion_payload_hash char(64);

CREATE UNIQUE INDEX IF NOT EXISTS uq_harvest_plan_completion_request
    ON harvest.harvest_plans (completion_request_id) WHERE completion_request_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_harvest_plan_farm
    ON harvest.harvest_plans (farm_id, status);

CREATE INDEX IF NOT EXISTS ix_harvest_plan_org
    ON harvest.harvest_plans (organization_id, status);

CREATE INDEX IF NOT EXISTS ix_harvest_plan_dates
    ON harvest.harvest_plans (expected_start_date, expected_end_date);

-- ============================================================
-- Áreas do plano
-- ============================================================
CREATE TABLE IF NOT EXISTS harvest.harvest_plan_areas (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    plan_id                     bigint NOT NULL REFERENCES harvest.harvest_plans(id) ON DELETE CASCADE,
    organization_id             bigint NOT NULL REFERENCES foundation.organizations(id),
    farm_id                     bigint NOT NULL REFERENCES foundation.operational_farms(id),
    name                        text NOT NULL,
    crop                        text NOT NULL,
    cultivar                    text NOT NULL DEFAULT '',
    area_ha                     numeric(10,2) NOT NULL CHECK (area_ha > 0),
    expected_yield_t_ha         numeric(10,2) NOT NULL CHECK (expected_yield_t_ha > 0),
    expected_dm_pct             numeric(5,2) NOT NULL CHECK (expected_dm_pct >= 0 AND expected_dm_pct <= 100),
    expected_harvest_date       date,
    calculated_gross_natural_kg numeric(12,2) NOT NULL DEFAULT 0 CHECK (calculated_gross_natural_kg >= 0),
    calculated_net_natural_kg   numeric(12,2) NOT NULL DEFAULT 0 CHECK (calculated_net_natural_kg >= 0),
    calculated_dm_kg            numeric(12,2) NOT NULL DEFAULT 0 CHECK (calculated_dm_kg >= 0),
    notes                       text NOT NULL DEFAULT '',
    display_order               integer NOT NULL DEFAULT 0,
    created_at                  timestamptz NOT NULL DEFAULT now(),
    archived_at                 timestamptz,

    CONSTRAINT uq_harvest_plan_area_public_id UNIQUE (public_id)
);

CREATE INDEX IF NOT EXISTS ix_harvest_plan_area_plan
    ON harvest.harvest_plan_areas (plan_id);

-- ============================================================
-- Alocações em silos / estruturas
-- ============================================================
CREATE TABLE IF NOT EXISTS harvest.harvest_storage_allocations (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    plan_id                     bigint NOT NULL REFERENCES harvest.harvest_plans(id) ON DELETE CASCADE,
    organization_id             bigint NOT NULL REFERENCES foundation.organizations(id),
    farm_id                     bigint NOT NULL REFERENCES foundation.operational_farms(id),
    facility_id                 bigint NOT NULL REFERENCES storage.feed_storage_facilities(id),
    expected_quantity_natural_kg numeric(12,2) NOT NULL CHECK (expected_quantity_natural_kg >= 0),
    actual_quantity_natural_kg  numeric(12,2) CHECK (actual_quantity_natural_kg IS NULL OR actual_quantity_natural_kg >= 0),
    expected_percentage         numeric(5,2) NOT NULL CHECK (expected_percentage >= 0 AND expected_percentage <= 100),
    capacity_snapshot_kg        numeric(12,2) CHECK (capacity_snapshot_kg IS NULL OR capacity_snapshot_kg >= 0),
    current_stock_snapshot_kg   numeric(12,2) CHECK (current_stock_snapshot_kg IS NULL OR current_stock_snapshot_kg >= 0),
    projected_occupancy_kg      numeric(12,2) CHECK (projected_occupancy_kg IS NULL OR projected_occupancy_kg >= 0),
    projected_occupancy_pct     numeric(5,2) CHECK (projected_occupancy_pct IS NULL OR projected_occupancy_pct >= 0),
    capacity_status             text NOT NULL DEFAULT 'available' CHECK (capacity_status IN ('available', 'near_capacity', 'over_capacity', 'unknown_capacity')),
    created_feed_lot_id         bigint REFERENCES storage.feed_lots(id),
    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now(),
    archived_at                 timestamptz,

    CONSTRAINT uq_harvest_storage_allocation_public_id UNIQUE (public_id)
);

CREATE INDEX IF NOT EXISTS ix_harvest_storage_alloc_plan
    ON harvest.harvest_storage_allocations (plan_id);

CREATE INDEX IF NOT EXISTS ix_harvest_storage_alloc_facility
    ON harvest.harvest_storage_allocations (facility_id);

COMMIT;
