"""Configuração explícita para futuro bootstrap legado; desativada por padrão."""
from dataclasses import dataclass
import os
from uuid import UUID


@dataclass(frozen=True)
class LegacyCompatibilitySettings:
    enabled: bool
    organization_public_id: UUID | None

    @classmethod
    def from_environment(cls):
        enabled = os.getenv("ENABLE_LEGACY_ORGANIZATION_COMPATIBILITY", "").lower() in {"1", "true", "yes"}
        raw_id = os.getenv("LEGACY_ORGANIZATION_PUBLIC_ID", "").strip()
        if enabled and not raw_id:
            raise RuntimeError("Compatibilidade legada exige LEGACY_ORGANIZATION_PUBLIC_ID")
        return cls(enabled=enabled, organization_public_id=UUID(raw_id) if raw_id else None)
