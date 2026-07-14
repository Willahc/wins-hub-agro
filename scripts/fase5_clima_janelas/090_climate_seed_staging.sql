-- 090_climate_seed_staging.sql — Dados sintéticos para validação do módulo Clima e Operações
BEGIN;

SET client_min_messages = warning;

DO $$
DECLARE
  v_org_id bigint;
  v_farm_id bigint;
  v_user_id bigint;
  v_profile_uuid uuid := 'b1000000-0000-4000-8000-000000000001';
  v_profile_id bigint;
  v_now timestamptz := now();
BEGIN
  SELECT id INTO v_org_id FROM foundation.organizations WHERE status = 'active' LIMIT 1;
  SELECT f.id INTO v_farm_id FROM foundation.operational_farms f
   WHERE f.organization_id = v_org_id AND f.status = 'active' LIMIT 1;
  SELECT id INTO v_user_id FROM foundation.app_users WHERE auth_subject = 'mari@winshubagro.cloud' LIMIT 1;

  IF v_org_id IS NULL OR v_farm_id IS NULL THEN
    RAISE NOTICE 'Dados de staging da Fase 0D não encontrados — seed de clima pulado.';
    RETURN;
  END IF;

  IF v_user_id IS NULL THEN
    SELECT id INTO v_user_id FROM foundation.app_users LIMIT 1;
  END IF;

  -- Perfil climático sintético (coordenadas públicas de uma fazenda no MT)
  INSERT INTO climate.farm_weather_profiles
    (public_id, organization_id, farm_id, latitude, longitude, timezone,
     provider, enabled, refresh_interval_minutes, forecast_days, status, notes,
     created_by_user_id)
  VALUES
    (v_profile_uuid, v_org_id, v_farm_id, -12.6400, -55.7200, 'America/Cuiaba',
     'open-meteo', true, 20, 7, 'active', 'Perfil sintético para testes de clima.', v_user_id)
  ON CONFLICT (public_id) DO NOTHING;

  SELECT id INTO v_profile_id FROM climate.farm_weather_profiles WHERE public_id = v_profile_uuid;

  -- Snapshot de condição atual sintética
  IF v_profile_id IS NOT NULL THEN
    INSERT INTO climate.weather_snapshots
      (public_id, organization_id, farm_id, profile_id, snapshot_type,
       period_start, period_end, payload_normalized, provider,
       normalization_version, fetched_at, expires_at, stale_after, checksum)
    VALUES
      (gen_random_uuid(), v_org_id, v_farm_id, v_profile_id, 'current',
       v_now, v_now + interval '20 minutes',
       '{"temperature_c": 28.5, "feels_like_c": 30.1, "humidity_pct": 65, "precipitation_mm": 0, "wind_kmh": 12, "gust_kmh": 18, "wind_direction_deg": 180, "cloud_cover_pct": 40, "condition_code": null, "condition_description": "Parcialmente nublado", "observation_time": null}'::jsonb,
       'open-meteo', 'weather_normalization.v1', v_now, v_now + interval '20 minutes',
       v_now + interval '20 minutes', 'seed_current_001')
    ON CONFLICT DO NOTHING;

    -- Snapshot de previsão diária sintética
    INSERT INTO climate.weather_snapshots
      (public_id, organization_id, farm_id, profile_id, snapshot_type,
       period_start, period_end, payload_normalized, provider,
       normalization_version, fetched_at, expires_at, stale_after, checksum)
    VALUES
      (gen_random_uuid(), v_org_id, v_farm_id, v_profile_id, 'daily_forecast',
       v_now, v_now + interval '7 days',
       '[{"date": "' || (current_date)::text || '", "temperature_min_c": 18, "temperature_max_c": 32, "precipitation_sum_mm": 0, "precipitation_probability_max": 10, "wind_speed_max_kmh": 20, "wind_gusts_max_kmh": 30},
         {"date": "' || (current_date + 1)::text || '", "temperature_min_c": 19, "temperature_max_c": 33, "precipitation_sum_mm": 2.5, "precipitation_probability_max": 45, "wind_speed_max_kmh": 25, "wind_gusts_max_kmh": 35},
         {"date": "' || (current_date + 2)::text || '", "temperature_min_c": 20, "temperature_max_c": 31, "precipitation_sum_mm": 8.0, "precipitation_probability_max": 80, "wind_speed_max_kmh": 30, "wind_gusts_max_kmh": 45}]'::jsonb,
       'open-meteo', 'weather_normalization.v1', v_now, v_now + interval '2 hours',
       v_now + interval '2 hours', 'seed_daily_001')
    ON CONFLICT DO NOTHING;

    -- Snapshot de histórico recente sintético
    INSERT INTO climate.weather_snapshots
      (public_id, organization_id, farm_id, profile_id, snapshot_type,
       period_start, period_end, payload_normalized, provider,
       normalization_version, fetched_at, expires_at, stale_after, checksum)
    VALUES
      (gen_random_uuid(), v_org_id, v_farm_id, v_profile_id, 'recent_history',
       v_now - interval '7 days', v_now,
       '[{"date": "' || (current_date - 6)::text || '", "precipitation_sum_mm": 0, "temperature_min_c": 17, "temperature_max_c": 30},
         {"date": "' || (current_date - 5)::text || '", "precipitation_sum_mm": 5.2, "temperature_min_c": 18, "temperature_max_c": 28},
         {"date": "' || (current_date - 4)::text || '", "precipitation_sum_mm": 12.0, "temperature_min_c": 19, "temperature_max_c": 27},
         {"date": "' || (current_date - 3)::text || '", "precipitation_sum_mm": 0, "temperature_min_c": 20, "temperature_max_c": 31},
         {"date": "' || (current_date - 2)::text || '", "precipitation_sum_mm": 0, "temperature_min_c": 21, "temperature_max_c": 32},
         {"date": "' || (current_date - 1)::text || '", "precipitation_sum_mm": 1.5, "temperature_min_c": 19, "temperature_max_c": 29},
         {"date": "' || (current_date)::text || '", "precipitation_sum_mm": 0, "temperature_min_c": 18, "temperature_max_c": 32}]'::jsonb,
       'open-meteo', 'weather_normalization.v1', v_now, v_now + interval '12 hours',
       v_now + interval '12 hours', 'seed_history_001')
    ON CONFLICT DO NOTHING;
  END IF;

END $$;

COMMIT;
