"""Serviço de negócio da listagem de fazendas operacionais privadas da API v2."""
from uuid import UUID
import logging

from core.authorization import AuthorizationService, ForbiddenError, HiddenResourceError
from core.permissions import Permission, ORGANIZATION_WIDE_FARM_ROLES

logger = logging.getLogger("wins_agro.farms_v2")


class FarmsV2Service:
    def __init__(self, repository, auth_repository=None):
        self.repository = repository
        self.auth_repository = auth_repository or repository

    def list_authorized_farms(
        self,
        *,
        subject: str | None,
        organization_uuid: UUID | None,
        limit: int = 25,
        offset: int = 0,
        status_filter: str | None = "active",
        request_id: str,
        source: str = "web",
    ) -> dict:
        auth_service = AuthorizationService(self.auth_repository)

        # 1. Autenticar usuário
        user = auth_service.require_authenticated_user(subject)

        # 2. Resolução do contexto organizacional
        if organization_uuid is not None:
            # Usuário passou organização
            membership = self.auth_repository.find_membership(user.id, organization_uuid)
            if membership is None:
                # Não revelar se a organização existe (retornar 404)
                auth_service._deny("membership_missing", user_id=user.id, organization_id=str(organization_uuid))
                raise HiddenResourceError()

            # Se a membership existe mas está revoked/inactive, require_organization_membership levantará ForbiddenError
            context = auth_service.require_organization_membership(
                subject, organization_uuid, request_id=request_id, source=source
            )
        else:
            # Usuário não passou organização -> tentar auto-resolver
            active_memberships = self.repository.find_active_memberships(user.id)

            if len(active_memberships) == 0:
                auth_service._deny("membership_missing", user_id=user.id, organization_id=None)
                raise ForbiddenError("membership_missing")
            elif len(active_memberships) == 1:
                # Exatamente uma active membership
                resolved_org_uuid = active_memberships[0]["organization_public_id"]
                context = auth_service.require_organization_membership(
                    subject, resolved_org_uuid, request_id=request_id, source=source
                )
            else:
                # Múltiplas memberships e nenhuma especificada
                auth_service._deny("organization_context_required", user_id=user.id)
                raise ForbiddenError("organization_context_required")

        # 3. Validar a permissão FARM_READ no nível da organização
        auth_service.require_organization_role(context, Permission.FARM_READ)

        # 4. Obter detalhes da organização para a resposta
        org_name = self.repository.get_organization_name(context.organization_id)

        # 5. Listar fazendas autorizadas
        is_org_wide = context.role in ORGANIZATION_WIDE_FARM_ROLES

        # Usamos limit + 1 para paginação eficiente (determinar has_more)
        query_limit = limit + 1
        raw_items = self.repository.list_farms(
            organization_id=context.organization_id,
            membership_id=context.membership_id,
            is_org_wide=is_org_wide,
            limit=query_limit,
            offset=offset,
            status_filter=status_filter
        )

        has_more = len(raw_items) > limit
        items_to_return = raw_items[:limit]

        # 6. Gravar auditoria (farm.listed)
        self.repository.audit_farms_listed(context, len(items_to_return), limit, offset)

        # 7. Retornar estrutura de domínio
        return {
            "organization": {
                "id": context.organization_public_id,
                "name": org_name
            },
            "items": [
                {
                    "id": item["public_id"],
                    "name": item["name"],
                    "state": item["state"],
                    "municipality_code": item["municipality_code"],
                    "area_ha": item["area_ha"],
                    "status": item["status"],
                    "access_level": item["access_level"]
                }
                for item in items_to_return
            ],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "returned": len(items_to_return),
                "has_more": has_more
            }
        }
