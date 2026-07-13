#!/usr/bin/env python3
"""CLI de bootstrap: dry-run padrão, apply explícito e DSN nunca exibido."""
import argparse
import json
from pathlib import Path
import sys
from uuid import uuid4

APP = Path(__file__).resolve().parents[2] / "app"
sys.path.insert(0, str(APP))

from services.legacy_bootstrap import BootstrapInputError, LegacyMapping, run_bootstrap  # noqa: E402


BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "db", "wins_agro_v1-db-1"})


def validate_explicit_dsn(dsn: str):
    import psycopg2.extensions

    if not dsn:
        raise ValueError("DSN explícito é obrigatório")
    try:
        parsed = psycopg2.extensions.parse_dsn(dsn)
    except Exception as exc:
        raise ValueError("DSN inválido") from exc
    host = parsed.get("host", "").strip().lower()
    dbname = parsed.get("dbname", "").strip().lower()
    if not host or host.startswith("/") or host in BLOCKED_HOSTS:
        raise ValueError("Host de banco bloqueado")
    if dbname in {"wins_agro", "postgres"} or "production" in dbname or "producao" in dbname:
        raise ValueError("Banco de produção bloqueado")
    return parsed


class PostgresBootstrapExecutor:
    def __init__(self, dsn: str):
        validate_explicit_dsn(dsn)
        self._dsn = dsn

    def process(self, payload, apply):
        import psycopg2
        from psycopg2.extras import Json

        with psycopg2.connect(self._dsn) as connection:
            connection.set_session(readonly=not apply)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT foundation.process_legacy_mapping(%s, %s)",
                    (Json(payload), apply),
                )
                report = cursor.fetchone()[0]
            if not apply:
                connection.rollback()
            return report


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Bootstrap legado explícito da Fase 0B")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.apply and args.confirm != "APPLY_EXPLICIT_LEGACY_MAPPING":
        raise SystemExit("Apply exige --confirm APPLY_EXPLICIT_LEGACY_MAPPING")
    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        mapping = LegacyMapping.parse(raw)
    except (BootstrapInputError, json.JSONDecodeError, OSError):
        print(json.dumps({
            "mode": "apply" if args.apply else "dry-run",
            "status": "blocked",
            "invalid": [{"code": "mapping_invalid"}],
            "blocked_actions": ["apply"],
        }, sort_keys=True))
        return 2
    if args.apply:
        payload = dict(mapping.payload)
        payload["audit_public_ids"] = {
            key: str(uuid4()) for key in ("user", "organization", "membership", "farm", "access", "link")
        }
        mapping = LegacyMapping(payload)
    report = run_bootstrap(mapping, PostgresBootstrapExecutor(args.dsn), apply=args.apply)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
