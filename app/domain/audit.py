"""Auditoria transacional e sanitizada para operações da fundação."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Mapping
from uuid import UUID, uuid4


_SENSITIVE_PARTS = frozenset({"password", "senha", "token", "secret", "cookie", "authorization", "credential"})
_ALLOWED_METADATA = frozenset({"reason_code", "permission", "resource_type", "formula_code", "parameter_code", "version"})


def sanitize_metadata(metadata: Mapping[str, object] | None) -> dict[str, object]:
    """Mantém apenas metadados operacionais não sensíveis e escalares."""
    clean: dict[str, object] = {}
    for key, value in (metadata or {}).items():
        normalized = str(key).lower()
        if any(part in normalized for part in _SENSITIVE_PARTS):
            continue
        if normalized not in _ALLOWED_METADATA:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            clean[normalized] = value
    return clean


def content_hash(value: Mapping[str, object] | None) -> str | None:
    if value is None:
        return None
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class AuditEvent:
    request_id: str
    action: str
    entity_type: str
    result: str
    source: str
    actor_user_id: int | None = None
    actor_membership_id: int | None = None
    organization_id: int | None = None
    farm_id: int | None = None
    entity_public_id: UUID | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    before_hash: str | None = None
    after_hash: str | None = None
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AuditService:
    """Grava usando o cursor da mesma transação da operação de negócio."""

    def record(self, cursor, event: AuditEvent) -> None:
        cursor.execute(
            """
            INSERT INTO foundation.audit_events (
                public_id, occurred_at, request_id, actor_user_id,
                actor_membership_id, organization_id, farm_id, action,
                entity_type, entity_public_id, result, source, metadata,
                before_hash, after_hash
            ) VALUES (
                %(public_id)s, %(occurred_at)s, %(request_id)s, %(actor_user_id)s,
                %(actor_membership_id)s, %(organization_id)s, %(farm_id)s, %(action)s,
                %(entity_type)s, %(entity_public_id)s, %(result)s, %(source)s,
                %(metadata)s::jsonb, %(before_hash)s, %(after_hash)s
            )
            """,
            {
                "public_id": str(uuid4()),
                "occurred_at": event.occurred_at,
                "request_id": event.request_id,
                "actor_user_id": event.actor_user_id,
                "actor_membership_id": event.actor_membership_id,
                "organization_id": event.organization_id,
                "farm_id": event.farm_id,
                "action": event.action,
                "entity_type": event.entity_type,
                "entity_public_id": str(event.entity_public_id) if event.entity_public_id else None,
                "result": event.result,
                "source": event.source,
                "metadata": json.dumps(sanitize_metadata(event.metadata), ensure_ascii=False),
                "before_hash": event.before_hash,
                "after_hash": event.after_hash,
            },
        )
