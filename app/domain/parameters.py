"""Parâmetros técnicos versionados, sem valores agronômicos implícitos."""
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID

from core.units import get_unit


class ParameterScope(str, Enum):
    GLOBAL = "global"
    REGIONAL = "regional"
    ORGANIZATION = "organization"
    FARM = "farm"


class VersionStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


@dataclass(frozen=True)
class TechnicalParameterVersion:
    public_id: UUID
    code: str
    name: str
    description: str
    value: Decimal
    unit_code: str
    value_type: str
    origin: str
    source_reference: str | None
    scope: ParameterScope
    version: int
    status: VersionStatus
    valid_from: datetime
    valid_to: datetime | None = None
    organization_id: int | None = None
    farm_id: int | None = None
    region_code: str | None = None
    animal_category: str | None = None
    justification: str | None = None
    confidence: Decimal | None = None

    def __post_init__(self):
        get_unit(self.unit_code)
        if self.version < 1:
            raise ValueError("Versão deve ser positiva")
        if self.scope is ParameterScope.FARM and self.farm_id is None:
            raise ValueError("Parâmetro de fazenda exige farm_id")
        if self.scope is ParameterScope.ORGANIZATION and self.organization_id is None:
            raise ValueError("Parâmetro de organização exige organization_id")

    def applies_at(self, moment: datetime) -> bool:
        return self.status is VersionStatus.PUBLISHED and self.valid_from <= moment and (
            self.valid_to is None or moment < self.valid_to
        )


class ParameterResolver:
    """Resolve fazenda > organização > região > global; ausência continua ausência."""

    def resolve(self, candidates, *, organization_id=None, farm_id=None, region_code=None, at=None):
        at = at or datetime.now(timezone.utc)
        applicable = [item for item in candidates if item.applies_at(at)]
        ranks = {
            ParameterScope.FARM: 4,
            ParameterScope.ORGANIZATION: 3,
            ParameterScope.REGIONAL: 2,
            ParameterScope.GLOBAL: 1,
        }

        def matches(item):
            if item.scope is ParameterScope.FARM:
                return item.farm_id == farm_id and item.organization_id in (None, organization_id)
            if item.scope is ParameterScope.ORGANIZATION:
                return item.organization_id == organization_id
            if item.scope is ParameterScope.REGIONAL:
                return item.region_code == region_code
            return item.scope is ParameterScope.GLOBAL

        matched = [item for item in applicable if matches(item)]
        return max(matched, key=lambda item: (ranks[item.scope], item.version), default=None)
