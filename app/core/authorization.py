"""Autorização central, deny-by-default e independente do FastAPI/DB."""
from dataclasses import dataclass, replace
from datetime import datetime, timezone
import logging
from typing import Protocol
from uuid import UUID

from core.permissions import (
    ORGANIZATION_WIDE_FARM_ROLES,
    Permission,
    Role,
    farm_level_allows,
    role_allows,
)
from domain.foundation import (
    FarmAccessRecord,
    MembershipRecord,
    OperationalFarmRecord,
    RecordStatus,
    ResourceScope,
    UserRecord,
)

logger = logging.getLogger("wins_agro.foundation.authorization")


class AuthorizationRepository(Protocol):
    def find_user_by_subject(self, subject: str) -> UserRecord | None: ...
    def find_membership(self, user_id: int, organization_public_id: UUID) -> MembershipRecord | None: ...
    def find_farm(self, farm_public_id: UUID) -> OperationalFarmRecord | None: ...
    def find_farm_access(self, membership_id: int, farm_id: int) -> FarmAccessRecord | None: ...
    def find_resource_scope(self, resource_type: str, resource_public_id: UUID) -> ResourceScope | None: ...


class AuthorizationError(Exception):
    status_code = 403
    code = "authorization_denied"

    def __init__(self, message: str = "Acesso negado"):
        super().__init__(message)


class UnauthenticatedError(AuthorizationError):
    status_code = 401
    code = "unauthenticated"


class ForbiddenError(AuthorizationError):
    status_code = 403

    def __init__(self, code: str, message: str = "Acesso negado"):
        self.code = code
        super().__init__(message)


class HiddenResourceError(AuthorizationError):
    status_code = 404
    code = "resource_not_found"


@dataclass(frozen=True)
class AuthorizationContext:
    user_id: int
    user_public_id: UUID
    organization_id: int
    organization_public_id: UUID
    membership_id: int
    membership_public_id: UUID
    role: Role
    request_id: str
    source: str
    authenticated_at: datetime
    farm_id: int | None = None
    farm_public_id: UUID | None = None


class AuthorizationService:
    """Resolve identidade e aplica policies usando apenas dados consultados no servidor."""

    def __init__(self, repository: AuthorizationRepository, now=None):
        self.repository = repository
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._cache: dict[tuple, object | None] = {}

    def _cached(self, key: tuple, loader):
        if key not in self._cache:
            self._cache[key] = loader()
        return self._cache[key]

    def require_authenticated_user(self, subject: str | None) -> UserRecord:
        if not subject:
            self._deny("unauthenticated")
            raise UnauthenticatedError("Autenticação necessária")
        user = self._cached(("user", subject), lambda: self.repository.find_user_by_subject(subject))
        if user is None or user.status is not RecordStatus.ACTIVE:
            self._deny("unauthenticated")
            raise UnauthenticatedError("Autenticação necessária")
        return user

    def require_organization_membership(
        self,
        subject: str | None,
        organization_public_id: UUID,
        request_id: str,
        source: str = "web",
    ) -> AuthorizationContext:
        user = self.require_authenticated_user(subject)
        membership = self._cached(
            ("membership", user.id, organization_public_id),
            lambda: self.repository.find_membership(user.id, organization_public_id),
        )
        if membership is None:
            self._deny("membership_missing", user_id=user.id, organization_id=str(organization_public_id))
            raise ForbiddenError("membership_missing")
        if membership.status is RecordStatus.REVOKED:
            self._deny("membership_revoked", user_id=user.id, organization_id=membership.organization_id)
            raise ForbiddenError("membership_revoked")
        if not membership.is_active(self._now()):
            self._deny("membership_inactive", user_id=user.id, organization_id=membership.organization_id)
            raise ForbiddenError("membership_inactive")
        return AuthorizationContext(
            user_id=user.id,
            user_public_id=user.public_id,
            organization_id=membership.organization_id,
            organization_public_id=membership.organization_public_id,
            membership_id=membership.id,
            membership_public_id=membership.public_id,
            role=membership.role,
            request_id=request_id,
            source=source,
            authenticated_at=self._now(),
        )

    def require_organization_role(
        self, context: AuthorizationContext, permission: Permission
    ) -> AuthorizationContext:
        if not role_allows(context.role, permission):
            self._deny(
                "role_denied",
                user_id=context.user_id,
                organization_id=context.organization_id,
                action=permission.value,
            )
            raise ForbiddenError("role_denied")
        return context

    def require_farm_access(
        self,
        context: AuthorizationContext,
        farm_public_id: UUID,
        permission: Permission = Permission.FARM_READ,
    ) -> AuthorizationContext:
        farm = self._cached(("farm", farm_public_id), lambda: self.repository.find_farm(farm_public_id))
        if farm is None or farm.status is not RecordStatus.ACTIVE:
            self._deny("resource_not_found", user_id=context.user_id, farm_id=str(farm_public_id))
            raise HiddenResourceError()
        if farm.organization_id != context.organization_id:
            self._deny(
                "cross_organization_access",
                user_id=context.user_id,
                organization_id=context.organization_id,
                farm_id=farm.id,
            )
            raise HiddenResourceError()
        self.require_organization_role(context, permission)
        if context.role not in ORGANIZATION_WIDE_FARM_ROLES:
            access = self._cached(
                ("farm_access", context.membership_id, farm.id),
                lambda: self.repository.find_farm_access(context.membership_id, farm.id),
            )
            if access is None or not access.is_active(self._now()):
                self._deny(
                    "farm_not_assigned",
                    user_id=context.user_id,
                    organization_id=context.organization_id,
                    farm_id=farm.id,
                )
                raise ForbiddenError("farm_not_assigned")
            if not farm_level_allows(access.access_level, permission):
                self._deny("farm_access_level_denied", user_id=context.user_id, farm_id=farm.id)
                raise ForbiddenError("farm_access_level_denied")
        return replace(context, farm_id=farm.id, farm_public_id=farm.public_id)

    def require_resource_access(
        self,
        context: AuthorizationContext,
        resource_type: str,
        resource_public_id: UUID,
        permission: Permission = Permission.FARM_READ,
    ) -> AuthorizationContext:
        scope = self._cached(
            ("resource", resource_type, resource_public_id),
            lambda: self.repository.find_resource_scope(resource_type, resource_public_id),
        )
        if scope is None or scope.organization_id != context.organization_id:
            self._deny("resource_not_found", user_id=context.user_id, action=resource_type)
            raise HiddenResourceError()
        return self.require_farm_access(context, scope.farm_public_id, permission)

    @staticmethod
    def _deny(code: str, **fields) -> None:
        safe = {key: value for key, value in fields.items() if value is not None}
        logger.warning("authorization_denied code=%s fields=%s", code, safe)
