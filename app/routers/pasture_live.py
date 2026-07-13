"""Router da API de Pasto Vivo — endpoints privados."""
import os
import re
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from auth import decode_token
from core.authorization import AuthorizationError, HiddenResourceError, ForbiddenError
from repositories.foundation import PostgresFoundationRepository
from repositories.pasture_live import PastureLiveRepository
from services.pasture_live import PastureLiveService
from schemas.pasture_live import (
    PaddockCreateRequest, PaddockUpdateRequest, PaddockResponse,
    PaddockListResponse, MeasurementCreateRequest, MeasurementResponse,
    MeasurementListResponse, EventCreateRequest, EventListResponse,
    DashboardResponse, AutonomySourceItem,
    StartGrazingRequest, StartGrazingResponse,
    FinishGrazingRequest, FinishGrazingResponse,
)

router = APIRouter(prefix="/api/v2/farms", tags=["pasture_live"])
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")
ENABLE_PASTURE_LIVE = os.getenv("ENABLE_PASTURE_LIVE", "false").lower() == "true"


def get_pasture_live_repository():
    return PastureLiveRepository()


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


def _check_feature():
    if not ENABLE_PASTURE_LIVE:
        raise HTTPException(
            status_code=404,
            detail={"code": "feature_disabled", "message": "Pasto Vivo não está habilitado."},
        )


@router.get(
    "/{farm_uuid}/pasture-live/dashboard",
    response_model=DashboardResponse,
)
def get_dashboard(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
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
    "/{farm_uuid}/pasture-live/paddocks",
)
def create_paddock(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    payload: PaddockCreateRequest,
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.create_paddock(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/pasture-live/paddocks",
    response_model=PaddockListResponse,
)
def list_paddocks(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    limit: int = 25,
    offset: int = 0,
    repository=Depends(get_pasture_live_repository),
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

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.list_paddocks(
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
    "/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}",
)
def get_paddock(
    farm_uuid: UUID,
    paddock_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.get_paddock(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            paddock_uuid=paddock_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.put(
    "/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}",
)
def update_paddock(
    farm_uuid: UUID,
    paddock_uuid: UUID,
    request: Request,
    response: Response,
    payload: PaddockUpdateRequest,
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.update_paddock(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            paddock_uuid=paddock_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.delete(
    "/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}",
)
def archive_paddock(
    farm_uuid: UUID,
    paddock_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
    try:
        service.archive_paddock(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            paddock_uuid=paddock_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return {"status": "archived"}


@router.post(
    "/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/measurements",
)
def create_measurement(
    farm_uuid: UUID,
    paddock_uuid: UUID,
    request: Request,
    response: Response,
    payload: MeasurementCreateRequest,
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.create_measurement(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            paddock_uuid=paddock_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/measurements",
    response_model=MeasurementListResponse,
)
def list_measurements(
    farm_uuid: UUID,
    paddock_uuid: UUID,
    request: Request,
    response: Response,
    limit: int = 50,
    offset: int = 0,
    repository=Depends(get_pasture_live_repository),
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

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.list_measurements(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            paddock_uuid=paddock_uuid,
            limit=limit,
            offset=offset,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/measurements/{measurement_uuid}",
)
def get_measurement(
    farm_uuid: UUID,
    paddock_uuid: UUID,
    measurement_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.get_measurement(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            paddock_uuid=paddock_uuid,
            measurement_uuid=measurement_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.post(
    "/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/events",
)
def create_event(
    farm_uuid: UUID,
    paddock_uuid: UUID,
    request: Request,
    response: Response,
    payload: EventCreateRequest,
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.create_event(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            paddock_uuid=paddock_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/events",
    response_model=EventListResponse,
)
def list_events(
    farm_uuid: UUID,
    paddock_uuid: UUID,
    request: Request,
    response: Response,
    limit: int = 50,
    offset: int = 0,
    repository=Depends(get_pasture_live_repository),
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

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.list_events(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            paddock_uuid=paddock_uuid,
            limit=limit,
            offset=offset,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.post(
    "/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/start-grazing",
)
def start_grazing(
    farm_uuid: UUID,
    paddock_uuid: UUID,
    request: Request,
    response: Response,
    payload: StartGrazingRequest = StartGrazingRequest(),
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.start_grazing(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            paddock_uuid=paddock_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.post(
    "/{farm_uuid}/pasture-live/paddocks/{paddock_uuid}/finish-grazing",
)
def finish_grazing(
    farm_uuid: UUID,
    paddock_uuid: UUID,
    request: Request,
    response: Response,
    payload: FinishGrazingRequest = FinishGrazingRequest(),
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.finish_grazing(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            paddock_uuid=paddock_uuid,
            payload=payload.model_dump(),
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result


@router.get(
    "/{farm_uuid}/pasture-live/autonomy-sources",
)
def get_autonomy_sources(
    farm_uuid: UUID,
    request: Request,
    response: Response,
    repository=Depends(get_pasture_live_repository),
    auth_repository=Depends(get_auth_repository),
):
    _check_feature()
    request_id = _request_id(request)
    _cache_headers(response)

    service = PastureLiveService(repository, auth_repository)
    try:
        result = service.get_autonomy_sources(
            subject=_subject(request),
            farm_public_id=farm_uuid,
            request_id=request_id,
        )
    except (AuthorizationError, ForbiddenError, HiddenResourceError) as exc:
        _handle_auth_error(exc, request_id)

    return result
