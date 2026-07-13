"""Repositório de dados otimizado para a listagem de fazendas operacionais privadas da API v2."""
from uuid import UUID
from db import query, _tx, _cur
from domain.audit import AuditEvent, AuditService


class FarmsV2Repository:
    def find_active_memberships(self, user_id: int) -> list[dict]:
        """Busca todas as memberships ativas do usuário, incluindo o nome e slug da organização."""
        return query(
            """
            SELECT m.id, m.public_id, m.organization_id, o.public_id as organization_public_id,
                   o.name as organization_name, o.slug as organization_slug, m.role
              FROM foundation.organization_memberships m
              JOIN foundation.organizations o ON o.id = m.organization_id
             WHERE m.user_id = %(user_id)s
               AND m.status = 'active'
               AND (m.expires_at IS NULL OR m.expires_at > now())
            """,
            {"user_id": user_id},
        )

    def get_organization_name(self, org_id: int) -> str:
        """Obtém o nome da organização pelo seu ID sequencial interno."""
        rows = query(
            "SELECT name FROM foundation.organizations WHERE id = %(org_id)s",
            {"org_id": org_id}
        )
        return rows[0]["name"] if rows else ""

    def list_farms(
        self,
        organization_id: int,
        membership_id: int,
        is_org_wide: bool,
        limit: int,
        offset: int,
        status_filter: str | None,
    ) -> list[dict]:
        """Lista fazendas operacionais autorizadas de forma paginada (limit + 1)."""
        # A ordenação é fixa e determinística por nome e UUID público.
        return query(
            """
            SELECT DISTINCT f.id, f.public_id, f.name, f.state, f.municipality_code, f.area_ha::text as area_ha, f.status,
                   CASE
                     WHEN %(is_org_wide)s THEN 'manage'
                     ELSE a.access_level
                   END as access_level
              FROM foundation.operational_farms f
              LEFT JOIN foundation.farm_access a ON a.farm_id = f.id
                                                AND a.membership_id = %(membership_id)s
                                                AND a.status = 'active'
                                                AND (a.expires_at IS NULL OR a.expires_at > now())
             WHERE f.organization_id = %(organization_id)s
               AND (%(status_filter)s IS NULL OR f.status = %(status_filter)s)
               AND (%(is_org_wide)s OR a.id IS NOT NULL)
             ORDER BY f.name ASC, f.public_id ASC
             LIMIT %(limit)s OFFSET %(offset)s
            """,
            {
                "organization_id": organization_id,
                "membership_id": membership_id,
                "is_org_wide": is_org_wide,
                "status_filter": status_filter,
                "limit": limit,
                "offset": offset,
            },
        )

    def audit_farms_listed(self, context, returned_count: int, limit: int, offset: int) -> None:
        """Registra a auditoria transacional para a ação farm.listed."""
        with _tx() as connection:
            cursor = _cur(connection)
            AuditService().record(cursor, AuditEvent(
                request_id=context.request_id,
                actor_user_id=context.user_id,
                actor_membership_id=context.membership_id,
                organization_id=context.organization_id,
                farm_id=None,
                action="farm.listed",
                entity_type="operational_farm",
                entity_public_id=None,
                result="success",
                source=context.source,
                metadata={
                    "returned_count": returned_count,
                    "limit": limit,
                    "offset": offset,
                    "role": context.role.value
                },
            ))
