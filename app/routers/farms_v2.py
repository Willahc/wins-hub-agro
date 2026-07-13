"""Router da listagem de fazendas operacionais privadas da API v2."""
import re
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from auth import decode_token
from core.authorization import AuthorizationError
from repositories.foundation import PostgresFoundationRepository
from repositories.farms_v2 import FarmsV2Repository
from services.farms_v2 import FarmsV2Service
from schemas.farms_v2 import FarmV2ListResponse

router = APIRouter(prefix="/api/v2/farms", tags=["farms_v2"])
_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]{1,100}$")


def get_farms_repository():
    return FarmsV2Repository()


def get_auth_repository():
    return PostgresFoundationRepository()


def _request_id(request: Request) -> str:
    candidate = request.headers.get("x-request-id", "")
    return candidate if _REQUEST_ID.fullmatch(candidate) else str(uuid4())


def _subject(request: Request) -> str | None:
    token = request.cookies.get("access_token")
    payload = decode_token(token) if token else None
    return payload.get("sub") if payload else None


@router.get(
    "",
    response_model=FarmV2ListResponse,
)
def list_farms(
    request: Request,
    response: Response,
    organization_uuid: UUID | None = None,
    limit: int = 25,
    offset: int = 0,
    status: str | None = "active",
    repository=Depends(get_farms_repository),
    auth_repository=Depends(get_auth_repository),
):
    request_id = _request_id(request)

    # 1. Validação explícita de paginação e status
    if limit < 1 or limit > 100 or offset < 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_pagination", "message": "Parâmetros de paginação inválidos", "request_id": request_id}
        )

    if status is not None and status not in {"active", "inactive", "archived"}:
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_status", "message": "Parâmetros de status inválidos", "request_id": request_id}
        )

    # 2. Definição obrigatória dos headers de cache exigidos na resposta autenticada
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"

    # 3. Execução do caso de uso
    service = FarmsV2Service(repository, auth_repository)
    try:
        data = service.list_authorized_farms(
            subject=_subject(request),
            organization_uuid=organization_uuid,
            limit=limit,
            offset=offset,
            status_filter=status,
            request_id=request_id,
            source="web"
        )
    except AuthorizationError as exc:
        status_code = exc.status_code
        code = getattr(exc, "code", "authorization_denied")
        # Ajusta status_code conforme códigos estáveis da Fase 0D
        if code == "organization_context_required":
            status_code = 409
        elif code == "membership_missing" and organization_uuid is None:
            status_code = 403

        raise HTTPException(
            status_code=status_code,
            detail={"code": code, "message": str(exc), "request_id": request_id},
        ) from exc

    return data
