"""Vertical slice privada da Fase 0, habilitável sem alterar rotas legadas."""
import re
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request

from auth import decode_token
from core.authorization import AuthorizationError
from repositories.foundation import PostgresFoundationRepository
from schemas.foundation import OperationalFarmResponse
from services.foundation import resolve_operational_farm


router = APIRouter(prefix="/api/v1/foundation", tags=["foundation"])
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def get_foundation_repository():
    return PostgresFoundationRepository()


def _request_id(request: Request) -> str:
    candidate = request.headers.get("x-request-id", "")
    return candidate if _REQUEST_ID.fullmatch(candidate) else str(uuid4())


def _subject(request: Request) -> str | None:
    token = request.cookies.get("access_token")
    payload = decode_token(token) if token else None
    return payload.get("sub") if payload else None


@router.get(
    "/organizations/{organization_public_id}/farms/{farm_public_id}",
    response_model=OperationalFarmResponse,
)
def get_operational_farm(
    organization_public_id: UUID,
    farm_public_id: UUID,
    request: Request,
    repository=Depends(get_foundation_repository),
):
    request_id = _request_id(request)
    try:
        _context, farm = resolve_operational_farm(
            repository,
            subject=_subject(request),
            organization_public_id=organization_public_id,
            farm_public_id=farm_public_id,
            request_id=request_id,
        )
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc), "request_id": request_id},
        ) from exc
    return OperationalFarmResponse(
        public_id=str(farm.public_id),
        organization_public_id=str(farm.organization_public_id),
        name=farm.name,
        status=farm.status.value,
        request_id=request_id,
    )
