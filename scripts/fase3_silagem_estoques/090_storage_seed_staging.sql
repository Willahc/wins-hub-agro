-- 090_storage_seed_staging.sql — Dados sintéticos para validação no staging
-- Idempotente: usa ON CONFLICT para reexecução segura.
BEGIN;

SET client_min_messages = warning;

DO $$
DECLARE
  v_org_id bigint;
  v_farm_id bigint;
  v_user_id bigint;
  v_facility_1 uuid := 'a1000000-0000-4000-8000-000000000001';
  v_facility_2 uuid := 'a1000000-0000-4000-8000-000000000002';
  v_fac_1_id bigint;
  v_fac_2_id bigint;
  v_lot_1 uuid := 'b1000000-0000-4000-8000-000000000001';
  v_lot_2 uuid := 'b1000000-0000-4000-8000-000000000002';
  v_lot_3 uuid := 'b1000000-0000-4000-8000-000000000003';
  v_lot_4 uuid := 'b1000000-0000-4000-8000-000000000004';
  v_lot_1_id bigint;
  v_lot_2_id bigint;
  v_lot_3_id bigint;
  v_lot_4_id bigint;
BEGIN
  SELECT id INTO v_org_id FROM foundation.organizations WHERE status = 'active' LIMIT 1;
  SELECT f.id INTO v_farm_id FROM foundation.operational_farms f
   WHERE f.organization_id = v_org_id AND f.status = 'active' LIMIT 1;
  SELECT id INTO v_user_id FROM foundation.app_users WHERE auth_subject = 'mari@winshubagro.cloud' LIMIT 1;

  IF v_org_id IS NULL OR v_farm_id IS NULL THEN
    RAISE NOTICE 'Dados sintéticos da Fase 0D não encontrados — seed de storage pulado.';
    RETURN;
  END IF;

  IF v_user_id IS NULL THEN
    SELECT id INTO v_user_id FROM foundation.app_users LIMIT 1;
  END IF;

  -- ============================================================
  -- Facility 1: Silo Trincheira (capacidade 100.000 kg)
  -- ============================================================
  INSERT INTO storage.feed_storage_facilities
    (public_id, organization_id, farm_id, name, code, facility_type,
     capacity_natural_kg, preferred_display_unit, location_description,
     active, notes, created_by_user_id)
  VALUES (
    v_facility_1, v_org_id, v_farm_id, 'Silo Trincheira Principal', 'ST01',
    'silo_trincheira', 100000.00, 'kg', 'Setor Norte da fazenda',
    true, 'Silo trincheira para silagem de milho', v_user_id
  )
  ON CONFLICT (public_id) DO NOTHING
  RETURNING id INTO v_fac_1_id;

  IF v_fac_1_id IS NULL THEN
    SELECT id INTO v_fac_1_id FROM storage.feed_storage_facilities WHERE public_id = v_facility_1;
  END IF;

  -- ============================================================
  -- Facility 2: Galpão (capacidade 20.000 kg)
  -- ============================================================
  INSERT INTO storage.feed_storage_facilities
    (public_id, organization_id, farm_id, name, code, facility_type,
     capacity_natural_kg, preferred_display_unit, location_description,
     active, notes, created_by_user_id)
  VALUES (
    v_facility_2, v_org_id, v_farm_id, 'Galpão de Feno', 'GF01',
    'galpao', 20000.00, 'kg', 'Setor Oeste da fazenda',
    true, 'Galpão coberto para armazenamento de feno', v_user_id
  )
  ON CONFLICT (public_id) DO NOTHING
  RETURNING id INTO v_fac_2_id;

  IF v_fac_2_id IS NULL THEN
    SELECT id INTO v_fac_2_id FROM storage.feed_storage_facilities WHERE public_id = v_facility_2;
  END IF;

  -- ============================================================
  -- Lot 1: Silagem de milho (60.000 kg, 35% MS, 90% util, opened)
  -- ============================================================
  INSERT INTO storage.feed_lots
    (public_id, organization_id, farm_id, facility_id, name, feed_type,
     production_date, ensiling_date, opened_at, source_description,
     initial_quantity_natural_kg, current_quantity_natural_kg,
     dry_matter_pct, utilization_pct,
     current_physical_dm_kg, current_usable_dm_kg,
     status, notes, created_by_user_id)
  VALUES (
    v_lot_1, v_org_id, v_farm_id, v_fac_1_id, 'Silagem Milho Safra 2026', 'silagem_milho',
    '2026-04-15', '2026-04-16', now() - INTERVAL '30 days',
    'Fazenda Alfa - Talhão 3',
    60000.00, 42000.00,
    35.00, 90.00,
    14700.00, 13230.00,
    'opened', 'Silagem em uso diário', v_user_id
  )
  ON CONFLICT (public_id) DO NOTHING
  RETURNING id INTO v_lot_1_id;

  IF v_lot_1_id IS NULL THEN
    SELECT id INTO v_lot_1_id FROM storage.feed_lots WHERE public_id = v_lot_1;
  END IF;

  -- ============================================================
  -- Lot 2: Feno (8.000 kg, 85% MS, 95% util, available)
  -- ============================================================
  INSERT INTO storage.feed_lots
    (public_id, organization_id, farm_id, facility_id, name, feed_type,
     production_date, source_description,
     initial_quantity_natural_kg, current_quantity_natural_kg,
     dry_matter_pct, utilization_pct,
     current_physical_dm_kg, current_usable_dm_kg,
     status, notes, created_by_user_id)
  VALUES (
    v_lot_2, v_org_id, v_farm_id, v_fac_2_id, 'Feno Tifton 85', 'feno',
    '2026-05-10', 'Compra - Fornecedore XYZ',
    8000.00, 8000.00,
    85.00, 95.00,
    6800.00, 6460.00,
    'available', 'Feno de qualidade premium', v_user_id
  )
  ON CONFLICT (public_id) DO NOTHING
  RETURNING id INTO v_lot_2_id;

  IF v_lot_2_id IS NULL THEN
    SELECT id INTO v_lot_2_id FROM storage.feed_lots WHERE public_id = v_lot_2;
  END IF;

  -- ============================================================
  -- Lot 3: Lote quase esgotado (saldo pequeno)
  -- ============================================================
  INSERT INTO storage.feed_lots
    (public_id, organization_id, farm_id, facility_id, name, feed_type,
     production_date, ensiling_date, opened_at, source_description,
     initial_quantity_natural_kg, current_quantity_natural_kg,
     dry_matter_pct, utilization_pct,
     current_physical_dm_kg, current_usable_dm_kg,
     status, notes, created_by_user_id)
  VALUES (
    v_lot_3, v_org_id, v_farm_id, v_fac_1_id, 'Silagem Milho Antiga', 'silagem_milho',
    '2025-11-20', '2025-11-21', now() - INTERVAL '90 days',
    'Fazenda Alfa - Talhão 1',
    45000.00, 2500.00,
    32.00, 85.00,
    800.00, 680.00,
    'opened', 'Lote quase esgotado — resto da safra anterior', v_user_id
  )
  ON CONFLICT (public_id) DO NOTHING
  RETURNING id INTO v_lot_3_id;

  IF v_lot_3_id IS NULL THEN
    SELECT id INTO v_lot_3_id FROM storage.feed_lots WHERE public_id = v_lot_3;
  END IF;

  -- ============================================================
  -- Lot 4: Lote em quarentena
  -- ============================================================
  INSERT INTO storage.feed_lots
    (public_id, organization_id, farm_id, facility_id, name, feed_type,
     production_date, ensiling_date, source_description,
     initial_quantity_natural_kg, current_quantity_natural_kg,
     dry_matter_pct, utilization_pct,
     current_physical_dm_kg, current_usable_dm_kg,
     status, notes, created_by_user_id)
  VALUES (
    v_lot_4, v_org_id, v_farm_id, v_fac_1_id, 'Silagem Sorgo Suspeita', 'silagem_sorgo',
    '2026-06-01', '2026-06-02', 'Fazenda Alfa - Talhão 5',
    15000.00, 15000.00,
    30.00, 90.00,
    4500.00, 4050.00,
    'quarantined', 'Amostra enviada para análise — aguardando resultado', v_user_id
  )
  ON CONFLICT (public_id) DO NOTHING
  RETURNING id INTO v_lot_4_id;

  IF v_lot_4_id IS NULL THEN
    SELECT id INTO v_lot_4_id FROM storage.feed_lots WHERE public_id = v_lot_4;
  END IF;

  -- ============================================================
  -- Movimentações — Lot 1 (Silagem Milho)
  -- ============================================================
  INSERT INTO storage.feed_stock_movements
    (public_id, organization_id, farm_id, lot_id, movement_type, movement_at,
     quantity_natural_kg, dry_matter_pct_snapshot, utilization_pct_snapshot,
     physical_dm_kg, usable_dm_kg, reason, notes, request_id, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_org_id, v_farm_id, v_lot_1_id, 'initial_balance',
    '2026-04-16T14:00:00Z',
    60000.00, 35.00, 90.00,
    21000.00, 18900.00,
    'Saldo inicial do lote', 'Abertura do lote de silagem de milho',
    'req-silagem-init-001', v_user_id
  )
  ON CONFLICT (lot_id, request_id) DO NOTHING;

  INSERT INTO storage.feed_stock_movements
    (public_id, organization_id, farm_id, lot_id, movement_type, movement_at,
     quantity_natural_kg, dry_matter_pct_snapshot, utilization_pct_snapshot,
     physical_dm_kg, usable_dm_kg, reason, notes, request_id, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_org_id, v_farm_id, v_lot_1_id, 'entry',
    '2026-05-01T09:00:00Z',
    5000.00, 35.00, 90.00,
    1750.00, 1575.00,
    'Complemento de silagem', 'Entrada de silagem produzida no talhão 4',
    'req-silagem-entry-001', v_user_id
  )
  ON CONFLICT (lot_id, request_id) DO NOTHING;

  INSERT INTO storage.feed_stock_movements
    (public_id, organization_id, farm_id, lot_id, movement_type, movement_at,
     quantity_natural_kg, dry_matter_pct_snapshot, utilization_pct_snapshot,
     physical_dm_kg, usable_dm_kg, reason, notes, request_id, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_org_id, v_farm_id, v_lot_1_id, 'withdrawal',
    '2026-06-01T07:30:00Z',
    10000.00, 35.00, 90.00,
    3500.00, 3150.00,
    'Uso diário — ração vacas lactantes', 'Retirada para mistura de TMR',
    'req-silagem-wd-001', v_user_id
  )
  ON CONFLICT (lot_id, request_id) DO NOTHING;

  INSERT INTO storage.feed_stock_movements
    (public_id, organization_id, farm_id, lot_id, movement_type, movement_at,
     quantity_natural_kg, dry_matter_pct_snapshot, utilization_pct_snapshot,
     physical_dm_kg, usable_dm_kg, loss_reason, reason, notes, request_id, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_org_id, v_farm_id, v_lot_1_id, 'loss',
    '2026-06-15T11:00:00Z',
    800.00, 35.00, 90.00,
    280.00, 252.00,
    'Mofamento na borda do silo', 'Perda por deterioração', 'Perda estimada visualmente',
    'req-silagem-loss-001', v_user_id
  )
  ON CONFLICT (lot_id, request_id) DO NOTHING;

  INSERT INTO storage.feed_stock_movements
    (public_id, organization_id, farm_id, lot_id, movement_type, movement_at,
     quantity_natural_kg, dry_matter_pct_snapshot, utilization_pct_snapshot,
     physical_dm_kg, usable_dm_kg, reason, notes, request_id, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_org_id, v_farm_id, v_lot_1_id, 'adjustment_positive',
    '2026-06-20T16:00:00Z',
    2200.00, 35.00, 90.00,
    770.00, 693.00,
    'Ajuste por reavaliação de peso', 'Aferição com balança indicou mais volume',
    'req-silagem-adj-001', v_user_id
  )
  ON CONFLICT (lot_id, request_id) DO NOTHING;

  -- ============================================================
  -- Movimentações — Lot 2 (Feno)
  -- ============================================================
  INSERT INTO storage.feed_stock_movements
    (public_id, organization_id, farm_id, lot_id, movement_type, movement_at,
     quantity_natural_kg, dry_matter_pct_snapshot, utilization_pct_snapshot,
     physical_dm_kg, usable_dm_kg, reason, notes, request_id, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_org_id, v_farm_id, v_lot_2_id, 'initial_balance',
    '2026-05-10T10:00:00Z',
    8000.00, 85.00, 95.00,
    6800.00, 6460.00,
    'Saldo inicial do lote', 'Compra de feno Tifton 85',
    'req-feno-init-001', v_user_id
  )
  ON CONFLICT (lot_id, request_id) DO NOTHING;

  -- ============================================================
  -- Movimentações — Lot 3 (Silagem quase esgotada)
  -- ============================================================
  INSERT INTO storage.feed_stock_movements
    (public_id, organization_id, farm_id, lot_id, movement_type, movement_at,
     quantity_natural_kg, dry_matter_pct_snapshot, utilization_pct_snapshot,
     physical_dm_kg, usable_dm_kg, reason, notes, request_id, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_org_id, v_farm_id, v_lot_3_id, 'initial_balance',
    '2025-11-21T14:00:00Z',
    45000.00, 32.00, 85.00,
    14400.00, 12240.00,
    'Saldo inicial do lote', 'Silagem da safra anterior',
    'req-antiga-init-001', v_user_id
  )
  ON CONFLICT (lot_id, request_id) DO NOTHING;

  -- ============================================================
  -- Movimentações — Lot 4 (Quarentena)
  -- ============================================================
  INSERT INTO storage.feed_stock_movements
    (public_id, organization_id, farm_id, lot_id, movement_type, movement_at,
     quantity_natural_kg, dry_matter_pct_snapshot, utilization_pct_snapshot,
     physical_dm_kg, usable_dm_kg, reason, notes, request_id, created_by_user_id)
  VALUES (
    gen_random_uuid(), v_org_id, v_farm_id, v_lot_4_id, 'initial_balance',
    '2026-06-02T14:00:00Z',
    15000.00, 30.00, 90.00,
    4500.00, 4050.00,
    'Saldo inicial do lote', 'Lote em quarentena para análise',
    'req-quar-init-001', v_user_id
  )
  ON CONFLICT (lot_id, request_id) DO NOTHING;

END
$$;

COMMIT;
