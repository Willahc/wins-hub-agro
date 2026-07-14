"""Repositório de dados do módulo de Clima e Janelas Operacionais."""
import hashlib
import json
from uuid import UUID
from db import query, _tx, _cur
from domain.audit import AuditEvent, AuditService
from psycopg2.extras import Json


class WeatherOperationsRepository:
    def find_farm(self, farm_public_id: UUID) -> dict | None:
        rows = query(
            """SELECT id, public_id, organization_id, name, status
               FROM foundation.operational_farms
              WHERE public_id = %(pid)s AND status = 'active'""",
            {"pid": str(farm_public_id)},
        )
        return rows[0] if rows else None

    def find_membership(self, user_id: int, org_id: int) -> dict | None:
        rows = query(
            """SELECT id, public_id, organization_id, role, status
               FROM foundation.organization_memberships
              WHERE user_id = %(uid)s AND organization_id = %(oid)s
                AND status = 'active'""",
            {"uid": user_id, "oid": org_id},
        )
        return rows[0] if rows else None

    def find_farm_access(self, membership_id: int, farm_id: int) -> dict | None:
        rows = query(
            """SELECT id, access_level, status
               FROM foundation.farm_access
              WHERE membership_id = %(mid)s AND farm_id = %(fid)s
                AND status = 'active'""",
            {"mid": membership_id, "fid": farm_id},
        )
        return rows[0] if rows else None

    def get_profile(self, farm_id: int) -> dict | None:
        rows = query(
            """SELECT * FROM climate.farm_weather_profiles
              WHERE farm_id = %(fid)s AND archived_at IS NULL
              ORDER BY id DESC LIMIT 1""",
            {"fid": farm_id},
        )
        return rows[0] if rows else None

    def create_profile(self, data: dict, user_id: int) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            sql_data = {k: str(v) if isinstance(v, UUID) else v for k, v in data.items()}
            cur.execute(
                """INSERT INTO climate.farm_weather_profiles
                   (public_id, organization_id, farm_id, latitude, longitude, timezone,
                    provider, enabled, refresh_interval_minutes, forecast_days,
                    status, notes, created_by_user_id)
                   VALUES (%(public_id)s, %(organization_id)s, %(farm_id)s,
                           %(latitude)s, %(longitude)s, %(timezone)s,
                           %(provider)s, %(enabled)s, %(refresh_interval_minutes)s,
                           %(forecast_days)s, %(status)s, %(notes)s, %(created_by_user_id)s)
                   RETURNING id, public_id""",
                sql_data,
            )
            row = cur.fetchone()
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", "create_profile"),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="climate.profile_created",
                entity_type="weather_profile",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={"provider": data["provider"]},
            ))
        return {"id": row["id"], "public_id": row["public_id"]}

    def update_profile(self, profile_id: int, data: dict, user_id: int) -> None:
        with _tx() as conn:
            cur = _cur(conn)
            fields = []
            params = {"id": profile_id}
            for key in ("latitude", "longitude", "timezone", "provider", "enabled",
                        "refresh_interval_minutes", "forecast_days", "notes", "status",
                        "last_attempt_at", "last_success_at", "last_error_at", "last_error_code"):
                if key in data:
                    fields.append(f"{key} = %({key})s")
                    params[key] = data[key]
            if not fields:
                return
            fields.append("updated_at = now()")
            cur.execute(
                f"UPDATE climate.farm_weather_profiles SET {', '.join(fields)} WHERE id = %(id)s",
                params,
            )
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", "update_profile"),
                actor_user_id=user_id,
                organization_id=data.get("organization_id", 0),
                farm_id=data.get("farm_id", 0),
                action="climate.profile_updated",
                entity_type="weather_profile",
                entity_public_id=str(data.get("public_id", "")),
                result="success",
                source="api",
                metadata={"fields": list(data.keys())},
            ))

    def archive_profile(self, profile_id: int, user_id: int, org_id: int, farm_id: int, public_id: UUID) -> None:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                "UPDATE climate.farm_weather_profiles SET archived_at = now() WHERE id = %(id)s",
                {"id": profile_id},
            )
            AuditService().record(cur, AuditEvent(
                request_id="archive_profile",
                actor_user_id=user_id,
                organization_id=org_id,
                farm_id=farm_id,
                action="climate.profile_archived",
                entity_type="weather_profile",
                entity_public_id=str(public_id),
                result="success",
                source="api",
            ))

    def invalidate_cache_for_farm(self, farm_id: int) -> None:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                "DELETE FROM climate.weather_snapshots WHERE farm_id = %(fid)s",
                {"fid": farm_id},
            )

    def save_snapshot(self, data: dict) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            sql_data = {}
            for k, v in data.items():
                if isinstance(v, UUID):
                    sql_data[k] = str(v)
                elif isinstance(v, (dict, list)):
                    sql_data[k] = Json(v)
                else:
                    sql_data[k] = v
            cur.execute(
                """INSERT INTO climate.weather_snapshots
                   (public_id, organization_id, farm_id, profile_id, snapshot_type,
                    period_start, period_end, payload_normalized, provider,
                    provider_reference, normalization_version, fetched_at, expires_at,
                    stale_after, checksum)
                   VALUES (%(public_id)s, %(organization_id)s, %(farm_id)s,
                           %(profile_id)s, %(snapshot_type)s, %(period_start)s,
                           %(period_end)s, %(payload_normalized)s, %(provider)s,
                           %(provider_reference)s, %(normalization_version)s,
                           %(fetched_at)s, %(expires_at)s, %(stale_after)s, %(checksum)s)
                   RETURNING id, public_id""",
                sql_data,
            )
            row = cur.fetchone()
        return {"id": row["id"], "public_id": row["public_id"]}

    def get_fresh_snapshot(self, farm_id: int, snapshot_type: str) -> dict | None:
        rows = query(
            """SELECT * FROM climate.weather_snapshots
              WHERE farm_id = %(fid)s AND snapshot_type = %(stype)s
                AND expires_at > now()
              ORDER BY fetched_at DESC LIMIT 1""",
            {"fid": farm_id, "stype": snapshot_type},
        )
        if not rows:
            rows = query(
                """SELECT * FROM climate.weather_snapshots
                  WHERE farm_id = %(fid)s AND snapshot_type = %(stype)s
                  ORDER BY fetched_at DESC LIMIT 1""",
                {"fid": farm_id, "stype": snapshot_type},
            )
        return rows[0] if rows else None

    def get_any_snapshot(self, farm_id: int, snapshot_type: str) -> dict | None:
        rows = query(
            """SELECT * FROM climate.weather_snapshots
              WHERE farm_id = %(fid)s AND snapshot_type = %(stype)s
              ORDER BY fetched_at DESC LIMIT 1""",
            {"fid": farm_id, "stype": snapshot_type},
        )
        return rows[0] if rows else None

    def save_evaluation(self, data: dict) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            sql_data = {}
            for k, v in data.items():
                if isinstance(v, UUID):
                    sql_data[k] = str(v)
                elif isinstance(v, (dict, list)):
                    sql_data[k] = Json(v)
                else:
                    sql_data[k] = v
            cur.execute(
                """INSERT INTO climate.operational_window_evaluations
                   (public_id, organization_id, farm_id, window_type,
                    period_start, period_end, score, classification,
                    positive_factors, risk_factors, data_snapshot_ids,
                    rule_version, evaluated_at, expires_at,
                    related_harvest_plan_id)
                   VALUES (%(public_id)s, %(organization_id)s, %(farm_id)s,
                           %(window_type)s, %(period_start)s, %(period_end)s,
                           %(score)s, %(classification)s, %(positive_factors)s,
                           %(risk_factors)s, %(data_snapshot_ids)s,
                           %(rule_version)s, %(evaluated_at)s, %(expires_at)s,
                           %(related_harvest_plan_id)s)
                   RETURNING id, public_id""",
                sql_data,
            )
            row = cur.fetchone()
            AuditService().record(cur, AuditEvent(
                request_id="save_evaluation",
                actor_user_id=data.get("created_by_user_id", 0),
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="climate.evaluation_saved",
                entity_type="operational_window",
                entity_public_id=str(row["public_id"]),
                result="success",
                source="api",
                metadata={"window_type": data["window_type"], "classification": data["classification"]},
            ))
        return {"id": row["id"], "public_id": row["public_id"]}

    def list_evaluations(self, farm_id: int, limit: int = 25, offset: int = 0,
                         window_type: str | None = None) -> list[dict]:
        conditions = ["farm_id = %(fid)s"]
        params: dict = {"fid": farm_id, "limit": limit, "offset": offset}
        if window_type:
            conditions.append("window_type = %(wt)s")
            params["wt"] = window_type
        where = " AND ".join(conditions)
        return query(
            f"""SELECT public_id, window_type, period_start, period_end, score,
                       classification, positive_factors, risk_factors, rule_version,
                       evaluated_at, created_at
                  FROM climate.operational_window_evaluations
                 WHERE {where}
                 ORDER BY evaluated_at DESC
                 LIMIT %(limit)s OFFSET %(offset)s""",
            params,
        )

    def count_evaluations(self, farm_id: int, window_type: str | None = None) -> int:
        conditions = ["farm_id = %(fid)s"]
        params: dict = {"fid": farm_id}
        if window_type:
            conditions.append("window_type = %(wt)s")
            params["wt"] = window_type
        where = " AND ".join(conditions)
        rows = query(
            f"SELECT COUNT(*)::int AS cnt FROM climate.operational_window_evaluations WHERE {where}",
            params,
        )
        return rows[0]["cnt"] if rows else 0

    def get_latest_evaluations_by_plan(self, plan_id: int) -> list[dict]:
        return query(
            """SELECT * FROM climate.operational_window_evaluations
              WHERE related_harvest_plan_id = %(pid)s
              ORDER BY evaluated_at DESC LIMIT 10""",
            {"pid": plan_id},
        )

    def find_harvest_plan_by_uuid(self, plan_uuid: UUID, farm_id: int) -> dict | None:
        rows = query(
            """SELECT id, public_id, name, expected_start_date, expected_end_date, status, farm_id
               FROM harvest.harvest_plans
              WHERE public_id = %(pid)s AND farm_id = %(fid)s AND archived_at IS NULL""",
            {"pid": str(plan_uuid), "fid": farm_id},
        )
        return rows[0] if rows else None
