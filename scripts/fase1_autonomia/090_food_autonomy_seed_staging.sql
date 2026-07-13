-- 090_food_autonomy_seed_staging.sql — Dados sintéticos para validação no staging
-- Idempotente: usa ON CONFLICT para reexecução segura.
BEGIN;

SET client_min_messages = warning;

-- Fazenda sintética (já existe no seed da Fase 0D)
-- Vamos usar a primeira fazenda ativa da organização sintética
DO $$
DECLARE
  v_org_id bigint;
  v_farm_id bigint;
  v_user_id bigint;
  v_scenario_1 uuid := gen_random_uuid();
  v_scenario_2 uuid := gen_random_uuid();
  v_scenario_3 uuid := gen_random_uuid();
BEGIN
  -- Busca organização e fazenda sintéticas
  SELECT id INTO v_org_id FROM foundation.organizations WHERE status = 'active' LIMIT 1;
  SELECT f.id INTO v_farm_id FROM foundation.operational_farms f
   WHERE f.organization_id = v_org_id AND f.status = 'active' LIMIT 1;
  SELECT id INTO v_user_id FROM foundation.app_users LIMIT 1;

  IF v_org_id IS NULL OR v_farm_id IS NULL THEN
    RAISE NOTICE 'Dados sintéticos da Fase 0D não encontrados — seed de autonomia pulado.';
    RETURN;
  END IF;

  -- ============================================================
  -- Cenário 1: ADEQUADO (estoque acima da meta)
  -- Demanda: 20 vacas × 450kg × 2.5% = 225 kg MS/dia
  -- Estoques: 50.000 kg silagem × 35% MS × 100% = 17.500 kg MS
  -- Autonomia: 17.500 / 225 = 77.78 dias > 60 dias meta
  -- ============================================================
  INSERT INTO nutrition.food_autonomy_scenarios
    (public_id, organization_id, farm_id, name, reference_date, target_days,
     safety_margin_pct, total_daily_demand_dm_kg, total_pasture_dm_kg,
     total_stored_feed_dm_kg, total_physical_dm_kg, reserve_dm_kg,
     planning_available_dm_kg, autonomy_days, target_required_dm_kg,
     balance_dm_kg, balance_days, status, estimated_end_date,
     formula_version, notes, created_by_user_id)
  VALUES (
    v_scenario_1, v_org_id, v_farm_id, 'Cenário Adequado', CURRENT_DATE, 60,
    0, 225.00, 0, 17500.00, 17500.00, 0, 17500.00, 77.78,
    13500.00, 4000.00, 17.78, 'adequate', CURRENT_DATE + 77,
    'food_autonomy.v1', 'Dados sintéticos para validação', COALESCE(v_user_id, 1)
  );

  INSERT INTO nutrition.food_autonomy_herd_items
    (scenario_id, category, custom_category_name, head_count, average_weight_kg,
     intake_pct_body_weight, calculated_daily_demand_dm_kg, display_order)
  VALUES (
    (SELECT id FROM nutrition.food_autonomy_scenarios WHERE public_id = v_scenario_1),
    'lactating_cows', '', 20, 450.00, 2.50, 225.00, 0
  );

  -- ============================================================
  -- Cenário 2: ATENÇÃO (autonomia entre 50% e 100% da meta)
  -- Demanda: 30 vacas × 450kg × 2.5% = 337.50 kg MS/dia
  -- Estoques: 20.000 kg silagem × 35% MS × 90% = 6.300 kg MS
  -- Autonomia: 6.300 / 337.50 = 18.67 dias, meta 30 → 62% da meta
  -- ============================================================
  INSERT INTO nutrition.food_autonomy_scenarios
    (public_id, organization_id, farm_id, name, reference_date, target_days,
     safety_margin_pct, total_daily_demand_dm_kg, total_pasture_dm_kg,
     total_stored_feed_dm_kg, total_physical_dm_kg, reserve_dm_kg,
     planning_available_dm_kg, autonomy_days, target_required_dm_kg,
     balance_dm_kg, balance_days, status, estimated_end_date,
     formula_version, notes, created_by_user_id)
  VALUES (
    v_scenario_2, v_org_id, v_farm_id, 'Cenário Atenção', CURRENT_DATE, 30,
    0, 337.50, 0, 6300.00, 6300.00, 0, 6300.00, 18.67,
    10125.00, -3825.00, -11.33, 'warning', CURRENT_DATE + 18,
    'food_autonomy.v1', 'Estoque insuficiente para meta', COALESCE(v_user_id, 1)
  );

  INSERT INTO nutrition.food_autonomy_herd_items
    (scenario_id, category, custom_category_name, head_count, average_weight_kg,
     intake_pct_body_weight, calculated_daily_demand_dm_kg, display_order)
  VALUES (
    (SELECT id FROM nutrition.food_autonomy_scenarios WHERE public_id = v_scenario_2),
    'lactating_cows', '', 30, 450.00, 2.50, 337.50, 0
  );

  -- ============================================================
  -- Cenário 3: CRÍTICO (autonomia abaixo de 50% da meta)
  -- Demanda: 50 vacas × 450kg × 2.5% = 562.50 kg MS/dia
  -- Estoques: 10.000 kg silagem × 35% MS × 90% = 3.150 kg MS
  -- Autonomia: 3.150 / 562.50 = 5.60 dias, meta 90 → 6.2% da meta
  -- ============================================================
  INSERT INTO nutrition.food_autonomy_scenarios
    (public_id, organization_id, farm_id, name, reference_date, target_days,
     safety_margin_pct, total_daily_demand_dm_kg, total_pasture_dm_kg,
     total_stored_feed_dm_kg, total_physical_dm_kg, reserve_dm_kg,
     planning_available_dm_kg, autonomy_days, target_required_dm_kg,
     balance_dm_kg, balance_days, status, estimated_end_date,
     formula_version, notes, created_by_user_id)
  VALUES (
    v_scenario_3, v_org_id, v_farm_id, 'Cenário Crítico', CURRENT_DATE, 90,
    0, 562.50, 0, 3150.00, 3150.00, 0, 3150.00, 5.60,
    50625.00, -47475.00, -84.40, 'critical', CURRENT_DATE + 5,
    'food_autonomy.v1', 'Estoque criticamente baixo', COALESCE(v_user_id, 1)
  );

  INSERT INTO nutrition.food_autonomy_herd_items
    (scenario_id, category, custom_category_name, head_count, average_weight_kg,
     intake_pct_body_weight, calculated_daily_demand_dm_kg, display_order)
  VALUES (
    (SELECT id FROM nutrition.food_autonomy_scenarios WHERE public_id = v_scenario_3),
    'lactating_cows', '', 50, 450.00, 2.50, 562.50, 0
  );

END
$$;

COMMIT;
