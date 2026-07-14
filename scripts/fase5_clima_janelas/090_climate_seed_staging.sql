-- 090_climate_seed_staging.sql — Dados sintéticos para validação do módulo Clima e Operações
-- Idempotente: upsert por public_id, pode ser re-executado sem duplicar registros.
BEGIN;

SET client_min_messages = warning;

DO $$
DECLARE
  v_user_id bigint;
  v_now timestamptz := now();
  v_farm_rec RECORD;
  v_profile_id bigint;
  v_snap_payload jsonb;
  v_org_alfa_pub constant uuid := 'a0000000-0000-4000-8000-00000000000a';
  v_org_alfa_id bigint;
BEGIN
  -- Localiza organização Alfa pelo UUID público determinístico do seed da Fase 0D
  SELECT id INTO v_org_alfa_id FROM foundation.organizations
   WHERE public_id = v_org_alfa_pub;

  IF v_org_alfa_id IS NULL THEN
    RAISE NOTICE 'Organização Alfa (%) não encontrada — seed de clima pulado.', v_org_alfa_pub;
    RETURN;
  END IF;

  -- Localiza o usuário mari (seed da Fase 0D). Se não existir, aborta.
  SELECT id INTO v_user_id FROM foundation.app_users
   WHERE auth_subject = 'mari@winshubagro.cloud';

  IF v_user_id IS NULL THEN
    RAISE NOTICE 'Usuário mari@winshubagro.cloud não encontrado — seed de clima pulado.';
    RETURN;
  END IF;

  -- Remove snapshots seed anteriores das 3 fazendas Alfa antes de reinserir.
  -- Apenas perfis de seed (public_id fixo) são limpos; snapshots reais/externos
  -- de outras fazendas ou providers são preservados.
  DELETE FROM climate.weather_snapshots ws
   WHERE ws.profile_id IN (
     SELECT id FROM climate.farm_weather_profiles
      WHERE public_id IN (
        'b1000000-0000-4000-8000-000000000001',
        'b1000000-0000-4000-8000-000000000002',
        'b1000000-0000-4000-8000-000000000003'
      )
   );

  -- Seed das 3 fazendas Alfa com coordenadas sintéticas distintas.
  -- Todos os UUIDs (fazenda, perfil, snapshots) são fixos e determinísticos,
  -- garantindo idempotência via ON CONFLICT DO UPDATE.
  FOR v_farm_rec IN
    WITH seed (farm_uuid, profile_uuid, current_uuid, forecast_uuid, history_uuid,
               lat, lon, tz, label) AS (
      VALUES
        ('f0000000-0000-4000-8000-000000000001'::uuid,
         'b1000000-0000-4000-8000-000000000001'::uuid,
         'c1000000-0000-4000-8000-000000000001'::uuid,
         'd1000000-0000-4000-8000-000000000001'::uuid,
         'e1000000-0000-4000-8000-000000000001'::uuid,
         -12.6400, -55.7200, 'America/Cuiaba',    'Norte'),
        ('f0000000-0000-4000-8000-000000000003'::uuid,
         'b1000000-0000-4000-8000-000000000002'::uuid,
         'c1000000-0000-4000-8000-000000000002'::uuid,
         'd1000000-0000-4000-8000-000000000002'::uuid,
         'e1000000-0000-4000-8000-000000000002'::uuid,
         -12.9700, -38.5100, 'America/Bahia',      'Leste'),
        ('f0000000-0000-4000-8000-000000000002'::uuid,
         'b1000000-0000-4000-8000-000000000003'::uuid,
         'c1000000-0000-4000-8000-000000000003'::uuid,
         'd1000000-0000-4000-8000-000000000003'::uuid,
         'e1000000-0000-4000-8000-000000000003'::uuid,
         -25.4300, -49.2700, 'America/Sao_Paulo',  'Sul')
    )
    SELECT s.*, f.id AS farm_id, f.organization_id
      FROM seed s
      JOIN foundation.operational_farms f ON f.public_id = s.farm_uuid
     WHERE f.organization_id = v_org_alfa_id
  LOOP
    -- Upsert do perfil climático
    INSERT INTO climate.farm_weather_profiles
      (public_id, organization_id, farm_id, latitude, longitude, timezone,
       provider, enabled, refresh_interval_minutes, forecast_days, status, notes,
       created_by_user_id)
    VALUES
      (v_farm_rec.profile_uuid, v_farm_rec.organization_id, v_farm_rec.farm_id,
       v_farm_rec.lat, v_farm_rec.lon, v_farm_rec.tz,
       'open-meteo', true, 20, 7, 'active',
       'Perfil sintético para testes de clima (' || v_farm_rec.label || ').',
       v_user_id)
    ON CONFLICT (public_id) DO UPDATE SET
      farm_id              = EXCLUDED.farm_id,
      organization_id      = EXCLUDED.organization_id,
      latitude             = EXCLUDED.latitude,
      longitude            = EXCLUDED.longitude,
      timezone             = EXCLUDED.timezone,
      provider             = EXCLUDED.provider,
      enabled              = EXCLUDED.enabled,
      refresh_interval_minutes = EXCLUDED.refresh_interval_minutes,
      forecast_days        = EXCLUDED.forecast_days,
      status               = EXCLUDED.status,
      notes                = EXCLUDED.notes;

    SELECT id INTO v_profile_id
      FROM climate.farm_weather_profiles
     WHERE public_id = v_farm_rec.profile_uuid;

    -- Snapshot current
    v_snap_payload := '{"temperature_c":28.5,"feels_like_c":30.1,"humidity_pct":65,"precipitation_mm":0,"wind_kmh":12,"gust_kmh":18,"wind_direction_deg":180,"cloud_cover_pct":40,"condition_code":null,"condition_description":"Parcialmente nublado","observation_time":null}'::jsonb;

    INSERT INTO climate.weather_snapshots
      (public_id, organization_id, farm_id, profile_id, snapshot_type,
       period_start, period_end, payload_normalized, provider,
       normalization_version, fetched_at, expires_at, stale_after, checksum)
    VALUES
      (v_farm_rec.current_uuid, v_farm_rec.organization_id, v_farm_rec.farm_id,
       v_profile_id, 'current',
       v_now, v_now + interval '20 minutes',
       v_snap_payload,
       'open-meteo', 'weather_normalization.v1', v_now, v_now + interval '20 minutes',
       v_now + interval '20 minutes', 'seed_current_' || v_farm_rec.label)
    ON CONFLICT (public_id) DO UPDATE SET
      organization_id = EXCLUDED.organization_id,
      farm_id         = EXCLUDED.farm_id,
      profile_id      = EXCLUDED.profile_id,
      snapshot_type   = EXCLUDED.snapshot_type,
      period_start    = EXCLUDED.period_start,
      period_end      = EXCLUDED.period_end,
      payload_normalized = EXCLUDED.payload_normalized,
      provider        = EXCLUDED.provider,
      fetched_at      = EXCLUDED.fetched_at,
      expires_at      = EXCLUDED.expires_at,
      stale_after     = EXCLUDED.stale_after,
      checksum        = EXCLUDED.checksum;

    -- Snapshot daily_forecast
    v_snap_payload := jsonb_build_array(
      jsonb_build_object('date', (current_date)::text, 'temperature_min_c', 18, 'temperature_max_c', 32, 'precipitation_sum_mm', 0, 'precipitation_probability_max', 10, 'wind_speed_max_kmh', 20, 'wind_gusts_max_kmh', 30),
      jsonb_build_object('date', (current_date + 1)::text, 'temperature_min_c', 19, 'temperature_max_c', 33, 'precipitation_sum_mm', 2.5, 'precipitation_probability_max', 45, 'wind_speed_max_kmh', 25, 'wind_gusts_max_kmh', 35),
      jsonb_build_object('date', (current_date + 2)::text, 'temperature_min_c', 20, 'temperature_max_c', 31, 'precipitation_sum_mm', 8.0, 'precipitation_probability_max', 80, 'wind_speed_max_kmh', 30, 'wind_gusts_max_kmh', 45)
    );

    INSERT INTO climate.weather_snapshots
      (public_id, organization_id, farm_id, profile_id, snapshot_type,
       period_start, period_end, payload_normalized, provider,
       normalization_version, fetched_at, expires_at, stale_after, checksum)
    VALUES
      (v_farm_rec.forecast_uuid, v_farm_rec.organization_id, v_farm_rec.farm_id,
       v_profile_id, 'daily_forecast',
       v_now, v_now + interval '7 days',
       v_snap_payload,
       'open-meteo', 'weather_normalization.v1', v_now, v_now + interval '2 hours',
       v_now + interval '2 hours', 'seed_daily_' || v_farm_rec.label)
    ON CONFLICT (public_id) DO UPDATE SET
      organization_id = EXCLUDED.organization_id,
      farm_id         = EXCLUDED.farm_id,
      profile_id      = EXCLUDED.profile_id,
      snapshot_type   = EXCLUDED.snapshot_type,
      period_start    = EXCLUDED.period_start,
      period_end      = EXCLUDED.period_end,
      payload_normalized = EXCLUDED.payload_normalized,
      provider        = EXCLUDED.provider,
      fetched_at      = EXCLUDED.fetched_at,
      expires_at      = EXCLUDED.expires_at,
      stale_after     = EXCLUDED.stale_after,
      checksum        = EXCLUDED.checksum;

    -- Snapshot recent_history
    v_snap_payload := jsonb_build_array(
      jsonb_build_object('date', (current_date - 6)::text, 'precipitation_sum_mm', 0, 'temperature_min_c', 17, 'temperature_max_c', 30),
      jsonb_build_object('date', (current_date - 5)::text, 'precipitation_sum_mm', 5.2, 'temperature_min_c', 18, 'temperature_max_c', 28),
      jsonb_build_object('date', (current_date - 4)::text, 'precipitation_sum_mm', 12.0, 'temperature_min_c', 19, 'temperature_max_c', 27),
      jsonb_build_object('date', (current_date - 3)::text, 'precipitation_sum_mm', 0, 'temperature_min_c', 20, 'temperature_max_c', 31),
      jsonb_build_object('date', (current_date - 2)::text, 'precipitation_sum_mm', 0, 'temperature_min_c', 21, 'temperature_max_c', 32),
      jsonb_build_object('date', (current_date - 1)::text, 'precipitation_sum_mm', 1.5, 'temperature_min_c', 19, 'temperature_max_c', 29),
      jsonb_build_object('date', (current_date)::text, 'precipitation_sum_mm', 0, 'temperature_min_c', 18, 'temperature_max_c', 32)
    );

    INSERT INTO climate.weather_snapshots
      (public_id, organization_id, farm_id, profile_id, snapshot_type,
       period_start, period_end, payload_normalized, provider,
       normalization_version, fetched_at, expires_at, stale_after, checksum)
    VALUES
      (v_farm_rec.history_uuid, v_farm_rec.organization_id, v_farm_rec.farm_id,
       v_profile_id, 'recent_history',
       v_now - interval '7 days', v_now,
       v_snap_payload,
       'open-meteo', 'weather_normalization.v1', v_now, v_now + interval '12 hours',
       v_now + interval '12 hours', 'seed_history_' || v_farm_rec.label)
    ON CONFLICT (public_id) DO UPDATE SET
      organization_id = EXCLUDED.organization_id,
      farm_id         = EXCLUDED.farm_id,
      profile_id      = EXCLUDED.profile_id,
      snapshot_type   = EXCLUDED.snapshot_type,
      period_start    = EXCLUDED.period_start,
      period_end      = EXCLUDED.period_end,
      payload_normalized = EXCLUDED.payload_normalized,
      provider        = EXCLUDED.provider,
      fetched_at      = EXCLUDED.fetched_at,
      expires_at      = EXCLUDED.expires_at,
      stale_after     = EXCLUDED.stale_after,
      checksum        = EXCLUDED.checksum;

  END LOOP;
END $$;

COMMIT;
