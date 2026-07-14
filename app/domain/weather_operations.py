"""Domínio de Clima e Janelas Operacionais — cálculos puros, sem banco."""
from dataclasses import dataclass
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from types import MappingProxyType


FORMULA_VERSION = "operational_windows.v1"
NORMALIZATION_VERSION = "weather_normalization.v1"


class WindowType(str, Enum):
    HARVEST_CUT = "harvest_cut"
    ENSILING = "ensiling"
    HAYMAKING = "haymaking"
    PASTURE_MANAGEMENT = "pasture_management"
    FIELD_OPERATION = "field_operation"
    HEAT_ATTENTION = "heat_attention"


WINDOW_TYPE_LABELS = {
    WindowType.HARVEST_CUT: "Corte",
    WindowType.ENSILING: "Ensilagem",
    WindowType.HAYMAKING: "Fenação",
    WindowType.PASTURE_MANAGEMENT: "Manejo de pastagem",
    WindowType.FIELD_OPERATION: "Operação de campo",
    WindowType.HEAT_ATTENTION: "Atenção ao calor",
}


class WindowClassification(str, Enum):
    FAVORABLE = "favorable"
    ATTENTION = "attention"
    UNFAVORABLE = "unfavorable"
    INSUFFICIENT_DATA = "insufficient_data"


CLASSIFICATION_LABELS = {
    WindowClassification.FAVORABLE: "Favorável",
    WindowClassification.ATTENTION: "Atenção",
    WindowClassification.UNFAVORABLE: "Desfavorável",
    WindowClassification.INSUFFICIENT_DATA: "Dados insuficientes",
}


class WeatherStatus(str, Enum):
    ACTIVE = "active"
    STALE = "stale"
    ERROR = "error"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"


WEATHER_STATUS_LABELS = {
    WeatherStatus.ACTIVE: "Ativo",
    WeatherStatus.STALE: "Desatualizado",
    WeatherStatus.ERROR: "Erro",
    WeatherStatus.DISABLED: "Desativado",
    WeatherStatus.NOT_CONFIGURED: "Não configurado",
}


class SnapshotType(str, Enum):
    CURRENT = "current"
    HOURLY_FORECAST = "hourly_forecast"
    DAILY_FORECAST = "daily_forecast"
    RECENT_HISTORY = "recent_history"


class CacheStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    FALLBACK = "fallback"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class WeatherSnapshot:
    snapshot_type: str
    period_start: datetime | None
    period_end: datetime | None
    payload_normalized: dict
    provider: str
    provider_reference: str | None
    normalization_version: str
    fetched_at: datetime
    expires_at: datetime
    stale_after: datetime
    checksum: str


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def normalize_temperature_celsius(value) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < -90 or v > 60:
        return None
    return round(v, 2)


def normalize_humidity_pct(value) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0 or v > 100:
        return None
    return round(v, 1)


def normalize_precipitation_mm(value) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    return round(v, 2)


def normalize_wind_kmh(value) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    return round(v, 1)


def normalize_cloud_cover_pct(value) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0 or v > 100:
        return None
    return round(v, 1)


def normalize_weather_condition(condition: dict) -> dict:
    return {
        "temperature_c": normalize_temperature_celsius(condition.get("temperature_c")),
        "feels_like_c": normalize_temperature_celsius(condition.get("feels_like_c")),
        "humidity_pct": normalize_humidity_pct(condition.get("humidity_pct")),
        "precipitation_mm": normalize_precipitation_mm(condition.get("precipitation_mm")),
        "wind_kmh": normalize_wind_kmh(condition.get("wind_kmh")),
        "gust_kmh": normalize_wind_kmh(condition.get("gust_kmh")),
        "wind_direction_deg": condition.get("wind_direction_deg"),
        "cloud_cover_pct": normalize_cloud_cover_pct(condition.get("cloud_cover_pct")),
        "condition_code": condition.get("condition_code"),
        "condition_description": condition.get("condition_description"),
        "observation_time": condition.get("observation_time"),
    }


def classify_temperature(temperature_c: float | None, feels_like_c: float | None) -> str:
    ref = feels_like_c if feels_like_c is not None else temperature_c
    if ref is None:
        return "normal"
    if ref >= 40:
        return "elevated"
    if ref >= 35:
        return "attention"
    return "normal"


def compute_window_score(
    window_type: str,
    *,
    precipitation_mm: float | None = None,
    precipitation_probability: float | None = None,
    wind_kmh: float | None = None,
    gust_kmh: float | None = None,
    temperature_c: float | None = None,
    feels_like_c: float | None = None,
    is_daytime: bool | None = None,
    has_severe_alert: bool = False,
    data_age_minutes: float | None = None,
    required_fields_present: bool = True,
    consecutive_dry_hours: int | None = None,
) -> tuple[float, str, list[dict], list[dict]]:
    if not required_fields_present:
        return 0, WindowClassification.INSUFFICIENT_DATA.value, [], [{"factor": "missing_required_fields", "impact": -100}]

    score = 100.0
    positive = []
    risks = []

    if has_severe_alert:
        score -= 40
        risks.append({"factor": "severe_weather_alert", "impact": -40, "description": "Alerta severo detectado"})

    if precipitation_mm is not None:
        if precipitation_mm <= 0:
            score += 0
            positive.append({"factor": "no_precipitation", "impact": 0, "description": "Sem precipitação prevista"})
        elif precipitation_mm <= 1:
            score -= 5
            positive.append({"factor": "low_precipitation", "impact": -5, "description": f"Precipitação baixa ({precipitation_mm} mm)"})
        elif precipitation_mm <= 5:
            score -= 20
            risks.append({"factor": "moderate_precipitation", "impact": -20, "description": f"Precipitação moderada ({precipitation_mm} mm)"})
        else:
            score -= 40
            risks.append({"factor": "high_precipitation", "impact": -40, "description": f"Precipitação alta ({precipitation_mm} mm)"})

    if precipitation_probability is not None:
        if precipitation_probability < 30:
            positive.append({"factor": "low_rain_probability", "impact": 0, "description": f"Baixa probabilidade de chuva ({precipitation_probability}%)"})
        elif precipitation_probability < 60:
            score -= 15
            risks.append({"factor": "moderate_rain_probability", "impact": -15, "description": f"Probabilidade moderada ({precipitation_probability}%)"})
        else:
            score -= 30
            risks.append({"factor": "high_rain_probability", "impact": -30, "description": f"Alta probabilidade de chuva ({precipitation_probability}%)"})

    if gust_kmh is not None:
        if gust_kmh > 60:
            score -= 25
            risks.append({"factor": "strong_gusts", "impact": -25, "description": f"Rajadas fortes ({gust_kmh} km/h)"})
        elif gust_kmh > 40:
            score -= 10
            risks.append({"factor": "moderate_gusts", "impact": -10, "description": f"Rajadas moderadas ({gust_kmh} km/h)"})

    if wind_kmh is not None:
        if wind_kmh > 50:
            score -= 15
            risks.append({"factor": "strong_wind", "impact": -15, "description": f"Vento forte ({wind_kmh} km/h)"})

    if window_type == WindowType.HEAT_ATTENTION.value:
        temp_ref = feels_like_c if feels_like_c is not None else temperature_c
        if temp_ref is not None:
            if temp_ref >= 40:
                score -= 30
                risks.append({"factor": "extreme_heat", "impact": -30, "description": f"Calor extremo ({temp_ref}°C)"})
            elif temp_ref >= 35:
                score -= 15
                risks.append({"factor": "high_heat", "impact": -15, "description": f"Calor elevado ({temp_ref}°C)"})
            elif temp_ref >= 30:
                score -= 5
                risks.append({"factor": "moderate_heat", "impact": -5, "description": f"Calor moderado ({temp_ref}°C)"})
            else:
                positive.append({"factor": "normal_temperature", "impact": 0, "description": f"Temperatura normal ({temp_ref}°C)"})

    if window_type == WindowType.HAYMAKING.value:
        if consecutive_dry_hours is not None and consecutive_dry_hours >= 48:
            positive.append({"factor": "long_dry_sequence", "impact": 5, "description": f"{consecutive_dry_hours}h sem chuva"})
            score += 5
        elif consecutive_dry_hours is not None and consecutive_dry_hours < 24:
            score -= 15
            risks.append({"factor": "short_dry_sequence", "impact": -15, "description": f"Apenas {consecutive_dry_hours}h sem chuva"})

    if data_age_minutes is not None:
        if data_age_minutes > 180:
            score -= 10
            risks.append({"factor": "stale_data", "impact": -10, "description": f"Dados desatualizados ({int(data_age_minutes)} min)"})
        elif data_age_minutes > 60:
            score -= 5
            risks.append({"factor": "aging_data", "impact": -5, "description": f"Dados com {int(data_age_minutes)} min"})

    if is_daytime is False and window_type == WindowType.HARVEST_CUT.value:
        score -= 5
        risks.append({"factor": "nighttime", "impact": -5, "description": "Período noturno"})

    score = max(0, min(100, score))

    if score >= 75:
        classification = WindowClassification.FAVORABLE.value
    elif score >= 45:
        classification = WindowClassification.ATTENTION.value
    else:
        classification = WindowClassification.UNFAVORABLE.value

    return round(score, 1), classification, positive, risks


def check_freshness(fetched_at: datetime, now: datetime | None = None) -> tuple[str, float]:
    if now is None:
        now = datetime.now(timezone.utc)
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    age = (now - fetched_at).total_seconds() / 60.0
    if age <= 30:
        return CacheStatus.FRESH.value, round(age, 1)
    if age <= 180:
        return CacheStatus.STALE.value, round(age, 1)
    if age <= 720:
        return CacheStatus.FALLBACK.value, round(age, 1)
    return CacheStatus.UNAVAILABLE.value, round(age, 1)


def compute_cache_expires_at(
    snapshot_type: str,
    fetched_at: datetime,
    cache_minutes: int | None = None,
) -> datetime:
    defaults = {
        SnapshotType.CURRENT.value: 20,
        SnapshotType.HOURLY_FORECAST.value: 45,
        SnapshotType.DAILY_FORECAST.value: 120,
        SnapshotType.RECENT_HISTORY.value: 720,
    }
    minutes = cache_minutes or defaults.get(snapshot_type, 30)
    return fetched_at + timedelta(minutes=minutes)


def build_window_response(
    window_type: str,
    period_start: datetime,
    period_end: datetime,
    score: float,
    classification: str,
    positive_factors: list[dict],
    risk_factors: list[dict],
    data_snapshot_ids: list[str],
    rule_version: str,
    evaluated_at: datetime,
    forecast_updated_at: datetime | None = None,
    warnings: list[str] | None = None,
) -> dict:
    return {
        "window_type": window_type,
        "window_type_label": WINDOW_TYPE_LABELS.get(WindowType(window_type), window_type),
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "score": score,
        "classification": classification,
        "classification_label": CLASSIFICATION_LABELS.get(WindowClassification(classification), classification),
        "positive_factors": positive_factors,
        "risk_factors": risk_factors,
        "data_snapshot_ids": data_snapshot_ids,
        "rule_version": rule_version,
        "evaluated_at": evaluated_at.isoformat(),
        "forecast_updated_at": forecast_updated_at.isoformat() if forecast_updated_at else None,
        "warnings": warnings or [],
    }


WINDOW_DEFAULTS = {
    WindowType.HARVEST_CUT.value: {"max_precipitation_mm": 1, "max_probability_pct": 30, "max_gust_kmh": 40},
    WindowType.ENSILING.value: {"max_precipitation_mm": 2, "max_probability_pct": 40, "max_gust_kmh": 45},
    WindowType.HAYMAKING.value: {"min_consecutive_dry_hours": 48, "max_precipitation_mm": 0.5, "max_probability_pct": 20},
    WindowType.PASTURE_MANAGEMENT.value: {"max_precipitation_mm": 10, "max_temperature_c": 35},
    WindowType.FIELD_OPERATION.value: {"max_precipitation_mm": 5, "max_gust_kmh": 50},
    WindowType.HEAT_ATTENTION.value: {"attention_temperature_c": 35, "elevated_temperature_c": 40},
}
