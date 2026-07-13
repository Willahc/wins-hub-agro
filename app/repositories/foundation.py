"""Persistência PostgreSQL da Fase 0; importar este módulo não abre conexão."""
from uuid import UUID

from core.permissions import FarmAccessLevel
from db import _cur, _tx, query
from domain.audit import AuditEvent, AuditService
from domain.foundation import (
    FarmAccessRecord,
    MembershipRecord,
    OperationalFarmRecord,
    RecordStatus,
    ResourceScope,
    UserRecord,
)
from core.permissions import Role


class PostgresFoundationRepository:
    def find_user_by_subject(self, subject: str):
        rows = query(
            "SELECT id, public_id, auth_subject, status FROM foundation.app_users WHERE auth_subject=%(subject)s",
            {"subject": subject},
        )
        if not rows:
            return None
        row = rows[0]
        return UserRecord(row["id"], UUID(str(row["public_id"])), row["auth_subject"], RecordStatus(row["status"]))

    def find_membership(self, user_id: int, organization_public_id: UUID):
        rows = query(
            """
            SELECT m.id, m.public_id, m.organization_id, o.public_id organization_public_id,
                   m.user_id, m.role, m.status, m.expires_at
              FROM foundation.organization_memberships m
              JOIN foundation.organizations o ON o.id=m.organization_id
             WHERE m.user_id=%(user_id)s AND o.public_id=%(organization_id)s
             ORDER BY m.id DESC LIMIT 1
            """,
            {"user_id": user_id, "organization_id": str(organization_public_id)},
        )
        if not rows:
            return None
        row = rows[0]
        return MembershipRecord(
            row["id"], UUID(str(row["public_id"])), row["organization_id"],
            UUID(str(row["organization_public_id"])), row["user_id"], Role(row["role"]),
            RecordStatus(row["status"]), row["expires_at"],
        )

    def find_farm(self, farm_public_id: UUID):
        rows = query(
            """
            SELECT f.id, f.public_id, f.organization_id, o.public_id organization_public_id,
                   f.name, f.status
              FROM foundation.operational_farms f
              JOIN foundation.organizations o ON o.id=f.organization_id
             WHERE f.public_id=%(farm_id)s
            """,
            {"farm_id": str(farm_public_id)},
        )
        if not rows:
            return None
        row = rows[0]
        return OperationalFarmRecord(
            row["id"], UUID(str(row["public_id"])), row["organization_id"],
            UUID(str(row["organization_public_id"])), row["name"], RecordStatus(row["status"]),
        )

    def find_farm_access(self, membership_id: int, farm_id: int):
        rows = query(
            """
            SELECT id, public_id, farm_id, membership_id, access_level, status, expires_at
              FROM foundation.farm_access
             WHERE membership_id=%(membership_id)s AND farm_id=%(farm_id)s
             ORDER BY id DESC LIMIT 1
            """,
            {"membership_id": membership_id, "farm_id": farm_id},
        )
        if not rows:
            return None
        row = rows[0]
        return FarmAccessRecord(
            row["id"], UUID(str(row["public_id"])), row["farm_id"], row["membership_id"],
            FarmAccessLevel(row["access_level"]), RecordStatus(row["status"]), row["expires_at"],
        )

    def find_resource_scope(self, resource_type: str, resource_public_id: UUID):
        # Allowlist explícita: nunca interpolar tabela enviada pelo navegador.
        if resource_type != "operational_farm":
            return None
        farm = self.find_farm(resource_public_id)
        if farm is None:
            return None
        return ResourceScope(
            resource_type, resource_public_id, farm.organization_id,
            farm.organization_public_id, farm.id, farm.public_id,
        )

    def audit_farm_read(self, context, farm: OperationalFarmRecord) -> None:
        # O insert compartilha commit/rollback; falha de auditoria não libera a operação.
        with _tx() as connection:
            cursor = _cur(connection)
            AuditService().record(cursor, AuditEvent(
                request_id=context.request_id,
                actor_user_id=context.user_id,
                actor_membership_id=context.membership_id,
                organization_id=context.organization_id,
                farm_id=farm.id,
                action="farm.read",
                entity_type="operational_farm",
                entity_public_id=farm.public_id,
                result="success",
                source=context.source,
                metadata={"permission": "farm.read", "resource_type": "operational_farm"},
            ))
