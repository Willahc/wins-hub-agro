-- 090_pasture_seed_staging.sql — Dados sintéticos para validação no staging
-- Idempotente: usa ON CONFLICT para reexecução segura.
BEGIN;

SET client_min_messages = warning;

DO $$
DECLARE
  v_org_id bigint;
  v_farm_id bigint;
  v_user_id bigint;
  v_paddock_1 uuid := gen_random_uuid();
  v_paddock_2 uuid := gen_random_uuid();
  v_paddock_3 uuid := gen_random_uuid();
  v_paddock_4 uuid := gen_random_uuid();
  v_pid_1 bigint;
  v_pid_2 bigint;
  v_pid_3 bigint;
  v_pid_4 bigint;
BEGIN
  SELECT id INTO v_org_id FROM foundation.organizations WHERE status = 'active' LIMIT 1;
  SELECT f.id INTO v_farm_id FROM foundation.operational_farms f
   WHERE f.organization_id = v_org_id AND f.status = 'active' LIMIT 1;
  SELECT id INTO v_user_id FROM foundation.app_users LIMIT 1;

  IF v_org_id IS NULL OR v_farm_id IS NULL THEN
    RAISE NOTICE 'Dados sintéticos da Fase 0D não encontrados — seed de pasto vivo pulado.';
    RETURN;
  END IF;

  -- ============================================================
  -- Piquete 1: Piquete Norte (pronto para entrar)
  -- 8 ha, Brachiaria brizantha cv. Marandu
  -- ============================================================
  INSERT INTO pasture.paddocks
    (public_id, organization_id, farm_id, name, code, forage_species, cultivar,
     area_ha, target_entry_height_cm, target_exit_height_cm, planned_rest_days,
     default_utilization_pct, manual_status, active, notes, created_by_user_id)
  VALUES (
    v_paddock_1, v_org_id, v_farm_id, 'Piquete Norte', 'PN01',
    'Brachiaria brizantha', 'Marandu',
    8.0000, 30, 10, 30, 50, 'ready', true,
    'Piquete sintético para validação', COALESCE(v_user_id, 1)
  )
  ON CONFLICT (public_id) DO NOTHING
  RETURNING id INTO v_pid_1;

  IF v_pid_1 IS NULL THEN
    SELECT id INTO v_pid_1 FROM pasture.paddocks WHERE public_id = v_paddock_1;
  END IF;

  INSERT INTO pasture.paddock_measurements
    (public_id, paddock_id, organization_id, farm_id, measured_at,
     average_height_cm, available_dm_kg_ha, utilization_pct,
     calculated_total_dm_kg, calculated_usable_dm_kg,
     measurement_method, rule_version, notes, measured_by_user_id)
  VALUES (
    gen_random_uuid(), v_pid_1, v_org_id, v_farm_id, now() - INTERVAL '3 days',
    35, 1800.00, 50, 14400.00, 7200.00,
    'ruler', 'pasture_live.v1', 'Medição sintética', COALESCE(v_user_id, 1)
  );

  INSERT INTO pasture.paddock_events
    (public_id, paddock_id, organization_id, farm_id, event_type, event_at,
     notes, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_pid_1, v_org_id, v_farm_id, 'grazing_finished', now() - INTERVAL '10 days',
     'Ciclo de pastejo encerrado', COALESCE(v_user_id, 1)
  );

  -- ============================================================
  -- Piquete 2: Piquete Sul (em pastejo)
  -- 6 ha, Panicum maximum cv. Mombaça
  -- ============================================================
  INSERT INTO pasture.paddocks
    (public_id, organization_id, farm_id, name, code, forage_species, cultivar,
     area_ha, target_entry_height_cm, target_exit_height_cm, planned_rest_days,
     default_utilization_pct, manual_status, active, notes, created_by_user_id)
  VALUES (
    v_paddock_2, v_org_id, v_farm_id, 'Piquete Sul', 'PS02',
    'Panicum maximum', 'Mombaça',
    6.0000, 25, 8, 25, 60, 'grazing', true,
    'Piquete sintético para validação', COALESCE(v_user_id, 1)
  )
  ON CONFLICT (public_id) DO NOTHING
  RETURNING id INTO v_pid_2;

  IF v_pid_2 IS NULL THEN
    SELECT id INTO v_pid_2 FROM pasture.paddocks WHERE public_id = v_paddock_2;
  END IF;

  INSERT INTO pasture.paddock_measurements
    (public_id, paddock_id, organization_id, farm_id, measured_at,
     average_height_cm, available_dm_kg_ha, utilization_pct,
     calculated_total_dm_kg, calculated_usable_dm_kg,
     measurement_method, rule_version, notes, measured_by_user_id)
  VALUES (
    gen_random_uuid(), v_pid_2, v_org_id, v_farm_id, now() - INTERVAL '2 days',
    20, 1500.00, 60, 9000.00, 5400.00,
    'visual', 'pasture_live.v1', 'Medição sintética', COALESCE(v_user_id, 1)
  );

  INSERT INTO pasture.paddock_events
    (public_id, paddock_id, organization_id, farm_id, event_type, event_at,
     expected_end_at, head_count, average_weight_kg, management_group_name,
     notes, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_pid_2, v_org_id, v_farm_id, 'grazing_started', now() - INTERVAL '5 days',
     now() + INTERVAL '10 days', 45, 450.00, 'Novilhas',
     'Pastejo em andamento', COALESCE(v_user_id, 1)
  );

  -- ============================================================
  -- Piquete 3: Piquete Leste (em descanso)
  -- 10 ha, Brachiaria decumbens
  -- ============================================================
  INSERT INTO pasture.paddocks
    (public_id, organization_id, farm_id, name, code, forage_species, cultivar,
     area_ha, target_entry_height_cm, target_exit_height_cm, planned_rest_days,
     default_utilization_pct, manual_status, active, notes, created_by_user_id)
  VALUES (
    v_paddock_3, v_org_id, v_farm_id, 'Piquete Leste', 'PL03',
    'Brachiaria decumbens', '',
    10.0000, 28, 10, 35, 50, 'resting', true,
    'Piquete sintético para validação', COALESCE(v_user_id, 1)
  )
  ON CONFLICT (public_id) DO NOTHING
  RETURNING id INTO v_pid_3;

  IF v_pid_3 IS NULL THEN
    SELECT id INTO v_pid_3 FROM pasture.paddocks WHERE public_id = v_paddock_3;
  END IF;

  INSERT INTO pasture.paddock_measurements
    (public_id, paddock_id, organization_id, farm_id, measured_at,
     average_height_cm, available_dm_kg_ha, utilization_pct,
     calculated_total_dm_kg, calculated_usable_dm_kg,
     measurement_method, rule_version, notes, measured_by_user_id)
  VALUES (
    gen_random_uuid(), v_pid_3, v_org_id, v_farm_id, now() - INTERVAL '1 day',
    12, 1200.00, 50, 12000.00, 6000.00,
    'ruler', 'pasture_live.v1', 'Medição sintética', COALESCE(v_user_id, 1)
  );

  INSERT INTO pasture.paddock_events
    (public_id, paddock_id, organization_id, farm_id, event_type, event_at,
     notes, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_pid_3, v_org_id, v_farm_id, 'grazing_finished', now() - INTERVAL '3 days',
     'Ciclo encerrado — início de descanso', COALESCE(v_user_id, 1)
  );

  INSERT INTO pasture.paddock_events
    (public_id, paddock_id, organization_id, farm_id, event_type, event_at,
     expected_end_at, notes, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_pid_3, v_org_id, v_farm_id, 'rest_started', now() - INTERVAL '3 days',
     now() + INTERVAL '32 days', 'Descanso programado 35 dias', COALESCE(v_user_id, 1)
  );

  -- ============================================================
  -- Piquete 4: Piquete Oeste (atenção)
  -- 5 ha, Tifton 85
  -- ============================================================
  INSERT INTO pasture.paddocks
    (public_id, organization_id, farm_id, name, code, forage_species, cultivar,
     area_ha, target_entry_height_cm, target_exit_height_cm, planned_rest_days,
     default_utilization_pct, manual_status, active, notes, created_by_user_id)
  VALUES (
    v_paddock_4, v_org_id, v_farm_id, 'Piquete Oeste', 'PO04',
    'Tifton 85', '',
    5.0000, 20, 8, 20, 45, 'attention', true,
    'Piquete com pastagem abaixo da altura de entrada', COALESCE(v_user_id, 1)
  )
  ON CONFLICT (public_id) DO NOTHING
  RETURNING id INTO v_pid_4;

  IF v_pid_4 IS NULL THEN
    SELECT id INTO v_pid_4 FROM pasture.paddocks WHERE public_id = v_paddock_4;
  END IF;

  INSERT INTO pasture.paddock_measurements
    (public_id, paddock_id, organization_id, farm_id, measured_at,
     average_height_cm, available_dm_kg_ha, utilization_pct,
     calculated_total_dm_kg, calculated_usable_dm_kg,
     measurement_method, rule_version, notes, measured_by_user_id)
  VALUES (
    gen_random_uuid(), v_pid_4, v_org_id, v_farm_id, now() - INTERVAL '25 days',
    15, 1000.00, 45, 5000.00, 2250.00,
    'visual', 'pasture_live.v1', 'Medição antiga — altura abaixo da meta', COALESCE(v_user_id, 1)
  );

  INSERT INTO pasture.paddock_events
    (public_id, paddock_id, organization_id, farm_id, event_type, event_at,
     notes, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_pid_4, v_org_id, v_farm_id, 'rest_started', now() - INTERVAL '25 days',
     'Descanso iniciado — período já encerrado', COALESCE(v_user_id, 1)
  );

END
$$;

COMMIT;
