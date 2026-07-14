"""Schemas Pydantic para a API de Clima e Janelas Operacionais."""
from datetime import date, datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class WeatherProfileCreateRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    timezone: str = Field(default="America/Sao_Paulo", max_length=50)
    provider: str = Field(default="open-meteo", max_length=50)
    enabled: bool = Field(default=True)
    refresh_interval_minutes: int = Field(default=20, ge=10, le=360)
    forecast_days: int = Field(default=7, ge=1, le=16)
    notes: str = Field(default="", max_length=2000)


class WeatherProfileUpdateRequest(BaseModel):
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    timezone: Optional[str] = Field(default=None, max_length=50)
    provider: Optional[str] = Field(default=None, max_length=50)
    enabled: Optional[bool] = None
    refresh_interval_minutes: Optional[int] = Field(default=None, ge=10, le=360)
    forecast_days: Optional[int] = Field(default=None, ge=1, le=16)
    notes: Optional[str] = Field(default=None, max_length=2000)


class WeatherProfileResponse(BaseModel):
    public_id: str
    latitude: float
    longitude: float
    timezone: str
    provider: str
    enabled: bool
    refresh_interval_minutes: int
    forecast_days: int
    status: str
    status_label: str
    last_attempt_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error_at: Optional[str] = None
    last_error_code: Optional[str] = None
    notes: str
    created_at: str
    updated_at: str


class CurrentWeatherResponse(BaseModel):
    temperature_c: Optional[float] = None
    feels_like_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_kmh: Optional[float] = None
    gust_kmh: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    cloud_cover_pct: Optional[float] = None
    condition_code: Optional[str] = None
    condition_description: Optional[str] = None
    observation_time: Optional[str] = None
    fetched_at: str
    expires_at: str
    source: str
    cache_status: str
    stale: bool
    age_minutes: float
    provider: str
    normalization_version: str


class HourlyForecastItem(BaseModel):
    timestamp: str
    temperature_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    precipitation_probability: Optional[float] = None
    precipitation_mm: Optional[float] = None
    wind_kmh: Optional[float] = None
    gust_kmh: Optional[float] = None
    cloud_cover_pct: Optional[float] = None


class HourlyForecastResponse(BaseModel):
    items: list[HourlyForecastItem]
    fetched_at: str
    expires_at: str
    source: str
    cache_status: str
    stale: bool
    age_minutes: float
    provider: str


class DailyForecastItem(BaseModel):
    date: str
    temperature_min_c: Optional[float] = None
    temperature_max_c: Optional[float] = None
    precipitation_sum_mm: Optional[float] = None
    precipitation_probability_max: Optional[float] = None
    wind_speed_max_kmh: Optional[float] = None
    wind_gusts_max_kmh: Optional[float] = None
    sunrise: Optional[str] = None
    sunset: Optional[str] = None


class DailyForecastResponse(BaseModel):
    items: list[DailyForecastItem]
    fetched_at: str
    expires_at: str
    source: str
    cache_status: str
    stale: bool
    age_minutes: float
    provider: str


class RecentRainfallItem(BaseModel):
    date: str
    precipitation_sum_mm: Optional[float] = None
    temperature_min_c: Optional[float] = None
    temperature_max_c: Optional[float] = None


class RecentRainfallResponse(BaseModel):
    items: list[RecentRainfallItem]
    total_mm: float
    fetched_at: str
    source: str
    cache_status: str
    stale: bool
    age_minutes: float
    provider: str


class OperationalWindowItem(BaseModel):
    window_type: str
    window_type_label: str
    period_start: str
    period_end: str
    score: float
    classification: str
    classification_label: str
    positive_factors: list[dict]
    risk_factors: list[dict]
    rule_version: str
    evaluated_at: str
    forecast_updated_at: Optional[str] = None
    warnings: list[str]


class OperationalWindowsResponse(BaseModel):
    items: list[OperationalWindowItem]
    evaluated_at: str
    rule_version: str
    source: str
    cache_status: str


class DashboardResponse(BaseModel):
    current: Optional[CurrentWeatherResponse] = None
    forecast_summary: list[DailyForecastItem] = []
    recent_rainfall_mm: float = 0
    upcoming_favorable_windows: list[OperationalWindowItem] = []
    risks: list[str] = []
    integration_status: str
    last_updated: Optional[str] = None
    provider: str
    source: str
    cache_status: str


class EvaluationSaveRequest(BaseModel):
    window_type: str
    period_start: datetime
    period_end: datetime
    score: float = Field(ge=0, le=100)
    classification: str
    positive_factors: list[dict] = Field(default=[])
    risk_factors: list[dict] = Field(default=[])
    related_harvest_plan_uuid: Optional[UUID] = None


class EvaluationResponse(BaseModel):
    public_id: str
    window_type: str
    period_start: str
    period_end: str
    score: float
    classification: str
    positive_factors: list[dict]
    risk_factors: list[dict]
    rule_version: str
    evaluated_at: str
    created_at: str


class EvaluationListResponse(BaseModel):
    items: list[EvaluationResponse]
    total: int


class HarvestWeatherContextResponse(BaseModel):
    plan_uuid: str
    plan_name: str
    plan_start_date: str
    plan_end_date: str
    forecast_during_plan: list[DailyForecastItem]
    expected_precipitation_mm: float
    max_precipitation_probability: float
    cut_score: Optional[OperationalWindowItem] = None
    ensiling_score: Optional[OperationalWindowItem] = None
    risk_factors: list[str]
    data_freshness: str
    warnings: list[str]


class PastureWeatherContextResponse(BaseModel):
    recent_rainfall_mm: float
    forecast_rainfall_mm: float
    current_temperature_c: Optional[float] = None
    heat_status: str
    last_updated: Optional[str] = None
    measurement_stale_days: Optional[int] = None
    warnings: list[str]
