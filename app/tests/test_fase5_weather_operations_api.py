"""Testes de API do módulo de Clima e Janelas Operacionais."""
import pytest
pytest.importorskip("pydantic", reason="Pydantic é validado dentro do staging_api")
from pydantic import ValidationError
from schemas.weather_operations import (
    WeatherProfileCreateRequest, WeatherProfileUpdateRequest,
    EvaluationSaveRequest, CurrentWeatherResponse, HourlyForecastItem,
    DailyForecastItem, RecentRainfallItem, OperationalWindowItem,
)


def test_profile_create_valid():
    p = WeatherProfileCreateRequest(latitude=-12.64, longitude=-55.72)
    assert p.latitude == -12.64
    assert p.timezone == "America/Sao_Paulo"


def test_profile_create_invalid_latitude():
    with pytest.raises(ValidationError):
        WeatherProfileCreateRequest(latitude=-100, longitude=-55.72)


def test_profile_create_invalid_longitude():
    with pytest.raises(ValidationError):
        WeatherProfileCreateRequest(latitude=-12.64, longitude=200)


def test_profile_update_optional():
    p = WeatherProfileUpdateRequest(latitude=-10.0)
    assert p.latitude == -10.0
    assert p.longitude is None


def test_evaluation_save_valid():
    from datetime import datetime, timezone
    e = EvaluationSaveRequest(
        window_type="harvest_cut",
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc),
        score=85.0,
        classification="favorable",
    )
    assert e.score == 85.0


def test_evaluation_save_score_bounds():
    from datetime import datetime, timezone
    with pytest.raises(ValidationError):
        EvaluationSaveRequest(
            window_type="harvest_cut",
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            score=101,
            classification="favorable",
        )


def test_router_exposes_required_operations(monkeypatch):
    monkeypatch.setenv("ENABLE_WEATHER_OPERATIONS", "true")
    import importlib, routers.weather_operations as module
    module = importlib.reload(module)
    paths = {(r.path, next(iter(r.methods))) for r in module.router.routes}
    rendered = "\n".join(f"{m} {p}" for p, m in paths)
    for fragment in ("/profile", "/current", "/forecast/hourly", "/forecast/daily",
                     "/rainfall/recent", "/refresh", "/operational-windows",
                     "/dashboard", "/evaluations", "/pasture-context"):
        assert fragment in rendered


def test_current_weather_response_fields():
    from datetime import datetime, timezone
    r = CurrentWeatherResponse(
        temperature_c=25, feels_like_c=27, humidity_pct=60,
        precipitation_mm=0, wind_kmh=10, gust_kmh=15,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        expires_at=datetime.now(timezone.utc).isoformat(),
        source="provider", cache_status="fresh", stale=False,
        age_minutes=0, provider="open-meteo",
        normalization_version="weather_normalization.v1",
    )
    assert r.temperature_c == 25


def test_hourly_forecast_item():
    i = HourlyForecastItem(
        timestamp="2026-01-01T12:00",
        temperature_c=25, humidity_pct=60,
        precipitation_probability=10, precipitation_mm=0,
        wind_kmh=10, gust_kmh=15, cloud_cover_pct=30,
    )
    assert i.temperature_c == 25


def test_daily_forecast_item():
    d = DailyForecastItem(
        date="2026-01-01",
        temperature_min_c=18, temperature_max_c=32,
        precipitation_sum_mm=0, precipitation_probability_max=10,
        wind_speed_max_kmh=20, wind_gusts_max_kmh=30,
    )
    assert d.temperature_max_c == 32
