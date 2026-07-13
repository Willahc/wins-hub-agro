"""Papéis e permissões centralizados da fundação multiusuário.

As policies negam por padrão. Código de domínio deve pedir uma ``Permission``;
nunca comparar strings de papel espalhadas por routers ou templates.
"""
from enum import Enum
from types import MappingProxyType


class Role(str, Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    TECHNICIAN = "technician"
    OPERATOR = "operator"
    VIEWER = "viewer"


class Permission(str, Enum):
    ORGANIZATION_READ = "organization.read"
    ORGANIZATION_MANAGE = "organization.manage"
    MEMBERSHIP_MANAGE = "membership.manage"
    OWNERSHIP_TRANSFER = "ownership.transfer"
    FARM_READ = "farm.read"
    FARM_MANAGE = "farm.manage"
    FARM_OPERATE = "farm.operate"
    TECHNICAL_RECORD = "technical.record"
    PARAMETER_MANAGE = "parameter.manage"
    FORMULA_MANAGE = "formula.manage"
    EXPORT = "export"


class FarmAccessLevel(str, Enum):
    READ = "read"
    OPERATE = "operate"
    MANAGE = "manage"


_ROLE_PERMISSIONS = MappingProxyType({
    Role.OWNER: frozenset(Permission),
    Role.ADMIN: frozenset({
        Permission.ORGANIZATION_READ,
        Permission.ORGANIZATION_MANAGE,
        Permission.MEMBERSHIP_MANAGE,
        Permission.FARM_READ,
        Permission.FARM_MANAGE,
        Permission.FARM_OPERATE,
        Permission.TECHNICAL_RECORD,
        Permission.PARAMETER_MANAGE,
        Permission.FORMULA_MANAGE,
        Permission.EXPORT,
    }),
    Role.MANAGER: frozenset({
        Permission.ORGANIZATION_READ,
        Permission.FARM_READ,
        Permission.FARM_MANAGE,
        Permission.FARM_OPERATE,
        Permission.TECHNICAL_RECORD,
        Permission.PARAMETER_MANAGE,
        Permission.EXPORT,
    }),
    Role.TECHNICIAN: frozenset({
        Permission.ORGANIZATION_READ,
        Permission.FARM_READ,
        Permission.TECHNICAL_RECORD,
        Permission.EXPORT,
    }),
    Role.OPERATOR: frozenset({
        Permission.ORGANIZATION_READ,
        Permission.FARM_READ,
        Permission.FARM_OPERATE,
    }),
    Role.VIEWER: frozenset({
        Permission.ORGANIZATION_READ,
        Permission.FARM_READ,
    }),
})

_FARM_LEVEL_PERMISSIONS = MappingProxyType({
    FarmAccessLevel.READ: frozenset({Permission.FARM_READ}),
    FarmAccessLevel.OPERATE: frozenset({
        Permission.FARM_READ,
        Permission.FARM_OPERATE,
        Permission.TECHNICAL_RECORD,
    }),
    FarmAccessLevel.MANAGE: frozenset({
        Permission.FARM_READ,
        Permission.FARM_MANAGE,
        Permission.FARM_OPERATE,
        Permission.TECHNICAL_RECORD,
        Permission.PARAMETER_MANAGE,
        Permission.EXPORT,
    }),
})

ORGANIZATION_WIDE_FARM_ROLES = frozenset({Role.OWNER, Role.ADMIN})


def role_permissions(role: Role) -> frozenset[Permission]:
    """Retorna permissões do papel; papel desconhecido falha ao construir ``Role``."""
    return _ROLE_PERMISSIONS.get(role, frozenset())


def farm_level_permissions(level: FarmAccessLevel) -> frozenset[Permission]:
    return _FARM_LEVEL_PERMISSIONS.get(level, frozenset())


def role_allows(role: Role, permission: Permission) -> bool:
    return permission in role_permissions(role)


def farm_level_allows(level: FarmAccessLevel, permission: Permission) -> bool:
    return permission in farm_level_permissions(level)
