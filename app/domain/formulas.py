"""Registro seguro e versionado de fórmulas explícitas; nunca interpreta código."""
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal
from enum import Enum
import hashlib
from types import MappingProxyType
from typing import Callable, Mapping
from uuid import UUID

from core.units import get_unit


class FormulaStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    RETIRED = "retired"


@dataclass(frozen=True)
class FormulaDefinition:
    public_id: UUID
    code: str
    name: str
    domain: str
    description: str


@dataclass(frozen=True)
class FormulaVersion:
    public_id: UUID
    formula_code: str
    version: int
    implementation_id: str
    input_units: Mapping[str, str]
    output_unit: str
    parameter_codes: tuple[str, ...]
    assumptions: str
    source_reference: str | None
    valid_from: datetime
    status: FormulaStatus
    created_by: int
    technical_review: str | None = None
    confidence: Decimal | None = None
    checksum: str = ""

    def __post_init__(self):
        if self.version < 1:
            raise ValueError("Versão deve ser positiva")
        for unit_code in self.input_units.values():
            get_unit(unit_code)
        get_unit(self.output_unit)
        expected = self.compute_checksum()
        if self.checksum and self.checksum != expected:
            raise ValueError("Checksum da fórmula não corresponde ao conteúdo")
        if not self.checksum:
            object.__setattr__(self, "checksum", expected)

    def compute_checksum(self) -> str:
        raw = "|".join((
            self.formula_code,
            str(self.version),
            self.implementation_id,
            repr(sorted(self.input_units.items())),
            self.output_unit,
            repr(self.parameter_codes),
            self.assumptions,
        ))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class FormulaRegistry:
    def __init__(self, implementations: Mapping[str, Callable] | None = None):
        self._implementations = MappingProxyType(dict(implementations or {}))

    def execute(self, version: FormulaVersion, inputs: Mapping[str, Decimal], parameters=None):
        try:
            implementation = self._implementations[version.implementation_id]
        except KeyError as exc:
            raise KeyError("Implementação de fórmula não registrada") from exc
        decimal_inputs = {key: value if isinstance(value, Decimal) else Decimal(str(value)) for key, value in inputs.items()}
        return implementation(decimal_inputs, parameters or {})


def publish_new_version(previous: FormulaVersion, draft: FormulaVersion) -> FormulaVersion:
    if previous.status is not FormulaStatus.PUBLISHED:
        raise ValueError("Versão anterior precisa estar publicada")
    if draft.formula_code != previous.formula_code or draft.version != previous.version + 1:
        raise ValueError("Nova versão deve ser sequencial e da mesma fórmula")
    if draft.status is not FormulaStatus.DRAFT:
        raise ValueError("Somente rascunho pode ser publicado")
    return replace(draft, status=FormulaStatus.PUBLISHED, checksum="")
