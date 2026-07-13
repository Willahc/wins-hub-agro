"""Validação e execução segura do mapping legado explícito."""
from dataclasses import dataclass
from datetime import datetime
from typing import Mapping, Protocol
from uuid import UUID


ALLOWED_SOURCE = ("fazenda", "cliente")
ALLOWED_ROLES = frozenset({"owner", "admin", "manager", "technician", "operator", "viewer"})
ALLOWED_ACCESS_LEVELS = frozenset({"read", "operate", "manage"})


class BootstrapInputError(ValueError):
    pass


class BootstrapExecutor(Protocol):
    def process(self, payload: Mapping[str, object], apply: bool) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class LegacyMapping:
    payload: Mapping[str, object]

    @classmethod
    def parse(cls, raw: Mapping[str, object]):
        if not isinstance(raw, dict):
            raise BootstrapInputError("Mapping deve ser um objeto")
        required = {
            "user_public_id", "auth_subject", "display_name", "organization_public_id",
            "organization_name", "organization_slug", "membership_public_id", "role",
            "farm_public_id", "farm_name", "access_public_id", "access_level",
            "link_public_id", "idempotency_key", "source_schema", "source_table",
            "legacy_client_id", "mapping_version", "origin", "justification",
            "approved_by_user_public_id", "approved_at",
        }
        unknown = set(raw) - required - {"audit_public_ids"}
        if unknown:
            raise BootstrapInputError("Campos não autorizados no mapping")
        missing = sorted(key for key in required if raw.get(key) in (None, ""))
        if missing:
            raise BootstrapInputError("Campos obrigatórios ausentes")
        if (raw["source_schema"], raw["source_table"]) != ALLOWED_SOURCE:
            raise BootstrapInputError("Origem legada não autorizada")
        if raw["role"] not in ALLOWED_ROLES:
            raise BootstrapInputError("Papel inválido")
        if raw["access_level"] not in ALLOWED_ACCESS_LEVELS:
            raise BootstrapInputError("Nível de acesso inválido")
        if raw["origin"] not in {"explicit_review", "explicit_synthetic_review"}:
            raise BootstrapInputError("Origem do mapping inválida")
        for key in (
            "user_public_id", "organization_public_id", "membership_public_id", "farm_public_id",
            "access_public_id", "link_public_id", "idempotency_key", "approved_by_user_public_id",
        ):
            try:
                UUID(str(raw[key]))
            except (ValueError, TypeError, AttributeError) as exc:
                raise BootstrapInputError("UUID inválido") from exc
        try:
            legacy_id = int(raw["legacy_client_id"])
            version = int(raw["mapping_version"])
        except (ValueError, TypeError) as exc:
            raise BootstrapInputError("Identificador ou versão inválidos") from exc
        if legacy_id <= 0 or version <= 0:
            raise BootstrapInputError("Identificador e versão devem ser positivos")
        if len(str(raw["justification"]).strip()) < 10:
            raise BootstrapInputError("Justificativa obrigatória")
        try:
            approved_at = datetime.fromisoformat(str(raw["approved_at"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise BootstrapInputError("Data de aprovação inválida") from exc
        if approved_at.tzinfo is None:
            raise BootstrapInputError("Data de aprovação exige timezone")
        normalized = dict(raw)
        normalized["legacy_client_id"] = legacy_id
        normalized["mapping_version"] = version
        return cls(normalized)


def run_bootstrap(mapping: LegacyMapping, executor: BootstrapExecutor, *, apply: bool = False):
    """Dry-run é o default; o executor decide atomicidade da persistência."""
    report = dict(executor.process(mapping.payload, apply))
    # Contrato de saída deliberadamente sem subject, nomes ou credenciais.
    allowed = {"mode", "status", "would_create", "existing", "created", "conflicts",
               "blocked_actions", "idempotency_key"}
    return {key: value for key, value in report.items() if key in allowed}
