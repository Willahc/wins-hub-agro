"""Modelos imutáveis usados pela autorização e pelos repositories."""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from core.permissions import FarmAccessLevel, Role


class RecordStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    REVOKED = "revoked"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class UserRecord:
    id: int
    public_id: UUID
    subject: str
    status: RecordStatus = RecordStatus.ACTIVE


@dataclass(frozen=True)
class OrganizationRecord:
    id: int
    public_id: UUID
    name: str
    slug: str
    status: RecordStatus = RecordStatus.ACTIVE


@dataclass(frozen=True)
class MembershipRecord:
    id: int
    public_id: UUID
    organization_id: int
    organization_public_id: UUID
    user_id: int
    role: Role
    status: RecordStatus = RecordStatus.ACTIVE
    expires_at: datetime | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return self.status is RecordStatus.ACTIVE and (
            self.expires_at is None or self.expires_at > now
        )


@dataclass(frozen=True)
class OperationalFarmRecord:
    id: int
    public_id: UUID
    organization_id: int
    organization_public_id: UUID
    name: str
    status: RecordStatus = RecordStatus.ACTIVE


@dataclass(frozen=True)
class FarmAccessRecord:
    id: int
    public_id: UUID
    farm_id: int
    membership_id: int
    access_level: FarmAccessLevel
    status: RecordStatus = RecordStatus.ACTIVE
    expires_at: datetime | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        return self.status is RecordStatus.ACTIVE and (
            self.expires_at is None or self.expires_at > now
        )


@dataclass(frozen=True)
class ResourceScope:
    """Escopo retornado por lookup server-side de um recurso privado."""

    resource_type: str
    resource_public_id: UUID
    organization_id: int
    organization_public_id: UUID
    farm_id: int
    farm_public_id: UUID
