"""Router da API de Clima e Janelas Operacionais — endpoints privados."""
import os
import re
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from auth import decode_token
from core.authorization import AuthorizationError, HiddenResourceError, ForbiddenError
from repositories.foundation import PostgresFoundationRepository
from repositories.weather_operations import WeatherOperationsRepository
from schemas.weather_operations import (
    WeatherProfileCreateRequest, WeatherProfileUpdateRequest, WeatherProfileResponse,
    CurrentWeatherResponse, HourlyForecastResponse, DailyForecastResponse,
    RecentRainfallResponse, OperationalWindowsResponse, DashboardResponse,
    EvaluationSaveRequest, EvaluationListResponse, HarvestWeatherContextResponse,
    PastureWeatherContextResponse,
)
from services.weather_operations import WeatherService

router = APIRouter(prefix="/api/v2/farms", tags=["weather_operations"])
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
ENABLE_WEATHER_OPERATIONS = os.getenv("ENABLE_WEATHER_OPERATIONS", "false").lower() in {"1", "true", "yes"}


def get_weather_repository():
    return WeatherOperationsRepository()

def get_auth_repository():
    return PostgresFoundationRepository()

def _subject(request):
    token = request.cookies.get("access_token")
    payload = decode_token(token) if token else None
    return payload.get("sub") if payload else None

def _request_id(request):
    value = request.headers.get("x-request-id", "")
    return value if _REQUEST_ID.fullmatch(value) else str(uuid4())

def _headers(response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"

def _check_feature():
    if not ENABLE_WEATHER_OPERATIONS:
        raise HTTPException(404, detail={"code": "feature_disabled", "message": "Clima e Operações não está habilitado."})

def _error(exc, request_id):
    if isinstance(exc, ForbiddenError):
        status, code = exc.status_code, exc.code
    else:
        status, code = getattr(exc, "status_code", 403), getattr(exc, "code", "authorization_denied")
    raise HTTPException(status, detail={"code": code, "message": str(exc), "request_id": request_id}) from exc

def _service(repository, auth_repository):
    return WeatherService(repository, auth_repository)


@router.get("/{farm_uuid}/weather-operations/profile")
def get_profile(farm_uuid: UUID, request: Request, response: Response,
                repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).get_profile(subject=_subject(request), farm_public_id=farm_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.put("/{farm_uuid}/weather-operations/profile")
def update_profile(farm_uuid: UUID, payload: WeatherProfileCreateRequest, request: Request, response: Response,
                   repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).create_or_update_profile(
            subject=_subject(request), farm_public_id=farm_uuid, payload=payload.model_dump(), request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.get("/{farm_uuid}/weather-operations/current")
def get_current(farm_uuid: UUID, request: Request, response: Response,
                repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).get_current(subject=_subject(request), farm_public_id=farm_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.get("/{farm_uuid}/weather-operations/forecast/hourly")
def get_hourly(farm_uuid: UUID, request: Request, response: Response,
               repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).get_hourly_forecast(subject=_subject(request), farm_public_id=farm_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.get("/{farm_uuid}/weather-operations/forecast/daily")
def get_daily(farm_uuid: UUID, request: Request, response: Response,
              repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).get_daily_forecast(subject=_subject(request), farm_public_id=farm_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.get("/{farm_uuid}/weather-operations/rainfall/recent")
def get_rainfall(farm_uuid: UUID, request: Request, response: Response,
                 repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).get_recent_rainfall(subject=_subject(request), farm_public_id=farm_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.post("/{farm_uuid}/weather-operations/refresh")
def refresh(farm_uuid: UUID, request: Request, response: Response,
            repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).refresh(subject=_subject(request), farm_public_id=farm_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.get("/{farm_uuid}/weather-operations/operational-windows")
def get_windows(farm_uuid: UUID, request: Request, response: Response,
                window_type: str | None = None,
                repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).get_operational_windows(
            subject=_subject(request), farm_public_id=farm_uuid, request_id=rid, window_type=window_type)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.get("/{farm_uuid}/weather-operations/dashboard")
def dashboard(farm_uuid: UUID, request: Request, response: Response,
              repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).get_dashboard(subject=_subject(request), farm_public_id=farm_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.post("/{farm_uuid}/weather-operations/evaluations")
def save_evaluation(farm_uuid: UUID, payload: EvaluationSaveRequest, request: Request, response: Response,
                    repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).save_evaluation(
            subject=_subject(request), farm_public_id=farm_uuid, payload=payload.model_dump(), request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.get("/{farm_uuid}/weather-operations/evaluations")
def list_evaluations(farm_uuid: UUID, request: Request, response: Response,
                     limit: int = 25, offset: int = 0, window_type: str | None = None,
                     repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).list_evaluations(
            subject=_subject(request), farm_public_id=farm_uuid, request_id=rid,
            limit=limit, offset=offset, window_type=window_type)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.get("/{farm_uuid}/weather-operations/pasture-context")
def get_pasture_context(farm_uuid: UUID, request: Request, response: Response,
                        repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).get_pasture_weather_context(
            subject=_subject(request), farm_public_id=farm_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)

@router.get("/{farm_uuid}/weather-operations/harvest-plans/{plan_uuid}/weather-context")
def get_harvest_context(farm_uuid: UUID, plan_uuid: UUID, request: Request, response: Response,
                        repository=Depends(get_weather_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try:
        return _service(repository, auth_repository).get_harvest_weather_context(
            subject=_subject(request), farm_public_id=farm_uuid, plan_uuid=str(plan_uuid), request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _error(exc, rid)
