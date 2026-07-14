-- 001_storage_schema.sql — Schema do módulo de Silagem e Estoques
-- Migration idempotente, transacional, sem CASCADE no rollback.
BEGIN;

SET client_min_messages = warning;

CREATE SCHEMA IF NOT EXISTS storage;

-- ============================================================
-- Estruturas de armazenamento
-- ============================================================
CREATE TABLE IF NOT EXISTS storage.feed_storage_facilities (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id               uuid NOT NULL DEFAULT gen_random_uuid(),
    organization_id         bigint NOT NULL REFERENCES foundation.organizations(id),
    farm_id                 bigint NOT NULL REFERENCES foundation.operational_farms(id),
    name                    text NOT NULL,
    code                    text NOT NULL DEFAULT '',
    facility_type           text NOT NULL CHECK (facility_type IN (
                                'silo_trincheira','silo_superficie','silo_bolsa',
                                'silo_torre','deposito_feno','galpao',
                                'deposito_concentrado','deposito_subproduto',
                                'outro')),
    capacity_natural_kg     numeric(12,2) CHECK (capacity_natural_kg IS NULL OR capacity_natural_kg > 0),
    preferred_display_unit  text NOT NULL DEFAULT 'kg',
    location_description    text NOT NULL DEFAULT '',
    active                  boolean NOT NULL DEFAULT true,
    notes                   text NOT NULL DEFAULT '',
    created_by_user_id      bigint NOT NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    archived_at             timestamptz,

    CONSTRAINT uq_facility_public_id UNIQUE (public_id)
);

CREATE UNIQUE INDEX uq_facility_code_per_farm
    ON storage.feed_storage_facilities (farm_id, code) WHERE code != '' AND archived_at IS NULL;

CREATE INDEX ix_facility_farm
    ON storage.feed_storage_facilities (farm_id, active);
CREATE INDEX ix_facility_org
    ON storage.feed_storage_facilities (organization_id, active);

-- ============================================================
-- Lotes de alimento
-- ============================================================
CREATE TABLE IF NOT EXISTS storage.feed_lots (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    organization_id             bigint NOT NULL,
    farm_id                     bigint NOT NULL,
    facility_id                 bigint NOT NULL REFERENCES storage.feed_storage_facilities(id),
    name                        text NOT NULL,
    feed_type                   text NOT NULL CHECK (feed_type IN (
                                    'silagem_milho','silagem_sorgo','silagem_capim',
                                    'silagem_cana','feno','pre_secado','concentrado',
                                    'suplemento_proteico','suplemento_mineral','subproduto',
                                    'polpa_citrica','caroco_algodao','casquinha_soja','outro')),
    custom_feed_type            text NOT NULL DEFAULT '',
    production_date             date,
    ensiling_date               date,
    opened_at                   timestamptz,
    source_description          text NOT NULL DEFAULT '',
    initial_quantity_natural_kg numeric(12,2) NOT NULL CHECK (initial_quantity_natural_kg >= 0),
    current_quantity_natural_kg numeric(12,2) NOT NULL DEFAULT 0 CHECK (current_quantity_natural_kg >= 0),
    dry_matter_pct              numeric(5,2) NOT NULL CHECK (dry_matter_pct >= 0 AND dry_matter_pct <= 100),
    utilization_pct             numeric(5,2) NOT NULL DEFAULT 100 CHECK (utilization_pct >= 0 AND utilization_pct <= 100),
    current_physical_dm_kg      numeric(12,2) NOT NULL DEFAULT 0 CHECK (current_physical_dm_kg >= 0),
    current_usable_dm_kg        numeric(12,2) NOT NULL DEFAULT 0 CHECK (current_usable_dm_kg >= 0),
    initial_total_cost          numeric(12,2) CHECK (initial_total_cost IS NULL OR initial_total_cost >= 0),
    average_cost_per_natural_kg numeric(10,4) CHECK (average_cost_per_natural_kg IS NULL OR average_cost_per_natural_kg >= 0),
    current_inventory_value     numeric(12,2) NOT NULL DEFAULT 0 CHECK (current_inventory_value >= 0),
    cost_per_usable_dm_kg       numeric(10,4) CHECK (cost_per_usable_dm_kg IS NULL OR cost_per_usable_dm_kg >= 0),
    planned_daily_use_dm_kg     numeric(10,2) CHECK (planned_daily_use_dm_kg IS NULL OR planned_daily_use_dm_kg >= 0),
    status                      text NOT NULL DEFAULT 'available'
                                    CHECK (status IN ('available','reserved','opened','depleted','quarantined','archived')),
    rule_version                text NOT NULL DEFAULT 'feed_inventory.v1',
    notes                       text NOT NULL DEFAULT '',
    created_by_user_id          bigint NOT NULL,
    created_at                  timestamptz NOT NULL DEFAULT now(),
    updated_at                  timestamptz NOT NULL DEFAULT now(),
    archived_at                 timestamptz,

    CONSTRAINT uq_lot_public_id UNIQUE (public_id)
);

CREATE INDEX ix_lot_farm
    ON storage.feed_lots (farm_id, status);
CREATE INDEX ix_lot_facility
    ON storage.feed_lots (facility_id, status);
CREATE INDEX ix_lot_feed_type
    ON storage.feed_lots (feed_type) WHERE archived_at IS NULL;
CREATE INDEX ix_lot_status
    ON storage.feed_lots (status) WHERE archived_at IS NULL;
CREATE INDEX ix_lot_production_date
    ON storage.feed_lots (production_date) WHERE archived_at IS NULL;

-- ============================================================
-- Movimentações de estoque (ledger imutável)
-- ============================================================
CREATE TABLE IF NOT EXISTS storage.feed_stock_movements (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id                   uuid NOT NULL DEFAULT gen_random_uuid(),
    organization_id             bigint NOT NULL,
    farm_id                     bigint NOT NULL,
    lot_id                      bigint NOT NULL REFERENCES storage.feed_lots(id),
    movement_type               text NOT NULL CHECK (movement_type IN (
                                    'initial_balance','entry','withdrawal','loss',
                                    'adjustment_positive','adjustment_negative')),
    movement_at                 timestamptz NOT NULL DEFAULT now(),
    quantity_natural_kg         numeric(12,2) NOT NULL CHECK (quantity_natural_kg >= 0),
    dry_matter_pct_snapshot     numeric(5,2) NOT NULL CHECK (dry_matter_pct_snapshot >= 0 AND dry_matter_pct_snapshot <= 100),
    utilization_pct_snapshot    numeric(5,2) NOT NULL DEFAULT 100 CHECK (utilization_pct_snapshot >= 0 AND utilization_pct_snapshot <= 100),
    physical_dm_kg              numeric(12,2) NOT NULL DEFAULT 0 CHECK (physical_dm_kg >= 0),
    usable_dm_kg                numeric(12,2) NOT NULL DEFAULT 0 CHECK (usable_dm_kg >= 0),
    unit_cost_snapshot          numeric(10,4) CHECK (unit_cost_snapshot IS NULL OR unit_cost_snapshot >= 0),
    total_cost                  numeric(12,2) CHECK (total_cost IS NULL OR total_cost >= 0),
    loss_reason                 text NOT NULL DEFAULT '',
    reason                      text NOT NULL DEFAULT '',
    notes                       text NOT NULL DEFAULT '',
    request_id                  varchar(200) NOT NULL,
    created_by_user_id          bigint NOT NULL,
    created_at                  timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_movement_public_id UNIQUE (public_id)
);

CREATE INDEX ix_movement_lot
    ON storage.feed_stock_movements (lot_id, movement_at DESC);
CREATE INDEX ix_movement_farm
    ON storage.feed_stock_movements (farm_id, movement_at DESC);
CREATE INDEX ix_movement_request_id
    ON storage.feed_stock_movements (request_id);
CREATE INDEX ix_movement_type
    ON storage.feed_stock_movements (movement_type) WHERE movement_type IN ('loss','adjustment_negative');

-- Idempotência: request_id único por lote
CREATE UNIQUE INDEX uq_movement_request_per_lot
    ON storage.feed_stock_movements (lot_id, request_id);

COMMIT;
