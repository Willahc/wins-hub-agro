-- 001_food_autonomy_schema.sql — Schema do módulo de Autonomia Alimentar
-- Migration idempotente, transacional, sem CASCADE no rollback.
BEGIN;

SET client_min_messages = warning;

CREATE SCHEMA IF NOT EXISTS nutrition;

-- ============================================================
-- Tabela principal: cenários de autonomia alimentar
-- ============================================================
CREATE TABLE IF NOT EXISTS nutrition.food_autonomy_scenarios (
    id                      bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id               uuid NOT NULL DEFAULT gen_random_uuid(),
    organization_id         bigint NOT NULL REFERENCES foundation.organizations(id),
    farm_id                 bigint NOT NULL REFERENCES foundation.operational_farms(id),
    name                    text NOT NULL,
    reference_date          date NOT NULL,
    target_days             integer NOT NULL CHECK (target_days >= 1),
    safety_margin_pct       numeric(5,2) NOT NULL DEFAULT 0 CHECK (safety_margin_pct >= 0 AND safety_margin_pct <= 100),
    total_daily_demand_dm_kg    numeric(12,2) NOT NULL DEFAULT 0,
    total_pasture_dm_kg         numeric(12,2) NOT NULL DEFAULT 0,
    total_stored_feed_dm_kg     numeric(12,2) NOT NULL DEFAULT 0,
    total_physical_dm_kg        numeric(12,2) NOT NULL DEFAULT 0,
    reserve_dm_kg               numeric(12,2) NOT NULL DEFAULT 0,
    planning_available_dm_kg    numeric(12,2) NOT NULL DEFAULT 0,
    autonomy_days               numeric(8,2) NOT NULL DEFAULT 0,
    target_required_dm_kg       numeric(12,2) NOT NULL DEFAULT 0,
    balance_dm_kg               numeric(12,2) NOT NULL DEFAULT 0,
    balance_days                numeric(8,2) NOT NULL DEFAULT 0,
    status                  text NOT NULL DEFAULT 'incomplete'
                            CHECK (status IN ('critical','warning','adequate','incomplete')),
    estimated_end_date      date,
    formula_version         text NOT NULL DEFAULT 'food_autonomy.v1',
    notes                   text NOT NULL DEFAULT '',
    created_by_user_id      bigint NOT NULL,
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now(),
    archived_at             timestamptz,

    CONSTRAINT uq_food_autonomy_scenario_public_id UNIQUE (public_id)
);

CREATE INDEX IF NOT EXISTS ix_food_autonomy_scenario_farm
    ON nutrition.food_autonomy_scenarios (farm_id, reference_date DESC);
CREATE INDEX IF NOT EXISTS ix_food_autonomy_scenario_org
    ON nutrition.food_autonomy_scenarios (organization_id, status);
CREATE INDEX IF NOT EXISTS ix_food_autonomy_scenario_status
    ON nutrition.food_autonomy_scenarios (status) WHERE archived_at IS NULL;

-- ============================================================
-- Itens do rebanho (herd)
-- ============================================================
CREATE TABLE IF NOT EXISTS nutrition.food_autonomy_herd_items (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_id                 bigint NOT NULL REFERENCES nutrition.food_autonomy_scenarios(id) ON DELETE CASCADE,
    category                    text NOT NULL,
    custom_category_name        text NOT NULL DEFAULT '',
    head_count                  integer NOT NULL CHECK (head_count >= 0),
    average_weight_kg           numeric(8,2) NOT NULL CHECK (average_weight_kg > 0),
    intake_pct_body_weight      numeric(5,2) NOT NULL CHECK (intake_pct_body_weight > 0 AND intake_pct_body_weight <= 10),
    calculated_daily_demand_dm_kg numeric(12,2) NOT NULL DEFAULT 0,
    display_order               integer NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_food_autonomy_herd_scenario
    ON nutrition.food_autonomy_herd_items (scenario_id);

-- ============================================================
-- Itens de pastagem
-- ============================================================
CREATE TABLE IF NOT EXISTS nutrition.food_autonomy_pasture_items (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_id                 bigint NOT NULL REFERENCES nutrition.food_autonomy_scenarios(id) ON DELETE CASCADE,
    name                        text NOT NULL,
    area_ha                     numeric(10,4) NOT NULL CHECK (area_ha > 0),
    available_dm_kg_ha          numeric(10,2) NOT NULL CHECK (available_dm_kg_ha >= 0),
    utilization_pct             numeric(5,2) NOT NULL DEFAULT 50 CHECK (utilization_pct >= 0 AND utilization_pct <= 100),
    calculated_usable_dm_kg     numeric(12,2) NOT NULL DEFAULT 0,
    notes                       text NOT NULL DEFAULT '',
    display_order               integer NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_food_autonomy_pasture_scenario
    ON nutrition.food_autonomy_pasture_items (scenario_id);

-- ============================================================
-- Itens de estoque (alimentos conservados e suplementos)
-- ============================================================
CREATE TABLE IF NOT EXISTS nutrition.food_autonomy_feed_items (
    id                          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    scenario_id                 bigint NOT NULL REFERENCES nutrition.food_autonomy_scenarios(id) ON DELETE CASCADE,
    feed_type                   text NOT NULL CHECK (feed_type IN (
                                    'silage','hay','pre_dried','concentrate',
                                    'protein_supplement','mineral_supplement',
                                    'byproduct','other')),
    name                        text NOT NULL,
    quantity_natural_kg         numeric(12,2) NOT NULL CHECK (quantity_natural_kg >= 0),
    dry_matter_pct              numeric(5,2) NOT NULL CHECK (dry_matter_pct >= 0 AND dry_matter_pct <= 100),
    utilization_pct             numeric(5,2) NOT NULL DEFAULT 100 CHECK (utilization_pct >= 0 AND utilization_pct <= 100),
    calculated_usable_dm_kg     numeric(12,2) NOT NULL DEFAULT 0,
    notes                       text NOT NULL DEFAULT '',
    display_order               integer NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS ix_food_autonomy_feed_scenario
    ON nutrition.food_autonomy_feed_items (scenario_id);

COMMIT;
