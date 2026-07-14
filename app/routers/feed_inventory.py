"""Router da API de Estoque de Ração — endpoints privados."""
import os
import re
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from auth import decode_token
from core.authorization import AuthorizationError, HiddenResourceError, ForbiddenError
from repositories.foundation import PostgresFoundationRepository
from repositories.feed_inventory import FeedInventoryRepository
from services.feed_inventory import FeedInventoryService
from schemas.feed_inventory import (
    FacilityCreateRequest, FacilityUpdateRequest, FacilityResponse,
    FacilityListResponse, LotCreateRequest, LotUpdateRequest, LotResponse,
    LotListResponse, MovementCreateRequest, MovementResponse,
    MovementListResponse, WithdrawRequest, RecordLossRequest, AdjustRequest,
    DashboardResponse, ReconciliationResponse, AutonomySourceItem,
)

router = APIRouter(prefix="/api/v2/farms", tags=["feed_inventory"])
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
ENABLE_FEED_INVENTORY = os.getenv("ENABLE_FEED_INVENTORY", "false").lower() == "true"


def get_feed_inventory_repository():
    return FeedInventoryRepository()


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
    if code == "duplicate_request_id":
        status_code = 409
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": str(exc), "request_id": request_id},
    ) from exc


def _check_feature():
    if not ENABLE_FEED_INVENTORY:
        raise HTTPException(
            status_code=404,
            detail={"code": "feature_disabled", "message": "Estoque de Ração não está habilitado."},
        )


@router.get(
    "/{farm_uuid}/feed-inventory/dashboard",
    response_model=DashboardResponse,
)
def get_dashboard(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.get_dashboard(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.post(
    "/{farm_uuid}/feed-inventory/facilities",
)
def create_facility(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    payload: FacilityCreateRequest,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.create_facility(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/feed-inventory/facilities",
    response_model=FacilityListResponse,
)
def list_facilities(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    limit: int = 25,
    offset: int = 0,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    if limit < 1 or limit > 100 or offset < 0:
        raise HTTPException(status_code=422, detail={
            "code": "invalid_pagination",
            "message": "Parâmetros de paginação inválidos",
            "request_id": request_id,
        })

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.list_facilities(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            limit=limit,
            offset=offset,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/feed-inventory/facilities/{facility_uuid}",
)
def get_facility(
    farm_uuid: UUID,
    facility_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.get_facility(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            facility_uuid=facility_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.put(
    "/{farm_uuid}/feed-inventory/facilities/{facility_uuid}",
)
def update_facility(
    farm_uuid: UUID,
    facility_uuid: UUID,
    request: Request,
    response: Response,
    payload: FacilityUpdateRequest,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.update_facility(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            facility_uuid=facility_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.delete(
    "/{farm_uuid}/feed-inventory/facilities/{facility_uuid}",
)
def archive_facility(
    farm_uuid: UUID,
    facility_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        service.archive_facility(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            facility_uuid=facility_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return {"status": "archived"}


@router.post(
    "/{farm_uuid}/feed-inventory/lots",
)
def create_lot(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    payload: LotCreateRequest,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.create_lot(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/feed-inventory/lots",
    response_model=LotListResponse,
)
def list_lots(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    limit: int = 25,
    offset: int = 0,
    facility: str = "",
    feed_type: str = "",
    status: str = "",
    search: str = "",
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    if limit < 1 or limit > 100 or offset < 0:
        raise HTTPException(status_code=422, detail={
            "code": "invalid_pagination",
            "message": "Parâmetros de paginação inválidos",
            "request_id": request_id,
        })

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.list_lots(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            limit=limit,
            offset=offset,
            facility_uuid=facility,
            feed_type=feed_type,
            status=status,
            search=search,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/feed-inventory/lots/{lot_uuid}",
)
def get_lot(
    farm_uuid: UUID,
    lot_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.get_lot(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            lot_uuid=lot_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.put(
    "/{farm_uuid}/feed-inventory/lots/{lot_uuid}",
)
def update_lot(
    farm_uuid: UUID,
    lot_uuid: UUID,
    request: Request,
    response: Response,
    payload: LotUpdateRequest,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.update_lot(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            lot_uuid=lot_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.delete(
    "/{farm_uuid}/feed-inventory/lots/{lot_uuid}",
)
def archive_lot(
    farm_uuid: UUID,
    lot_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        service.archive_lot(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            lot_uuid=lot_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return {"status": "archived"}


@router.post(
    "/{farm_uuid}/feed-inventory/lots/{lot_uuid}/movements",
)
def create_movement(
    farm_uuid: UUID,
    lot_uuid: UUID,
    request: Request,
    response: Response,
    payload: MovementCreateRequest,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = payload.request_id or _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.create_movement(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            lot_uuid=lot_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/feed-inventory/lots/{lot_uuid}/movements",
    response_model=MovementListResponse,
)
def list_movements(
    farm_uuid: UUID,
    lot_uuid: UUID,
    request: Request,
    response: Response,
    limit: int = 50,
    offset: int = 0,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    if limit < 1 or limit > 100 or offset < 0:
        raise HTTPException(status_code=422, detail={
            "code": "invalid_pagination",
            "message": "Parâmetros de paginação inválidos",
            "request_id": request_id,
        })

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.list_movements(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            lot_uuid=lot_uuid,
            limit=limit,
            offset=offset,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/feed-inventory/lots/{lot_uuid}/movements/{movement_uuid}",
)
def get_movement(
    farm_uuid: UUID,
    lot_uuid: UUID,
    movement_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.get_movement(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            lot_uuid=lot_uuid,
            movement_uuid=movement_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.post(
    "/{farm_uuid}/feed-inventory/lots/{lot_uuid}/withdraw",
)
def withdraw_from_lot(
    farm_uuid: UUID,
    lot_uuid: UUID,
    request: Request,
    response: Response,
    payload: WithdrawRequest,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.withdraw_from_lot(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            lot_uuid=lot_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.post(
    "/{farm_uuid}/feed-inventory/lots/{lot_uuid}/record-loss",
)
def record_loss_on_lot(
    farm_uuid: UUID,
    lot_uuid: UUID,
    request: Request,
    response: Response,
    payload: RecordLossRequest,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.record_loss_on_lot(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            lot_uuid=lot_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.post(
    "/{farm_uuid}/feed-inventory/lots/{lot_uuid}/adjust",
)
def adjust_lot(
    farm_uuid: UUID,
    lot_uuid: UUID,
    request: Request,
    response: Response,
    payload: AdjustRequest,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.adjust_lot(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            lot_uuid=lot_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/feed-inventory/lots/{lot_uuid}/reconciliation",
    response_model=ReconciliationResponse,
)
def get_reconciliation(
    farm_uuid: UUID,
    lot_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.get_reconciliation(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            lot_uuid=lot_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/feed-inventory/autonomy-sources",
)
def get_autonomy_sources(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_feed_inventory_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = FeedInventoryService(repository, auth_repository)
    try:
        result = service.get_autonomy_sources(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result
