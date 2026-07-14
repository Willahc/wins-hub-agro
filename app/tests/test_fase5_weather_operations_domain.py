"""Testes de Domínio do módulo de Clima e Janelas Operacionais."""
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from domain.weather_operations import (
    FORMULA_VERSION, NORMALIZATION_VERSION,
    WindowType, WindowClassification, WeatherStatus, SnapshotType, CacheStatus,
    WINDOW_TYPE_LABELS, CLASSIFICATION_LABELS, WEATHER_STATUS_LABELS,
    normalize_temperature_celsius, normalize_humidity_pct,
    normalize_precipitation_mm, normalize_wind_kmh, normalize_cloud_cover_pct,
    normalize_weather_condition, classify_temperature,
    compute_window_score, check_freshness, compute_cache_expires_at,
    build_window_response, WINDOW_DEFAULTS,
)


class TestNormalization:
    def test_temperature_valid(self):
        assert normalize_temperature_celsius(25.5) == 25.5

    def test_temperature_none(self):
        assert normalize_temperature_celsius(None) is None

    def test_temperature_out_of_range(self):
        assert normalize_temperature_celsius(-100) is None
        assert normalize_temperature_celsius(70) is None

    def test_temperature_string(self):
        assert normalize_temperature_celsius("30.0") == 30.0

    def test_humidity_valid(self):
        assert normalize_humidity_pct(65.0) == 65.0

    def test_humidity_none(self):
        assert normalize_humidity_pct(None) is None

    def test_humidity_out_of_range(self):
        assert normalize_humidity_pct(-1) is None
        assert normalize_humidity_pct(101) is None

    def test_precipitation_valid(self):
        assert normalize_precipitation_mm(5.5) == 5.5

    def test_precipitation_none(self):
        assert normalize_precipitation_mm(None) is None

    def test_precipitation_negative(self):
        assert normalize_precipitation_mm(-1) is None

    def test_wind_valid(self):
        assert normalize_wind_kmh(15.0) == 15.0

    def test_wind_none(self):
        assert normalize_wind_kmh(None) is None

    def test_wind_negative(self):
        assert normalize_wind_kmh(-5) is None

    def test_cloud_cover_valid(self):
        assert normalize_cloud_cover_pct(50.0) == 50.0

    def test_cloud_cover_none(self):
        assert normalize_cloud_cover_pct(None) is None

    def test_cloud_cover_out_of_range(self):
        assert normalize_cloud_cover_pct(-1) is None
        assert normalize_cloud_cover_pct(101) is None


class TestWeatherCondition:
    def test_normalize_full(self):
        result = normalize_weather_condition({
            "temperature_c": 25, "feels_like_c": 27, "humidity_pct": 60,
            "precipitation_mm": 0, "wind_kmh": 10, "gust_kmh": 15,
            "wind_direction_deg": 180, "cloud_cover_pct": 30,
            "condition_code": "clear", "condition_description": "Limpo",
            "observation_time": "2026-01-01T12:00",
        })
        assert result["temperature_c"] == 25
        assert result["humidity_pct"] == 60

    def test_normalize_empty(self):
        result = normalize_weather_condition({})
        assert result["temperature_c"] is None


class TestClassifyTemperature:
    def test_normal(self):
        assert classify_temperature(25, 27) == "normal"

    def test_attention(self):
        assert classify_temperature(35, 36) == "attention"

    def test_elevated(self):
        assert classify_temperature(40, 42) == "elevated"

    def test_none(self):
        assert classify_temperature(None, None) == "normal"

    def test_feels_like_priority(self):
        assert classify_temperature(30, 36) == "attention"


class TestWindowScore:
    def test_insufficient_data(self):
        score, cls, pos, risks = compute_window_score("harvest_cut", required_fields_present=False)
        assert score == 0
        assert cls == WindowClassification.INSUFFICIENT_DATA.value

    def test_favorable_cut(self):
        score, cls, pos, risks = compute_window_score(
            "harvest_cut", precipitation_mm=0, precipitation_probability=10, gust_kmh=20)
        assert score >= 75
        assert cls == WindowClassification.FAVORABLE.value

    def test_attention_cut(self):
        score, cls, pos, risks = compute_window_score(
            "harvest_cut", precipitation_mm=3, precipitation_probability=45, gust_kmh=30)
        assert 45 <= score < 75
        assert cls == WindowClassification.ATTENTION.value

    def test_unfavorable_cut(self):
        score, cls, pos, risks = compute_window_score(
            "harvest_cut", precipitation_mm=10, precipitation_probability=80, gust_kmh=50)
        assert score < 45
        assert cls == WindowClassification.UNFAVORABLE.value

    def test_severe_alert(self):
        score, cls, pos, risks = compute_window_score(
            "harvest_cut", precipitation_mm=0, precipitation_probability=10,
            has_severe_alert=True)
        assert score < 100
        assert any(r["factor"] == "severe_weather_alert" for r in risks)

    def test_heat_attention(self):
        score, cls, pos, risks = compute_window_score(
            "heat_attention", temperature_c=38, feels_like_c=40)
        assert score < 100
        assert any(r["factor"] == "extreme_heat" for r in risks)

    def test_ensiling_window(self):
        score, cls, pos, risks = compute_window_score(
            "ensiling", precipitation_mm=0.5, precipitation_probability=15, gust_kmh=20)
        assert score >= 75

    def test_haymaking_window(self):
        score, cls, pos, risks = compute_window_score(
            "haymaking", precipitation_mm=0, precipitation_probability=5,
            consecutive_dry_hours=72)
        assert score >= 75

    def test_stale_data_penalty(self):
        score_with_stale, _, _, _ = compute_window_score(
            "harvest_cut", precipitation_mm=0, precipitation_probability=10,
            data_age_minutes=200)
        score_fresh, _, _, _ = compute_window_score(
            "harvest_cut", precipitation_mm=0, precipitation_probability=10,
            data_age_minutes=10)
        assert score_with_stale < score_fresh


class TestCacheFreshness:
    def test_fresh(self):
        now = datetime.now(timezone.utc)
        fetched = now - timedelta(minutes=10)
        status, age = check_freshness(fetched, now)
        assert status == CacheStatus.FRESH.value

    def test_stale(self):
        now = datetime.now(timezone.utc)
        fetched = now - timedelta(minutes=60)
        status, age = check_freshness(fetched, now)
        assert status == CacheStatus.STALE.value

    def test_fallback(self):
        now = datetime.now(timezone.utc)
        fetched = now - timedelta(minutes=240)
        status, age = check_freshness(fetched, now)
        assert status == CacheStatus.FALLBACK.value

    def test_unavailable(self):
        now = datetime.now(timezone.utc)
        fetched = now - timedelta(hours=15)
        status, age = check_freshness(fetched, now)
        assert status == CacheStatus.UNAVAILABLE.value


class TestCacheExpiresAt:
    def test_current_default(self):
        now = datetime.now(timezone.utc)
        expires = compute_cache_expires_at("current", now)
        assert expires > now

    def test_custom_minutes(self):
        now = datetime.now(timezone.utc)
        expires = compute_cache_expires_at("current", now, cache_minutes=60)
        diff = (expires - now).total_seconds() / 60
        assert abs(diff - 60) < 1


class TestWindowResponse:
    def test_build(self):
        now = datetime.now(timezone.utc)
        resp = build_window_response(
            "harvest_cut", now, now + timedelta(hours=1),
            85.0, "favorable", [{"factor": "test"}], [], ["snap1"],
            FORMULA_VERSION, now)
        assert resp["window_type"] == "harvest_cut"
        assert resp["score"] == 85.0
        assert resp["classification"] == "favorable"
        assert resp["window_type_label"] == "Corte"


class TestRuleVersion:
    def test_formula_version(self):
        assert FORMULA_VERSION == "operational_windows.v1"

    def test_normalization_version(self):
        assert NORMALIZATION_VERSION == "weather_normalization.v1"


class TestWindowDefaults:
    def test_all_types_covered(self):
        for wt in WindowType:
            assert wt.value in WINDOW_DEFAULTS


class TestLabels:
    def test_all_window_types_labeled(self):
        for wt in WindowType:
            assert wt in WINDOW_TYPE_LABELS

    def test_all_classifications_labeled(self):
        for cls in WindowClassification:
            assert cls in CLASSIFICATION_LABELS
