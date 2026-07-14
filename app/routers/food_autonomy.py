"""Router da API de Autonomia Alimentar — endpoints privados."""
import re
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from auth import decode_token
from core.authorization import AuthorizationError, HiddenResourceError, ForbiddenError
from repositories.foundation import PostgresFoundationRepository
from repositories.food_autonomy import FoodAutonomyRepository
from services.food_autonomy import FoodAutonomyService
from schemas.food_autonomy import (
    SimulationRequest, ScenarioCreateRequest, ScenarioUpdateRequest,
    SimulationResponse, ScenarioListResponse, FeedItemSchema,
)

router = APIRouter(prefix="/api/v2/farms", tags=["food_autonomy"])
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def get_food_autonomy_repository():
    return FoodAutonomyRepository()


def get_auth_repository():
    return PostgresFoundationRepository()


def _request_id(request: Request) -> str:
    candidate = request.headers.get("x-request-id", "")
    return candidate if _REQUEST_ID.fullmatch(candidate) else str(uuid4())


def _subject(request: Request) -> str | None:
    token = request.cookies.get("access_token")
    payload = decode_token(token) if token else None
    return payload.get("sub") if payload else None


def _cache_headers(response: Response):
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"


def _handle_auth_error(exc, request_id):
    status_code = exc.status_code
    code = getattr(exc, "code", "authorization_denied")
    if code == "organization_context_required":
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": str(exc), "request_id": request_id},
    ) from exc


@router.post(
    "/{farm_uuid}/food-autonomy/simulate",
    response_model=SimulationResponse,
)
def simulate_food_autonomy(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    payload: SimulationRequest,
    repository=Depends(get_food_autonomy_repository),
    auth_repository=Depends(get_auth_repository),
):
    request_id = _request_id(request)
    _cache_headers(response)

    service = FoodAutonomyService(repository, auth_repository)
    try:
        result = service.simulate(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.post(
    "/{farm_uuid}/food-autonomy/scenarios",
)
def create_scenario(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    payload: ScenarioCreateRequest,
    repository=Depends(get_food_autonomy_repository),
    auth_repository=Depends(get_auth_repository),
):
    request_id = _request_id(request)
    _cache_headers(response)

    service = FoodAutonomyService(repository, auth_repository)
    try:
        result = service.create_scenario(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/food-autonomy/scenarios",
    response_model=ScenarioListResponse,
)
def list_scenarios(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    limit: int = 25,
    offset: int = 0,
    status: str | None = None,
    repository=Depends(get_food_autonomy_repository),
    auth_repository=Depends(get_auth_repository),
):
    request_id = _request_id(request)
    _cache_headers(response)

    if limit < 1 or limit > 100 or offset < 0:
        raise HTTPException(status_code=422, detail={
            "code": "invalid_pagination",
            "message": "Parâmetros de paginação inválidos",
            "request_id": request_id,
        })

    service = FoodAutonomyService(repository, auth_repository)
    try:
        result = service.list_scenarios(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            limit=limit,
            offset=offset,
            status_filter=status,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/food-autonomy/scenarios/{scenario_uuid}",
)
def get_scenario(
    farm_uuid: UUID,
    scenario_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_food_autonomy_repository),
    auth_repository=Depends(get_auth_repository),
):
    request_id = _request_id(request)
    _cache_headers(response)

    service = FoodAutonomyService(repository, auth_repository)
    try:
        result = service.get_scenario(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            scenario_uuid=scenario_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.put(
    "/{farm_uuid}/food-autonomy/scenarios/{scenario_uuid}",
)
def update_scenario(
    farm_uuid: UUID,
    scenario_uuid: UUID,
    request: Request,
    response: Response,
    payload: ScenarioUpdateRequest,
    repository=Depends(get_food_autonomy_repository),
    auth_repository=Depends(get_auth_repository),
):
    request_id = _request_id(request)
    _cache_headers(response)

    service = FoodAutonomyService(repository, auth_repository)
    try:
        result = service.update_scenario(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            scenario_uuid=scenario_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.delete(
    "/{farm_uuid}/food-autonomy/scenarios/{scenario_uuid}",
)
def archive_scenario(
    farm_uuid: UUID,
    scenario_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_food_autonomy_repository),
    auth_repository=Depends(get_auth_repository),
):
    request_id = _request_id(request)
    _cache_headers(response)

    service = FoodAutonomyService(repository, auth_repository)
    try:
        service.archive_scenario(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            scenario_uuid=scenario_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return {"status": "archived"}


@router.post(
    "/{farm_uuid}/food-autonomy/feeds",
)
def import_feed(
    farm_uuid: UUID,
    payload: FeedItemSchema,
    request: Request,
    response: Response,
):
    from decimal import Decimal
    qty = Decimal(str(payload.quantity_natural_kg))
    dm = Decimal(str(payload.dry_matter_pct))
    util = Decimal(str(payload.utilization_pct))
    usable = qty * (dm / 100) * (util / 100)

    return {
        "public_id": str(uuid4()),
        "feed_type": payload.feed_type,
        "name": payload.name,
        "quantity_natural_kg": str(qty),
        "dry_matter_pct": str(dm),
        "utilization_pct": str(util),
        "usable_dm_kg": f"{usable:.2f}",
        "notes": payload.notes,
    }
