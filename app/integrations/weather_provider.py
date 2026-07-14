"""Provider adapter para dados meteorológicos — HTTP, timeout, retry, cache."""
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone, timedelta
from typing import Any

import urllib.request
import urllib.error

logger = logging.getLogger("wins_agro.weather_provider")

WEATHER_API_BASE_URL = os.getenv("WEATHER_API_BASE_URL", "")
WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
WEATHER_TIMEOUT_SECONDS = int(os.getenv("WEATHER_TIMEOUT_SECONDS", "10"))
WEATHER_PROVIDER = os.getenv("WEATHER_PROVIDER", "open-meteo")

_circuit_breaker_state = {
    "failures": 0,
    "last_failure_time": 0.0,
    "open_until": 0.0,
}
MAX_FAILURES = 5
CIRCUIT_BREAKER_COOLDOWN_SECONDS = 300


def _is_circuit_open() -> bool:
    now = time.time()
    if _circuit_breaker_state["failures"] >= MAX_FAILURES:
        if now < _circuit_breaker_state["open_until"]:
            return True
        _circuit_breaker_state["failures"] = 0
    return False


def _record_failure():
    now = time.time()
    _circuit_breaker_state["failures"] += 1
    _circuit_breaker_state["last_failure_time"] = now
    if _circuit_breaker_state["failures"] >= MAX_FAILURES:
        _circuit_breaker_state["open_until"] = now + CIRCUIT_BREAKER_COOLDOWN_SECONDS
        logger.warning("weather_circuit_breaker_open failures=%d", _circuit_breaker_state["failures"])


def _record_success():
    _circuit_breaker_state["failures"] = 0


def _http_get(url: str, params: dict | None = None) -> dict:
    if params:
        query_str = "&".join(f"{k}={v}" for k, v in params.items() if v is not None)
        if query_str:
            url = f"{url}?{query_str}"

    if _is_circuit_open():
        raise WeatherProviderError("circuit_breaker_open", "Provider temporariamente indisponível")

    headers = {"User-Agent": "WiNS-Hub-Agro/1.0", "Accept": "application/json"}
    if WEATHER_API_KEY:
        headers["Authorization"] = f"Bearer {WEATHER_API_KEY}"

    req = urllib.request.Request(url, headers=headers, method="GET")
    last_error = None

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=WEATHER_TIMEOUT_SECONDS) as resp:
                body = resp.read().decode("utf-8")
                _record_success()
                return json.loads(body)
        except urllib.error.HTTPError as e:
            last_error = e
            if e.code in (401, 403, 404):
                raise WeatherProviderError(f"http_{e.code}", f"Erro HTTP {e.code}")
            if e.code == 429:
                raise WeatherProviderError("rate_limited", "Limite de requisições atingido")
            if attempt < 2:
                time.sleep(1 * (attempt + 1))
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last_error = e
            if attempt < 2:
                time.sleep(1 * (attempt + 1))

    _record_failure()
    raise WeatherProviderError("request_failed", f"Falha após 3 tentativas: {last_error}")


class WeatherProviderError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(message)


def _parse_open_meteo_current(data: dict) -> dict:
    current = data.get("current", {})
    return {
        "temperature_c": current.get("temperature_2m"),
        "feels_like_c": current.get("apparent_temperature"),
        "humidity_pct": current.get("relative_humidity_2m"),
        "precipitation_mm": current.get("precipitation"),
        "wind_kmh": current.get("wind_speed_10m"),
        "gust_kmh": current.get("wind_gusts_10m"),
        "wind_direction_deg": current.get("wind_direction_10m"),
        "cloud_cover_pct": current.get("cloud_cover"),
        "condition_code": None,
        "condition_description": None,
        "observation_time": current.get("time"),
    }


def _parse_open_meteo_hourly(data: dict) -> list[dict]:
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    result = []
    for i, t in enumerate(times):
        result.append({
            "timestamp": t,
            "temperature_c": hourly.get("temperature_2m", [None])[i] if i < len(hourly.get("temperature_2m", [])) else None,
            "humidity_pct": hourly.get("relative_humidity_2m", [None])[i] if i < len(hourly.get("relative_humidity_2m", [])) else None,
            "precipitation_probability": hourly.get("precipitation_probability", [None])[i] if i < len(hourly.get("precipitation_probability", [])) else None,
            "precipitation_mm": hourly.get("precipitation", [None])[i] if i < len(hourly.get("precipitation", [])) else None,
            "wind_kmh": hourly.get("wind_speed_10m", [None])[i] if i < len(hourly.get("wind_speed_10m", [])) else None,
            "gust_kmh": hourly.get("wind_gusts_10m", [None])[i] if i < len(hourly.get("wind_gusts_10m", [])) else None,
            "cloud_cover_pct": hourly.get("cloud_cover", [None])[i] if i < len(hourly.get("cloud_cover", [])) else None,
        })
    return result


def _parse_open_meteo_daily(data: dict) -> list[dict]:
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    result = []
    for i, d in enumerate(dates):
        result.append({
            "date": d,
            "temperature_min_c": daily.get("temperature_2m_min", [None])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
            "temperature_max_c": daily.get("temperature_2m_max", [None])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
            "precipitation_sum_mm": daily.get("precipitation_sum", [None])[i] if i < len(daily.get("precipitation_sum", [])) else None,
            "precipitation_probability_max": daily.get("precipitation_probability_max", [None])[i] if i < len(daily.get("precipitation_probability_max", [])) else None,
            "wind_speed_max_kmh": daily.get("wind_speed_10m_max", [None])[i] if i < len(daily.get("wind_speed_10m_max", [])) else None,
            "wind_gusts_max_kmh": daily.get("wind_gusts_10m_max", [None])[i] if i < len(daily.get("wind_gusts_10m_max", [])) else None,
            "sunrise": daily.get("sunrise", [None])[i] if i < len(daily.get("sunrise", [])) else None,
            "sunset": daily.get("sunset", [None])[i] if i < len(daily.get("sunset", [])) else None,
        })
    return result


def _parse_open_meteo_history(data: dict) -> list[dict]:
    daily = data.get("daily", {})
    dates = daily.get("time", [])
    result = []
    for i, d in enumerate(dates):
        result.append({
            "date": d,
            "precipitation_sum_mm": daily.get("precipitation_sum", [None])[i] if i < len(daily.get("precipitation_sum", [])) else None,
            "temperature_min_c": daily.get("temperature_2m_min", [None])[i] if i < len(daily.get("temperature_2m_min", [])) else None,
            "temperature_max_c": daily.get("temperature_2m_max", [None])[i] if i < len(daily.get("temperature_2m_max", [])) else None,
        })
    return result


def fetch_current_weather(latitude: float, longitude: float, timezone_str: str = "auto") -> dict:
    if WEATHER_PROVIDER == "open-meteo":
        base = WEATHER_API_BASE_URL or "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,wind_speed_10m,wind_gusts_10m,wind_direction_10m,cloud_cover",
            "timezone": timezone_str,
        }
        raw = _http_get(base, params)
        return {"current": _parse_open_meteo_current(raw), "raw_checksum": hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()[:16]}
    raise WeatherProviderError("unknown_provider", f"Provider desconhecido: {WEATHER_PROVIDER}")


def fetch_hourly_forecast(latitude: float, longitude: float, timezone_str: str = "auto", hours: int = 72) -> dict:
    if WEATHER_PROVIDER == "open-meteo":
        base = WEATHER_API_BASE_URL or "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,wind_speed_10m,wind_gusts_10m,cloud_cover",
            "timezone": timezone_str,
            "forecast_hours": hours,
        }
        raw = _http_get(base, params)
        return {"hourly": _parse_open_meteo_hourly(raw), "raw_checksum": hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()[:16]}
    raise WeatherProviderError("unknown_provider", f"Provider desconhecido: {WEATHER_PROVIDER}")


def fetch_daily_forecast(latitude: float, longitude: float, timezone_str: str = "auto", days: int = 7) -> dict:
    if WEATHER_PROVIDER == "open-meteo":
        base = WEATHER_API_BASE_URL or "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "temperature_2m_min,temperature_2m_max,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,sunrise,sunset",
            "timezone": timezone_str,
            "forecast_days": days,
        }
        raw = _http_get(base, params)
        return {"daily": _parse_open_meteo_daily(raw), "raw_checksum": hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()[:16]}
    raise WeatherProviderError("unknown_provider", f"Provider desconhecido: {WEATHER_PROVIDER}")


def fetch_recent_history(latitude: float, longitude: float, timezone_str: str = "auto", days: int = 7) -> dict:
    if WEATHER_PROVIDER == "open-meteo":
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)
        base = WEATHER_API_BASE_URL or "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "daily": "precipitation_sum,temperature_2m_min,temperature_2m_max",
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "timezone": "auto",
        }
        raw = _http_get(base, params)
        return {"daily": _parse_open_meteo_history(raw), "raw_checksum": hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()[:16]}
    raise WeatherProviderError("unknown_provider", f"Provider desconhecido: {WEATHER_PROVIDER}")


def compute_checksum(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]
