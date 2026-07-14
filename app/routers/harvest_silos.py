"""API privada de Colheita e Silos."""
import os
import re
from datetime import date
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from auth import decode_token
from core.authorization import AuthorizationError, ForbiddenError, HiddenResourceError
from repositories.foundation import PostgresFoundationRepository
from repositories.harvest_silos import HarvestSilosRepository
from schemas.harvest_silos import (
    CompleteRequest, DashboardResponse, PlanCreateRequest, PlanListResponse,
    PlanResponse, PlanUpdateRequest, SimulationResponse, StartRequest,
)
from services.harvest_silos import ConflictError, HarvestSilosService, ValidationError

router = APIRouter(prefix="/api/v2/farms", tags=["harvest_silos"])
ENABLE_HARVEST_SILOS = os.getenv("ENABLE_HARVEST_SILOS", "false").lower() in {"1", "true", "yes"}
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def get_harvest_repository(): return HarvestSilosRepository()
def get_auth_repository(): return PostgresFoundationRepository()
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
    if not ENABLE_HARVEST_SILOS:
        raise HTTPException(404, detail={"code": "feature_disabled", "message": "Colheita e Silos não está habilitado."})
def _error(exc, request_id):
    if isinstance(exc, ConflictError): status, code = 409, exc.code
    elif isinstance(exc, ValidationError): status, code = 422, exc.code
    else: status, code = exc.status_code, getattr(exc, "code", "authorization_denied")
    raise HTTPException(status, detail={"code": code, "message": str(exc), "request_id": request_id}) from exc
def _service(repository, auth_repository): return HarvestSilosService(repository, auth_repository)


@router.get("/{farm_uuid}/harvest-silos/dashboard", response_model=DashboardResponse)
def dashboard(farm_uuid: UUID, request: Request, response: Response, repository=Depends(get_harvest_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try: return _service(repository, auth_repository).get_dashboard(subject=_subject(request), farm_public_id=farm_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError, ConflictError, ValidationError) as exc: _error(exc, rid)


@router.post("/{farm_uuid}/harvest-silos/simulate", response_model=SimulationResponse)
def simulate(farm_uuid: UUID, payload: PlanCreateRequest, request: Request, response: Response, repository=Depends(get_harvest_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try: return _service(repository, auth_repository).simulate(subject=_subject(request), farm_public_id=farm_uuid, payload=payload.model_dump(), request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError, ConflictError, ValidationError) as exc: _error(exc, rid)


@router.post("/{farm_uuid}/harvest-silos/plans", response_model=PlanResponse, status_code=201)
def create_plan(farm_uuid: UUID, payload: PlanCreateRequest, request: Request, response: Response, repository=Depends(get_harvest_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try: return _service(repository, auth_repository).create_plan(subject=_subject(request), farm_public_id=farm_uuid, payload=payload.model_dump(), request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError, ConflictError, ValidationError) as exc: _error(exc, rid)


@router.get("/{farm_uuid}/harvest-silos/plans", response_model=PlanListResponse)
def list_plans(farm_uuid: UUID, request: Request, response: Response, limit: int=25, offset: int=0, status: str|None=None, crop: str|None=None, start_date: date|None=None, end_date: date|None=None, search: str|None=None, repository=Depends(get_harvest_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    if limit < 1 or limit > 100 or offset < 0: raise HTTPException(422, detail={"code":"invalid_pagination"})
    try: return _service(repository, auth_repository).list_plans(subject=_subject(request), farm_public_id=farm_uuid, request_id=rid, limit=limit, offset=offset, status=status, crop=crop, start_date=start_date, end_date=end_date, search=search)
    except (AuthorizationError, ForbiddenError, HiddenResourceError, ConflictError, ValidationError) as exc: _error(exc, rid)


@router.get("/{farm_uuid}/harvest-silos/plans/{plan_uuid}", response_model=PlanResponse)
def get_plan(farm_uuid: UUID, plan_uuid: UUID, request: Request, response: Response, repository=Depends(get_harvest_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try: return _service(repository, auth_repository).get_plan(subject=_subject(request), farm_public_id=farm_uuid, plan_public_id=plan_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError, ConflictError, ValidationError) as exc: _error(exc, rid)


@router.put("/{farm_uuid}/harvest-silos/plans/{plan_uuid}", response_model=PlanResponse)
def update_plan(farm_uuid: UUID, plan_uuid: UUID, payload: PlanUpdateRequest, request: Request, response: Response, repository=Depends(get_harvest_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try: return _service(repository, auth_repository).update_plan(subject=_subject(request), farm_public_id=farm_uuid, plan_public_id=plan_uuid, payload=payload.model_dump(), request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError, ConflictError, ValidationError) as exc: _error(exc, rid)


@router.delete("/{farm_uuid}/harvest-silos/plans/{plan_uuid}", status_code=204)
def archive_plan(farm_uuid: UUID, plan_uuid: UUID, request: Request, response: Response, repository=Depends(get_harvest_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try: _service(repository, auth_repository).archive_plan(subject=_subject(request), farm_public_id=farm_uuid, plan_public_id=plan_uuid, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError, ConflictError, ValidationError) as exc: _error(exc, rid)


@router.post("/{farm_uuid}/harvest-silos/plans/{plan_uuid}/start", response_model=PlanResponse)
def start_plan(farm_uuid: UUID, plan_uuid: UUID, payload: StartRequest, request: Request, response: Response, repository=Depends(get_harvest_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try: return _service(repository, auth_repository).start_plan(subject=_subject(request), farm_public_id=farm_uuid, plan_public_id=plan_uuid, actual_start_date=payload.actual_start_date, request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError, ConflictError, ValidationError) as exc: _error(exc, rid)


@router.post("/{farm_uuid}/harvest-silos/plans/{plan_uuid}/complete", response_model=PlanResponse)
def complete_plan(farm_uuid: UUID, plan_uuid: UUID, payload: CompleteRequest, request: Request, response: Response, repository=Depends(get_harvest_repository), auth_repository=Depends(get_auth_repository)):
    _check_feature(); rid = _request_id(request); _headers(response)
    try: return _service(repository, auth_repository).complete_plan(subject=_subject(request), farm_public_id=farm_uuid, plan_public_id=plan_uuid, payload=payload.model_dump(), request_id=rid)
    except (AuthorizationError, ForbiddenError, HiddenResourceError, ConflictError, ValidationError) as exc: _error(exc, rid)
