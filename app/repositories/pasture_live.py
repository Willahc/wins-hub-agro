"""Repositório de dados do módulo de Pasto Vivo."""
from uuid import UUID
from db import query, _tx, _cur
from domain.audit import AuditEvent, AuditService
from domain.pasture_live import EventType


class PastureLiveRepository:
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

    def create_paddock(self, data: dict, user_id: int) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            insert_data = {**data, "public_id": str(data["public_id"])}
            cur.execute(
                """INSERT INTO pasture.paddocks
                   (public_id, organization_id, farm_id, name, code,
                    area_ha, forage_species, cultivar,
                    target_entry_height_cm, target_exit_height_cm,
                    planned_rest_days, default_utilization_pct,
                    manual_status, active, notes, created_by_user_id)
                   VALUES (%(public_id)s, %(organization_id)s, %(farm_id)s,
                           %(name)s, %(code)s, %(area_ha)s, %(forage_species)s,
                           %(cultivar)s, %(target_entry_height_cm)s,
                           %(target_exit_height_cm)s, %(planned_rest_days)s,
                           %(default_utilization_pct)s, %(manual_status)s,
                           %(active)s, %(notes)s, %(created_by_user_id)s)
                   RETURNING id, public_id""",
                insert_data,
            )
            row = cur.fetchone()
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", "create_measurement"),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="pasture.paddock_created",
                entity_type="pasture_live_paddock",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={"name": data["name"], "area_ha": str(data["area_ha"])},
            ))
        return {"id": row["id"], "public_id": row["public_id"]}

    def get_paddock(self, paddock_public_id: UUID) -> dict | None:
        rows = query(
            """SELECT p.*, p.public_id
               FROM pasture.paddocks p
              WHERE p.public_id = %(pid)s AND p.archived_at IS NULL""",
            {"pid": str(paddock_public_id)},
        )
        return rows[0] if rows else None

    def list_paddocks(self, farm_id: int, limit: int = 25, offset: int = 0,
                      include_archived: bool = False) -> list[dict]:
        conditions = ["p.farm_id = %(farm_id)s"]
        if not include_archived:
            conditions.append("p.archived_at IS NULL")
        where = " AND ".join(conditions)
        return query(
            f"""SELECT p.public_id, p.name, p.area_ha, p.forage_species,
                       p.planned_rest_days, p.manual_status, p.active,
                       p.default_utilization_pct, p.target_entry_height_cm,
                       p.target_exit_height_cm, p.code, p.cultivar, p.notes,
                       p.created_at, p.updated_at
                  FROM pasture.paddocks p
                 WHERE {where}
                 ORDER BY p.name
                 LIMIT %(limit)s OFFSET %(offset)s""",
            {"farm_id": farm_id, "limit": limit, "offset": offset},
        )

    def count_paddocks(self, farm_id: int, include_archived: bool = False) -> int:
        conditions = ["farm_id = %(farm_id)s"]
        if not include_archived:
            conditions.append("archived_at IS NULL")
        where = " AND ".join(conditions)
        rows = query(
            f"SELECT count(*) as n FROM pasture.paddocks WHERE {where}",
            {"farm_id": farm_id},
        )
        return rows[0]["n"] if rows else 0

    def update_paddock(self, paddock_id: int, data: dict, user_id: int) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE pasture.paddocks SET
                   name = %(name)s, code = %(code)s, area_ha = %(area_ha)s,
                   forage_species = %(forage_species)s, cultivar = %(cultivar)s,
                   target_entry_height_cm = %(target_entry_height_cm)s,
                   target_exit_height_cm = %(target_exit_height_cm)s,
                   planned_rest_days = %(planned_rest_days)s,
                   default_utilization_pct = %(default_utilization_pct)s,
                   manual_status = %(manual_status)s, active = %(active)s,
                   notes = %(notes)s, updated_at = now()
                 WHERE id = %(id)s RETURNING id, public_id""",
                {**data, "id": paddock_id},
            )
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", ""),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="pasture.paddock_updated",
                entity_type="pasture_live_paddock",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={"name": data["name"]},
            ))
        return {"id": paddock_id, "public_id": data["public_id"]}

    def update_paddock_manual_status(self, paddock_id: int, new_status: str, user_id: int) -> None:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE pasture.paddocks
                   SET manual_status = %(status)s, updated_at = now()
                 WHERE id = %(pid)s""",
                {"pid": paddock_id, "status": new_status},
            )

    def archive_paddock(self, paddock_id: int, user_id: int, org_id: int,
                        farm_id: int, public_id: UUID, request_id: str = "") -> None:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE pasture.paddocks
                   SET archived_at = now(), updated_at = now()
                 WHERE id = %(sid)s""",
                {"sid": paddock_id},
            )
            AuditService().record(cur, AuditEvent(
                request_id=request_id or "archive",
                actor_user_id=user_id,
                organization_id=org_id,
                farm_id=farm_id,
                action="pasture.paddock_archived",
                entity_type="pasture_live_paddock",
                entity_public_id=public_id,
                result="success",
                source="api",
            ))

    def create_measurement(self, data: dict, user_id: int) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            insert_data = {**data, "public_id": str(data["public_id"])}
            cur.execute(
                """INSERT INTO pasture.paddock_measurements
                   (public_id, paddock_id, farm_id, organization_id,
                    measurement_method, measured_at, available_dm_kg_ha, utilization_pct,
                    calculated_total_dm_kg, calculated_usable_dm_kg,
                    notes, measured_by_user_id)
                   VALUES (%(public_id)s, %(paddock_id)s, %(farm_id)s,
                           %(organization_id)s, %(measurement_method)s, %(measured_at)s,
                           %(available_dm_kg_ha)s, %(utilization_pct)s,
                           %(calculated_total_dm_kg)s, %(calculated_usable_dm_kg)s,
                           %(notes)s, %(measured_by_user_id)s)
                   RETURNING id, public_id""",
                insert_data,
            )
            row = cur.fetchone()
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", ""),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="pasture.measurement_created",
                entity_type="pasture_live_measurement",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={
                    "paddock_id": data["paddock_id"],
                    "method": data["measurement_method"],
                    "available_dm_kg_ha": str(data["available_dm_kg_ha"]),
                },
            ))
        return {"id": row["id"], "public_id": row["public_id"]}

    def get_measurement(self, measurement_public_id: UUID) -> dict | None:
        rows = query(
            """SELECT m.*, m.public_id
               FROM pasture.paddock_measurements m
              WHERE m.public_id = %(pid)s AND m.archived_at IS NULL""",
            {"pid": str(measurement_public_id)},
        )
        return rows[0] if rows else None

    def list_measurements(self, paddock_id: int, limit: int = 50,
                          offset: int = 0) -> list[dict]:
        return query(
            """SELECT m.public_id, m.measurement_method, m.measured_at,
                      m.available_dm_kg_ha, m.utilization_pct,
                      m.calculated_total_dm_kg, m.calculated_usable_dm_kg,
                      m.average_height_cm, m.notes, m.created_at
                 FROM pasture.paddock_measurements m
                WHERE m.paddock_id = %(pid)s AND m.archived_at IS NULL
                ORDER BY m.measured_at DESC
                LIMIT %(limit)s OFFSET %(offset)s""",
            {"pid": paddock_id, "limit": limit, "offset": offset},
        )

    def count_measurements(self, paddock_id: int) -> int:
        rows = query(
            "SELECT count(*) as n FROM pasture.paddock_measurements WHERE paddock_id = %(pid)s AND archived_at IS NULL",
            {"pid": paddock_id},
        )
        return rows[0]["n"] if rows else 0

    def archive_measurement(self, measurement_id: int, user_id: int, org_id: int,
                            farm_id: int, public_id: UUID) -> None:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE pasture.paddock_measurements
                   SET archived_at = now()
                 WHERE id = %(mid)s""",
                {"mid": measurement_id},
            )
            AuditService().record(cur, AuditEvent(
                request_id="",
                actor_user_id=user_id,
                organization_id=org_id,
                farm_id=farm_id,
                action="pasture.measurement_archived",
                entity_type="pasture_live_measurement",
                entity_public_id=public_id,
                result="success",
                source="api",
            ))

    def get_latest_measurement(self, paddock_id: int) -> dict | None:
        rows = query(
            """SELECT m.*, m.public_id
               FROM pasture.paddock_measurements m
              WHERE m.paddock_id = %(pid)s AND m.archived_at IS NULL
              ORDER BY m.measured_at DESC
              LIMIT 1""",
            {"pid": paddock_id},
        )
        return rows[0] if rows else None

    def create_event(self, data: dict, user_id: int) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            insert_data = {**data, "public_id": str(data["public_id"])}
            cur.execute(
                """INSERT INTO pasture.paddock_events
                   (public_id, paddock_id, farm_id, organization_id,
                    event_type, event_at, expected_end_at, actual_end_at,
                    head_count, average_weight_kg, management_group_name,
                    notes, created_by_user_id)
                   VALUES (%(public_id)s, %(paddock_id)s, %(farm_id)s,
                           %(organization_id)s, %(event_type)s,
                           %(event_at)s, %(expected_end_at)s, %(actual_end_at)s,
                           %(head_count)s, %(average_weight_kg)s,
                           %(management_group_name)s, %(notes)s,
                           %(created_by_user_id)s)
                   RETURNING id, public_id""",
                insert_data,
            )
            row = cur.fetchone()
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", ""),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action=f"pasture.event_{data['event_type']}",
                entity_type="pasture_live_event",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={
                    "paddock_id": data["paddock_id"],
                    "event_type": data["event_type"],
                },
            ))
        return {"id": row["id"], "public_id": row["public_id"]}

    def list_events(self, paddock_id: int, limit: int = 50,
                    offset: int = 0) -> list[dict]:
        return query(
            """SELECT e.public_id, e.event_type, e.notes, e.created_at,
                      e.head_count, e.average_weight_kg, e.management_group_name,
                      e.expected_end_at, e.actual_end_at
                 FROM pasture.paddock_events e
                WHERE e.paddock_id = %(pid)s
                ORDER BY e.created_at DESC
                LIMIT %(limit)s OFFSET %(offset)s""",
            {"pid": paddock_id, "limit": limit, "offset": offset},
        )

    def count_events(self, paddock_id: int) -> int:
        rows = query(
            "SELECT count(*) as n FROM pasture.paddock_events WHERE paddock_id = %(pid)s",
            {"pid": paddock_id},
        )
        return rows[0]["n"] if rows else 0

    def get_open_grazing_event(self, paddock_id: int) -> dict | None:
        rows = query(
            """SELECT e.event_type
               FROM pasture.paddock_events e
              WHERE e.paddock_id = %(pid)s
              ORDER BY e.created_at DESC
              LIMIT 1""",
            {"pid": paddock_id},
        )
        if rows and rows[0]["event_type"] == EventType.GRAZING_STARTED.value:
            return rows[0]
        return None

    def get_open_grazing_event_v2(self, paddock_id: int) -> dict | None:
        rows = query(
            """SELECT e.*, e.public_id
               FROM pasture.paddock_events e
              WHERE e.paddock_id = %(pid)s
                AND e.event_type = 'grazing_started'
                AND NOT EXISTS (
                    SELECT 1 FROM pasture.paddock_events ef
                    WHERE ef.paddock_id = e.paddock_id
                      AND ef.event_type = 'grazing_finished'
                      AND ef.created_at > e.created_at
                )
              ORDER BY e.created_at DESC
              LIMIT 1""",
            {"pid": paddock_id},
        )
        return rows[0] if rows else None

    def get_dashboard(self, farm_id: int) -> dict:
        paddocks = query(
            """SELECT p.id, p.name, p.manual_status, p.area_ha, p.active
               FROM pasture.paddocks p
              WHERE p.farm_id = %(fid)s AND p.archived_at IS NULL""",
            {"fid": farm_id},
        )
        total_paddocks = len(paddocks)
        active_paddocks = [
            p for p in paddocks
            if p["active"] and p["manual_status"] != "unavailable"
        ]
        grazing_count = sum(1 for p in active_paddocks if p["manual_status"] == "grazing")
        resting_count = sum(1 for p in active_paddocks if p["manual_status"] == "resting")
        ready_count = sum(1 for p in active_paddocks if p["manual_status"] == "ready")
        attention_count = sum(1 for p in active_paddocks if p["manual_status"] == "attention")
        total_area = sum(p["area_ha"] or Decimal("0") for p in active_paddocks)

        measurements = query(
            """SELECT m.paddock_id, m.available_dm_kg_ha, m.calculated_usable_dm_kg,
                      m.measured_at, m.utilization_pct
               FROM pasture.paddock_measurements m
              INNER JOIN pasture.paddocks p ON p.id = m.paddock_id
              WHERE p.farm_id = %(fid)s AND m.archived_at IS NULL
              AND p.archived_at IS NULL""",
            {"fid": farm_id},
        )
        total_usable_dm = sum(m["calculated_usable_dm_kg"] or Decimal("0") for m in measurements)

        return {
            "total_paddocks": total_paddocks,
            "active_paddocks": len(active_paddocks),
            "grazing_count": grazing_count,
            "resting_count": resting_count,
            "ready_count": ready_count,
            "attention_count": attention_count,
            "total_area_ha": str(total_area),
            "total_usable_dm_kg": str(total_usable_dm),
            "measurements_total": len(measurements),
        }

    def get_autonomy_sources(self, farm_id: int) -> list[dict]:
        paddocks = query(
            """SELECT p.id, p.public_id, p.name, p.area_ha, p.forage_species, p.manual_status
               FROM pasture.paddocks p
              WHERE p.farm_id = %(fid)s
                AND p.archived_at IS NULL
                AND p.active = true
                AND p.manual_status != 'unavailable'""",
            {"fid": farm_id},
        )
        results = []
        for p in paddocks:
            latest = query(
                """SELECT available_dm_kg_ha, calculated_usable_dm_kg, utilization_pct, measured_at
                   FROM pasture.paddock_measurements
                  WHERE paddock_id = %(pid)s AND archived_at IS NULL
                  ORDER BY measured_at DESC LIMIT 1""",
                {"pid": p["id"]},
            )
            m = latest[0] if latest else None
            results.append({
                "paddock_public_id": str(p["public_id"]),
                "name": p["name"],
                "area_ha": str(p["area_ha"]),
                "forage_species": p["forage_species"],
                "status": p["manual_status"],
                "latest_measurement": {
                    "available_dm_kg_ha": str(m["available_dm_kg_ha"]) if m else None,
                    "usable_dm_kg": str(m["calculated_usable_dm_kg"]) if m else None,
                    "utilization_pct": str(m["utilization_pct"]) if m else None,
                    "measured_at": m["measured_at"].isoformat() if m and hasattr(m["measured_at"], "isoformat") else str(m["measured_at"]) if m else None,
                } if m else None,
            })
        return results
