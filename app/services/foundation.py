"""Caso de uso da vertical slice sem dependência de FastAPI ou banco concreto."""
from uuid import UUID

from core.authorization import AuthorizationService, HiddenResourceError
from core.permissions import Permission


def resolve_operational_farm(
    repository,
    *,
    subject: str | None,
    organization_public_id: UUID,
    farm_public_id: UUID,
    request_id: str,
):
    service = AuthorizationService(repository)
    context = service.require_organization_membership(
        subject, organization_public_id, request_id=request_id
    )
    context = service.require_farm_access(context, farm_public_id, Permission.FARM_READ)
    farm = repository.find_farm(farm_public_id)
    if farm is None:  # proteção contra alteração concorrente entre checks
        raise HiddenResourceError()
    repository.audit_farm_read(context, farm)
    return context, farm
