-- 090_harvest_seed_staging.sql — Dados sintéticos para validação do módulo Colheita e Silos
BEGIN;

SET client_min_messages = warning;

DO $$
DECLARE
  v_org_id bigint;
  v_farm_id bigint;
  v_user_id bigint;

  -- Facilities
  v_facility_c_uuid uuid := 'a1000000-0000-4000-8000-000000000011';
  v_facility_d_uuid uuid := 'a1000000-0000-4000-8000-000000000012';
  v_facility_e_uuid uuid := 'a1000000-0000-4000-8000-000000000013';
  v_facility_f_uuid uuid := 'a1000000-0000-4000-8000-000000000014';

  v_fac_c_id bigint;
  v_fac_d_id bigint;
  v_fac_e_id bigint;
  v_fac_f_id bigint;

  -- Plan 1 (Capacidade Adequada)
  v_plan_1_uuid uuid := 'c1000000-0000-4000-8000-000000000001';
  v_plan_1_id bigint;
  v_area_1_uuid uuid := 'd1000000-0000-4000-8000-000000000001';
  v_alloc_1_uuid uuid := 'e1000000-0000-4000-8000-000000000001';

  -- Plan 2 (Próximo do Limite)
  v_plan_2_uuid uuid := 'c1000000-0000-4000-8000-000000000002';
  v_plan_2_id bigint;
  v_area_2_uuid uuid := 'd1000000-0000-4000-8000-000000000002';
  v_alloc_2_uuid uuid := 'e1000000-0000-4000-8000-000000000002';

  -- Plan 3 (Acima da Capacidade)
  v_plan_3_uuid uuid := 'c1000000-0000-4000-8000-000000000003';
  v_plan_3_id bigint;
  v_area_3_uuid uuid := 'd1000000-0000-4000-8000-000000000003';
  v_alloc_3_uuid uuid := 'e1000000-0000-4000-8000-000000000003';

  -- Plan 4 (Concluído)
  v_plan_4_uuid uuid := 'c1000000-0000-4000-8000-000000000004';
  v_plan_4_id bigint;
  v_area_4_uuid uuid := 'd1000000-0000-4000-8000-000000000004';
  v_alloc_4_uuid uuid := 'e1000000-0000-4000-8000-000000000004';

  -- Feed Lot and movement for Plan 4
  v_lot_4_uuid uuid := 'b1000000-0000-4000-8000-000000000014';
  v_movement_4_uuid uuid := 'f1000000-0000-4000-8000-000000000014';
  v_lot_4_id bigint;

BEGIN
  SELECT id INTO v_org_id FROM foundation.organizations WHERE status = 'active' LIMIT 1;
  SELECT f.id INTO v_farm_id FROM foundation.operational_farms f
   WHERE f.organization_id = v_org_id AND f.status = 'active' LIMIT 1;
  SELECT id INTO v_user_id FROM foundation.app_users WHERE auth_subject = 'mari@winshubagro.cloud' LIMIT 1;

  IF v_org_id IS NULL OR v_farm_id IS NULL THEN
    RAISE NOTICE 'Dados de staging da Fase 0D não encontrados — seed de colheita pulado.';
    RETURN;
  END IF;

  IF v_user_id IS NULL THEN
    SELECT id INTO v_user_id FROM foundation.app_users LIMIT 1;
  END IF;

  -- ============================================================
  -- 1. ESTRUTURAS DE ARMAZENAMENTO COMPATÍVEIS (SILOS)
  -- ============================================================

  -- Silo C (1.000.000 kg para Plano 1 - Capacidade Adequada)
  INSERT INTO storage.feed_storage_facilities
    (public_id, organization_id, farm_id, name, code, facility_type,
     capacity_natural_kg, preferred_display_unit, location_description, active, notes, created_by_user_id)
  VALUES (v_facility_c_uuid, v_org_id, v_farm_id, 'Silo Grande C', 'SGC', 'silo_trincheira',
          1000000.00, 'kg', 'Setor Leste', true, 'Silo grande para milho', v_user_id)
  ON CONFLICT (public_id) DO NOTHING;
  SELECT id INTO v_fac_c_id FROM storage.feed_storage_facilities WHERE public_id = v_facility_c_uuid;

  -- Silo D (300.000 kg para Plano 2 - Próximo do Limite)
  INSERT INTO storage.feed_storage_facilities
    (public_id, organization_id, farm_id, name, code, facility_type,
     capacity_natural_kg, preferred_display_unit, location_description, active, notes, created_by_user_id)
  VALUES (v_facility_d_uuid, v_org_id, v_farm_id, 'Silo Médio D', 'SMD', 'silo_trincheira',
          300000.00, 'kg', 'Setor Sul', true, 'Silo médio para sorgo', v_user_id)
  ON CONFLICT (public_id) DO NOTHING;
  SELECT id INTO v_fac_d_id FROM storage.feed_storage_facilities WHERE public_id = v_facility_d_uuid;

  -- Silo E (400.000 kg para Plano 3 - Acima da Capacidade)
  INSERT INTO storage.feed_storage_facilities
    (public_id, organization_id, farm_id, name, code, facility_type,
     capacity_natural_kg, preferred_display_unit, location_description, active, notes, created_by_user_id)
  VALUES (v_facility_e_uuid, v_org_id, v_farm_id, 'Silo Pequeno E', 'SPE', 'silo_superficie',
          400000.00, 'kg', 'Setor Oeste', true, 'Silo pequeno para capim', v_user_id)
  ON CONFLICT (public_id) DO NOTHING;
  SELECT id INTO v_fac_e_id FROM storage.feed_storage_facilities WHERE public_id = v_facility_e_uuid;

  -- Silo F (500.000 kg para Plano 4 - Concluído)
  INSERT INTO storage.feed_storage_facilities
    (public_id, organization_id, farm_id, name, code, facility_type,
     capacity_natural_kg, preferred_display_unit, location_description, active, notes, created_by_user_id)
  VALUES (v_facility_f_uuid, v_org_id, v_farm_id, 'Silo Concluído F', 'SCF', 'silo_superficie',
          500000.00, 'kg', 'Setor Central', true, 'Silo para concluído', v_user_id)
  ON CONFLICT (public_id) DO NOTHING;
  SELECT id INTO v_fac_f_id FROM storage.feed_storage_facilities WHERE public_id = v_facility_f_uuid;

  -- ============================================================
  -- 2. PLANO 1 - CAPACIDADE ADEQUADA (Milho, 20 ha, 40 t/ha, 35% MS)
  -- ============================================================
  INSERT INTO harvest.harvest_plans
    (public_id, organization_id, farm_id, name, main_crop, purpose,
     expected_start_date, expected_end_date, expected_field_loss_pct, expected_ensiling_loss_pct,
     expected_gross_natural_kg, expected_net_natural_kg, expected_dm_kg, status, notes, created_by_user_id)
  VALUES
    (v_plan_1_uuid, v_org_id, v_farm_id, 'Plano 1 - Capacidade Adequada', 'milho', 'silagem',
     current_date + 10, current_date + 15, 5.00, 8.00,
     800000.00, 699200.00, 244720.00, 'planned', 'Planejamento de milho com capacidade adequada.', v_user_id)
  ON CONFLICT (public_id) DO NOTHING;
  SELECT id INTO v_plan_1_id FROM harvest.harvest_plans WHERE public_id = v_plan_1_uuid;

  IF v_plan_1_id IS NOT NULL THEN
    INSERT INTO harvest.harvest_plan_areas
      (public_id, plan_id, organization_id, farm_id, name, crop, cultivar, area_ha, expected_yield_t_ha,
       expected_dm_pct, expected_harvest_date, calculated_gross_natural_kg, calculated_net_natural_kg,
       calculated_dm_kg, notes, display_order)
    VALUES
      (v_area_1_uuid, v_plan_1_id, v_org_id, v_farm_id, 'Talhão A', 'milho', 'P30F53', 20.00, 40.00,
       35.00, current_date + 10, 800000.00, 699200.00, 244720.00, 'Sem intercorrências', 1)
    ON CONFLICT (public_id) DO NOTHING;

    INSERT INTO harvest.harvest_storage_allocations
      (public_id, plan_id, organization_id, farm_id, facility_id, expected_quantity_natural_kg,
       expected_percentage, capacity_snapshot_kg, current_stock_snapshot_kg, projected_occupancy_kg,
       projected_occupancy_pct, capacity_status)
    VALUES
      (v_alloc_1_uuid, v_plan_1_id, v_org_id, v_farm_id, v_fac_c_id, 699200.00,
       100.00, 1000000.00, 0.00, 699200.00, 69.92, 'available')
    ON CONFLICT (public_id) DO NOTHING;
  END IF;

  -- ============================================================
  -- 3. PLANO 2 - PRÓXIMO DO LIMITE (Sorgo, 10 ha, 30 t/ha, 35% MS)
  -- ============================================================
  INSERT INTO harvest.harvest_plans
    (public_id, organization_id, farm_id, name, main_crop, purpose,
     expected_start_date, expected_end_date, expected_field_loss_pct, expected_ensiling_loss_pct,
     expected_gross_natural_kg, expected_net_natural_kg, expected_dm_kg, status, notes, created_by_user_id)
  VALUES
    (v_plan_2_uuid, v_org_id, v_farm_id, 'Plano 2 - Próximo do Limite', 'sorgo', 'silagem',
     current_date + 20, current_date + 25, 5.00, 8.00,
     300000.00, 262200.00, 91770.00, 'planned', 'Planejamento de sorgo com ocupação de ~87%.', v_user_id)
  ON CONFLICT (public_id) DO NOTHING;
  SELECT id INTO v_plan_2_id FROM harvest.harvest_plans WHERE public_id = v_plan_2_uuid;

  IF v_plan_2_id IS NOT NULL THEN
    INSERT INTO harvest.harvest_plan_areas
      (public_id, plan_id, organization_id, farm_id, name, crop, cultivar, area_ha, expected_yield_t_ha,
       expected_dm_pct, expected_harvest_date, calculated_gross_natural_kg, calculated_net_natural_kg,
       calculated_dm_kg, notes, display_order)
    VALUES
      (v_area_2_uuid, v_plan_2_id, v_org_id, v_farm_id, 'Talhão B', 'sorgo', 'SS22', 10.00, 30.00,
       35.00, current_date + 20, 300000.00, 262200.00, 91770.00, 'Solo arenoso', 1)
    ON CONFLICT (public_id) DO NOTHING;

    INSERT INTO harvest.harvest_storage_allocations
      (public_id, plan_id, organization_id, farm_id, facility_id, expected_quantity_natural_kg,
       expected_percentage, capacity_snapshot_kg, current_stock_snapshot_kg, projected_occupancy_kg,
       projected_occupancy_pct, capacity_status)
    VALUES
      (v_alloc_2_uuid, v_plan_2_id, v_org_id, v_farm_id, v_fac_d_id, 262200.00,
       100.00, 300000.00, 0.00, 262200.00, 87.40, 'near_capacity')
    ON CONFLICT (public_id) DO NOTHING;
  END IF;

  -- ============================================================
  -- 4. PLANO 3 - ACIMA DA CAPACIDADE (Capim, 15 ha, 40 t/ha)
  -- ============================================================
  INSERT INTO harvest.harvest_plans
    (public_id, organization_id, farm_id, name, main_crop, purpose,
     expected_start_date, expected_end_date, expected_field_loss_pct, expected_ensiling_loss_pct,
     expected_gross_natural_kg, expected_net_natural_kg, expected_dm_kg, status, notes, created_by_user_id)
  VALUES
    (v_plan_3_uuid, v_org_id, v_farm_id, 'Plano 3 - Acima da Capacidade', 'capim', 'silagem',
     current_date + 30, current_date + 35, 5.00, 8.00,
     600000.00, 524400.00, 183540.00, 'planned', 'Planejamento de capim que excede capacidade do silo E.', v_user_id)
  ON CONFLICT (public_id) DO NOTHING;
  SELECT id INTO v_plan_3_id FROM harvest.harvest_plans WHERE public_id = v_plan_3_uuid;

  IF v_plan_3_id IS NOT NULL THEN
    INSERT INTO harvest.harvest_plan_areas
      (public_id, plan_id, organization_id, farm_id, name, crop, cultivar, area_ha, expected_yield_t_ha,
       expected_dm_pct, expected_harvest_date, calculated_gross_natural_kg, calculated_net_natural_kg,
       calculated_dm_kg, notes, display_order)
    VALUES
      (v_area_3_uuid, v_plan_3_id, v_org_id, v_farm_id, 'Talhão C', 'capim', 'Mombaça', 15.00, 40.00,
       35.00, current_date + 30, 600000.00, 524400.00, 183540.00, 'Pasto rotacionado', 1)
    ON CONFLICT (public_id) DO NOTHING;

    INSERT INTO harvest.harvest_storage_allocations
      (public_id, plan_id, organization_id, farm_id, facility_id, expected_quantity_natural_kg,
       expected_percentage, capacity_snapshot_kg, current_stock_snapshot_kg, projected_occupancy_kg,
       projected_occupancy_pct, capacity_status)
    VALUES
      (v_alloc_3_uuid, v_plan_3_id, v_org_id, v_farm_id, v_fac_e_id, 524400.00,
       100.00, 400000.00, 0.00, 524400.00, 131.10, 'over_capacity')
    ON CONFLICT (public_id) DO NOTHING;
  END IF;

  -- ============================================================
  -- 5. PLANO 4 - CONCLUÍDO (Milho, lote synthetic criado no estoque)
  -- ============================================================
  -- Insere o lote de alimento correspondente
  INSERT INTO storage.feed_lots
    (public_id, organization_id, farm_id, facility_id, name, feed_type,
     production_date, ensiling_date, opened_at, source_description,
     initial_quantity_natural_kg, current_quantity_natural_kg,
     dry_matter_pct, utilization_pct,
     current_physical_dm_kg, current_usable_dm_kg,
     status, notes, created_by_user_id, rule_version)
  VALUES
    (v_lot_4_uuid, v_org_id, v_farm_id, v_fac_f_id, 'Lote Colheita Plano 4', 'silagem_milho',
     current_date - 10, current_date - 10, now(), 'Harvest Plan c1000000-0000-4000-8000-000000000004',
     100000.00, 100000.00, 35.00, 100.00,
     35000.00, 35000.00,
     'available', 'Lote gerado automaticamente pela conclusão do plano', v_user_id, 'feed_inventory.v1')
  ON CONFLICT (public_id) DO NOTHING;
  SELECT id INTO v_lot_4_id FROM storage.feed_lots WHERE public_id = v_lot_4_uuid;

  IF v_lot_4_id IS NOT NULL THEN
    -- Insere o movimento correspondente
    INSERT INTO storage.feed_stock_movements
      (public_id, organization_id, farm_id, lot_id, movement_type, movement_at, quantity_natural_kg,
       dry_matter_pct_snapshot, utilization_pct_snapshot, physical_dm_kg, usable_dm_kg, request_id, created_by_user_id)
    VALUES
      (v_movement_4_uuid, v_org_id, v_farm_id, v_lot_4_id, 'initial_balance', current_date - 10, 100000.00,
       35.00, 100.00, 35000.00, 35000.00, 'req-seed-harvest-p4', v_user_id)
    ON CONFLICT (public_id) DO NOTHING;
  END IF;

  -- Insere o plano 4
  INSERT INTO harvest.harvest_plans
    (public_id, organization_id, farm_id, name, main_crop, purpose,
     expected_start_date, expected_end_date, expected_field_loss_pct, expected_ensiling_loss_pct,
     expected_gross_natural_kg, expected_net_natural_kg, expected_dm_kg,
     actual_start_date, actual_end_date, actual_natural_kg, actual_dm_pct, actual_loss_pct,
     status, notes, completion_request_id, completed_by_user_id, completed_at, created_by_user_id)
  VALUES
    (v_plan_4_uuid, v_org_id, v_farm_id, 'Plano 4 - Concluído', 'milho', 'silagem',
     current_date - 15, current_date - 10, 5.00, 8.00,
     120000.00, 104880.00, 36708.00,
     current_date - 12, current_date - 10, 100000.00, 35.00, 0.00,
     'completed', 'Plano concluído com sucesso e lote gerado.', 'req-seed-harvest-p4', v_user_id, now(), v_user_id)
  ON CONFLICT (public_id) DO NOTHING;
  SELECT id INTO v_plan_4_id FROM harvest.harvest_plans WHERE public_id = v_plan_4_uuid;

  IF v_plan_4_id IS NOT NULL THEN
    INSERT INTO harvest.harvest_plan_areas
      (public_id, plan_id, organization_id, farm_id, name, crop, cultivar, area_ha, expected_yield_t_ha,
       expected_dm_pct, expected_harvest_date, calculated_gross_natural_kg, calculated_net_natural_kg,
       calculated_dm_kg, notes, display_order)
    VALUES
      (v_area_4_uuid, v_plan_4_id, v_org_id, v_farm_id, 'Talhão D', 'milho', 'K9555', 3.00, 40.00,
       35.00, current_date - 12, 120000.00, 104880.00, 36708.00, 'Concluído', 1)
    ON CONFLICT (public_id) DO NOTHING;

    INSERT INTO harvest.harvest_storage_allocations
      (public_id, plan_id, organization_id, farm_id, facility_id, expected_quantity_natural_kg,
       actual_quantity_natural_kg, expected_percentage, capacity_snapshot_kg, current_stock_snapshot_kg,
       projected_occupancy_kg, projected_occupancy_pct, capacity_status, created_feed_lot_id)
    VALUES
      (v_alloc_4_uuid, v_plan_4_id, v_org_id, v_farm_id, v_fac_f_id, 104880.00,
       100000.00, 100.00, 500000.00, 0.00, 100000.00, 20.00, 'available', v_lot_4_id)
    ON CONFLICT (public_id) DO NOTHING;
  END IF;

END $$;

COMMIT;
