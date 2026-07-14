"""Repositório de dados do módulo de Silagem e Estoques de Alimentação."""
from uuid import UUID
from db import query, _tx, _cur
from domain.audit import AuditEvent, AuditService

import psycopg2


class FeedInventoryRepository:
    # ------------------------------------------------------------------ #
    # Foundation lookups                                                  #
    # ------------------------------------------------------------------ #

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

    # ------------------------------------------------------------------ #
    # Facilities                                                          #
    # ------------------------------------------------------------------ #

    def create_facility(self, data: dict, user_id: int) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            insert_data = {**data, "public_id": str(data["public_id"])}
            cur.execute(
                """INSERT INTO storage.feed_storage_facilities
                   (public_id, organization_id, farm_id, name, code,
                    facility_type, capacity_natural_kg, preferred_display_unit,
                    location_description, active, notes, created_by_user_id)
                   VALUES (%(public_id)s, %(organization_id)s, %(farm_id)s,
                           %(name)s, %(code)s, %(facility_type)s,
                           %(capacity_natural_kg)s, %(preferred_display_unit)s,
                           %(location_description)s, %(active)s, %(notes)s,
                           %(created_by_user_id)s)
                   RETURNING id, public_id""",
                {**insert_data, "created_by_user_id": user_id},
            )
            row = cur.fetchone()
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", ""),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="feed_inventory.facility_created",
                entity_type="feed_storage_facility",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={"name": data["name"], "facility_type": data["facility_type"]},
            ))
        return {"id": row["id"], "public_id": row["public_id"]}

    def get_facility(self, facility_public_id: UUID) -> dict | None:
        rows = query(
            """SELECT f.*, f.public_id
               FROM storage.feed_storage_facilities f
              WHERE f.public_id = %(pid)s AND f.archived_at IS NULL""",
            {"pid": str(facility_public_id)},
        )
        return rows[0] if rows else None

    def list_facilities(self, farm_id: int, limit: int = 25, offset: int = 0) -> list[dict]:
        return query(
            """SELECT f.id, f.public_id, f.name, f.code, f.facility_type,
                      f.capacity_natural_kg, f.preferred_display_unit,
                      f.location_description, f.active, f.notes, f.created_at, f.updated_at
                 FROM storage.feed_storage_facilities f
                WHERE f.farm_id = %(farm_id)s AND f.archived_at IS NULL
                ORDER BY f.name, f.public_id
                LIMIT %(limit)s OFFSET %(offset)s""",
            {"farm_id": farm_id, "limit": limit, "offset": offset},
        )

    def count_facilities(self, farm_id: int) -> int:
        rows = query(
            """SELECT count(*) as n
               FROM storage.feed_storage_facilities
              WHERE farm_id = %(farm_id)s AND archived_at IS NULL""",
            {"farm_id": farm_id},
        )
        return rows[0]["n"] if rows else 0

    def update_facility(self, facility_id: int, data: dict, user_id: int) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE storage.feed_storage_facilities SET
                   name = %(name)s, code = %(code)s, facility_type = %(facility_type)s,
                   capacity_natural_kg = %(capacity_natural_kg)s,
                   preferred_display_unit = %(preferred_display_unit)s,
                   location_description = %(location_description)s,
                   active = %(active)s, notes = %(notes)s, updated_at = now()
                 WHERE id = %(id)s
                 RETURNING id, public_id""",
                {**data, "id": facility_id},
            )
            cur.fetchone()
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", ""),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="feed_inventory.facility_updated",
                entity_type="feed_storage_facility",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={"name": data["name"]},
            ))
        return {"id": facility_id, "public_id": data["public_id"]}

    def archive_facility(self, facility_id: int, user_id: int, org_id: int,
                         farm_id: int, public_id: UUID, request_id: str = "") -> None:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE storage.feed_storage_facilities
                   SET archived_at = now(), updated_at = now()
                 WHERE id = %(fid)s""",
                {"fid": facility_id},
            )
            AuditService().record(cur, AuditEvent(
                request_id=request_id or "archive",
                actor_user_id=user_id,
                organization_id=org_id,
                farm_id=farm_id,
                action="feed_inventory.facility_archived",
                entity_type="feed_storage_facility",
                entity_public_id=public_id,
                result="success",
                source="api",
            ))

    # ------------------------------------------------------------------ #
    # Lots                                                                #
    # ------------------------------------------------------------------ #

    def create_lot(self, data: dict, movement_data: dict, user_id: int) -> dict:
        from domain.feed_inventory import (
            calculate_physical_dm, calculate_usable_dm,
            calculate_cost_per_natural_kg, calculate_inventory_value,
            calculate_cost_per_usable_dm, FORMULA_VERSION
        )
        from decimal import Decimal

        initial_qty = Decimal(str(data["initial_quantity_natural_kg"]))
        dm_pct = Decimal(str(data["dry_matter_pct"]))
        util_pct = Decimal(str(data.get("utilization_pct", 100)))
        initial_cost = Decimal(str(data["initial_total_cost"])) if data.get("initial_total_cost") is not None else None

        phys_dm = calculate_physical_dm(initial_qty, dm_pct)
        usab_dm = calculate_usable_dm(phys_dm, util_pct)
        avg_cost = calculate_cost_per_natural_kg(initial_cost, initial_qty)
        inv_val = calculate_inventory_value(initial_qty, avg_cost)
        cost_per_usab = calculate_cost_per_usable_dm(inv_val, usab_dm)

        params = {
            "public_id": str(data["public_id"]),
            "organization_id": data["organization_id"],
            "farm_id": data["farm_id"],
            "facility_id": data["facility_id"],
            "name": data["name"],
            "feed_type": data["feed_type"],
            "custom_feed_type": data.get("custom_feed_type", ""),
            "production_date": data.get("production_date"),
            "ensiling_date": data.get("ensiling_date"),
            "opened_at": data.get("opened_at"),
            "source_description": data.get("source_description", ""),
            "initial_quantity_natural_kg": initial_qty,
            "current_quantity_natural_kg": initial_qty,
            "dry_matter_pct": dm_pct,
            "utilization_pct": util_pct,
            "current_physical_dm_kg": phys_dm,
            "current_usable_dm_kg": usab_dm,
            "initial_total_cost": initial_cost,
            "average_cost_per_natural_kg": avg_cost,
            "current_inventory_value": inv_val,
            "cost_per_usable_dm_kg": cost_per_usab,
            "planned_daily_use_dm_kg": data.get("planned_daily_use_dm_kg"),
            "status": data["status"],
            "rule_version": FORMULA_VERSION,
            "notes": data.get("notes", ""),
            "created_by_user_id": user_id,
        }

        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """INSERT INTO storage.feed_lots
                   (public_id, organization_id, farm_id, facility_id, name,
                    feed_type, custom_feed_type, production_date, ensiling_date,
                    opened_at, source_description, initial_quantity_natural_kg,
                    current_quantity_natural_kg, dry_matter_pct, utilization_pct,
                    current_physical_dm_kg, current_usable_dm_kg,
                    initial_total_cost, average_cost_per_natural_kg,
                    current_inventory_value, cost_per_usable_dm_kg,
                    planned_daily_use_dm_kg, status, rule_version, notes,
                    created_by_user_id)
                   VALUES (%(public_id)s, %(organization_id)s, %(farm_id)s,
                           %(facility_id)s, %(name)s, %(feed_type)s,
                           %(custom_feed_type)s, %(production_date)s,
                           %(ensiling_date)s, %(opened_at)s,
                           %(source_description)s, %(initial_quantity_natural_kg)s,
                           %(current_quantity_natural_kg)s, %(dry_matter_pct)s,
                           %(utilization_pct)s, %(current_physical_dm_kg)s,
                           %(current_usable_dm_kg)s, %(initial_total_cost)s,
                           %(average_cost_per_natural_kg)s,
                           %(current_inventory_value)s, %(cost_per_usable_dm_kg)s,
                           %(planned_daily_use_dm_kg)s, %(status)s,
                           %(rule_version)s, %(notes)s, %(created_by_user_id)s)
                   RETURNING id, public_id""",
                params,
            )
            row = cur.fetchone()

            if movement_data:
                movement_params = {
                    "public_id": str(movement_data["public_id"]),
                    "organization_id": movement_data["organization_id"],
                    "farm_id": movement_data["farm_id"],
                    "lot_id": row["id"],
                    "movement_type": movement_data["movement_type"],
                    "movement_at": movement_data.get("reference_date"),
                    "quantity_natural_kg": movement_data["quantity_natural_kg"],
                    "dry_matter_pct_snapshot": movement_data.get("dry_matter_pct"),
                    "utilization_pct_snapshot": movement_data.get("utilization_pct", util_pct),
                    "physical_dm_kg": movement_data.get("quantity_dm_kg"),
                    "usable_dm_kg": movement_data.get("usable_dm_kg", usab_dm),
                    "unit_cost_snapshot": movement_data.get("unit_cost"),
                    "total_cost": movement_data.get("total_cost"),
                    "loss_reason": movement_data.get("loss_reason") or "",
                    "reason": movement_data.get("reason", ""),
                    "notes": movement_data.get("notes", ""),
                    "request_id": movement_data.get("request_id", ""),
                    "created_by_user_id": user_id,
                }
                cur.execute(
                    """INSERT INTO storage.feed_stock_movements
                       (public_id, organization_id, farm_id, lot_id,
                        movement_type, movement_at, quantity_natural_kg,
                        dry_matter_pct_snapshot, utilization_pct_snapshot,
                        physical_dm_kg, usable_dm_kg, unit_cost_snapshot,
                        total_cost, loss_reason, reason, notes,
                        request_id, created_by_user_id)
                       VALUES (%(public_id)s, %(organization_id)s, %(farm_id)s, %(lot_id)s,
                               %(movement_type)s, %(movement_at)s, %(quantity_natural_kg)s,
                               %(dry_matter_pct_snapshot)s, %(utilization_pct_snapshot)s,
                               %(physical_dm_kg)s, %(usable_dm_kg)s, %(unit_cost_snapshot)s,
                               %(total_cost)s, %(loss_reason)s, %(reason)s, %(notes)s,
                               %(request_id)s, %(created_by_user_id)s)""",
                    movement_params,
                )

            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", ""),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="feed_inventory.lot_created",
                entity_type="feed_lot",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={
                    "name": data["name"],
                    "feed_type": data["feed_type"],
                    "facility_id": data["facility_id"],
                },
            ))
        return {"id": row["id"], "public_id": row["public_id"]}

    def get_lot(self, lot_public_id: UUID) -> dict | None:
        rows = query(
            """SELECT l.*, l.public_id,
                      COALESCE(f.public_id::text, '') AS facility_public_id,
                      COALESCE(f.name, '') AS facility_name
               FROM storage.feed_lots l
               LEFT JOIN storage.feed_storage_facilities f ON f.id = l.facility_id
              WHERE l.public_id = %(pid)s AND l.archived_at IS NULL""",
            {"pid": str(lot_public_id)},
        )
        return rows[0] if rows else None

    def list_lots(self, farm_id: int, limit: int = 25, offset: int = 0,
                  filters: dict | None = None) -> list[dict]:
        conditions = ["l.farm_id = %(farm_id)s", "l.archived_at IS NULL"]
        params: dict = {"farm_id": farm_id, "limit": limit, "offset": offset}
        if filters:
            if filters.get("status"):
                conditions.append("l.status = %(status)s")
                params["status"] = filters["status"]
            if filters.get("feed_type"):
                conditions.append("l.feed_type = %(feed_type)s")
                params["feed_type"] = filters["feed_type"]
            if filters.get("facility_id"):
                conditions.append("l.facility_id = %(facility_id)s")
                params["facility_id"] = filters["facility_id"]
            if filters.get("search"):
                conditions.append("l.name ILIKE %(search)s")
                params["search"] = f"%{filters['search']}%"
        where = " AND ".join(conditions)
        return query(
            f"""SELECT l.id, l.public_id, l.name, l.feed_type, l.custom_feed_type,
                       l.facility_id,
                       COALESCE(f.public_id::text, '') AS facility_public_id,
                       COALESCE(f.name, '') AS facility_name,
                       l.production_date, l.ensiling_date,
                       l.source_description,
                       l.initial_quantity_natural_kg,
                       l.current_quantity_natural_kg, l.dry_matter_pct,
                       l.utilization_pct, l.current_physical_dm_kg,
                       l.current_usable_dm_kg, l.initial_total_cost,
                       l.average_cost_per_natural_kg,
                       l.current_inventory_value, l.cost_per_usable_dm_kg,
                       l.planned_daily_use_dm_kg, l.status, l.rule_version,
                       l.notes, l.created_at, l.updated_at
                  FROM storage.feed_lots l
                  LEFT JOIN storage.feed_storage_facilities f ON f.id = l.facility_id
                 WHERE {where}
                 ORDER BY l.name, l.public_id
                 LIMIT %(limit)s OFFSET %(offset)s""",
            params,
        )

    def count_lots(self, farm_id: int, filters: dict | None = None) -> int:
        conditions = ["farm_id = %(farm_id)s", "archived_at IS NULL"]
        params: dict = {"farm_id": farm_id}
        if filters:
            if filters.get("status"):
                conditions.append("status = %(status)s")
                params["status"] = filters["status"]
            if filters.get("feed_type"):
                conditions.append("feed_type = %(feed_type)s")
                params["feed_type"] = filters["feed_type"]
            if filters.get("facility_id"):
                conditions.append("facility_id = %(facility_id)s")
                params["facility_id"] = filters["facility_id"]
            if filters.get("search"):
                conditions.append("name ILIKE %(search)s")
                params["search"] = f"%{filters['search']}%"
        where = " AND ".join(conditions)
        rows = query(
            f"SELECT count(*) as n FROM storage.feed_lots WHERE {where}",
            params,
        )
        return rows[0]["n"] if rows else 0

    def update_lot(self, lot_id: int, data: dict, user_id: int) -> dict:
        """Update lot metadata only (NOT balance fields)."""
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE storage.feed_lots SET
                   name = %(name)s, feed_type = %(feed_type)s,
                   custom_feed_type = %(custom_feed_type)s,
                   production_date = %(production_date)s,
                   ensiling_date = %(ensiling_date)s,
                   opened_at = %(opened_at)s,
                   source_description = %(source_description)s,
                   dry_matter_pct = %(dry_matter_pct)s,
                   utilization_pct = %(utilization_pct)s,
                   initial_total_cost = %(initial_total_cost)s,
                   planned_daily_use_dm_kg = %(planned_daily_use_dm_kg)s,
                   status = %(status)s, notes = %(notes)s, updated_at = now()
                 WHERE id = %(id)s
                 RETURNING id, public_id""",
                {**data, "id": lot_id},
            )
            cur.fetchone()
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", ""),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="feed_inventory.lot_updated",
                entity_type="feed_lot",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={"name": data["name"], "feed_type": data["feed_type"]},
            ))
        return {"id": lot_id, "public_id": data["public_id"]}

    def archive_lot(self, lot_id: int, user_id: int, org_id: int,
                    farm_id: int, public_id: UUID, request_id: str = "") -> None:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE storage.feed_lots
                   SET archived_at = now(), updated_at = now()
                 WHERE id = %(lid)s""",
                {"lid": lot_id},
            )
            AuditService().record(cur, AuditEvent(
                request_id=request_id or "archive",
                actor_user_id=user_id,
                organization_id=org_id,
                farm_id=farm_id,
                action="feed_inventory.lot_archived",
                entity_type="feed_lot",
                entity_public_id=public_id,
                result="success",
                source="api",
            ))

    def get_lot_for_update(self, lot_id: int) -> dict | None:
        rows = query(
            """SELECT l.*, l.public_id
               FROM storage.feed_lots l
              WHERE l.id = %(lid)s AND l.archived_at IS NULL
              FOR UPDATE""",
            {"lid": lot_id},
        )
        return rows[0] if rows else None

    def update_lot_balance(
        self,
        lot_id: int,
        current_quantity_natural_kg: float,
        current_physical_dm_kg: float,
        current_usable_dm_kg: float,
        current_inventory_value: float,
        average_cost_per_natural_kg: float | None,
        cost_per_usable_dm_kg: float | None,
        status: str,
        user_id: int,
    ) -> None:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE storage.feed_lots SET
                   current_quantity_natural_kg = %(cqty)s,
                   current_physical_dm_kg = %(cpdm)s,
                   current_usable_dm_kg = %(cudm)s,
                   current_inventory_value = %(civ)s,
                   average_cost_per_natural_kg = %(acnk)s,
                   cost_per_usable_dm_kg = %(cpudm)s,
                   status = %(status)s, updated_at = now()
                 WHERE id = %(lid)s""",
                {
                    "lid": lot_id,
                    "cqty": current_quantity_natural_kg,
                    "cpdm": current_physical_dm_kg,
                    "cudm": current_usable_dm_kg,
                    "civ": current_inventory_value,
                    "acnk": average_cost_per_natural_kg,
                    "cpudm": cost_per_usable_dm_kg,
                    "status": status,
                },
            )

    # ------------------------------------------------------------------ #
    # Movements (ledger imutável)                                         #
    # ------------------------------------------------------------------ #

    def create_movement(self, data: dict, lot_update: dict, lot_id: int, user_id: int) -> dict:
        from domain.feed_inventory import (
            calculate_physical_dm, calculate_usable_dm,
            calculate_inventory_value, calculate_cost_per_usable_dm
        )
        from decimal import Decimal

        with _tx() as conn:
            cur = _cur(conn)

            # 1. Fetch current lot to get snapshot values for calculations
            cur.execute(
                """SELECT dry_matter_pct, utilization_pct, initial_total_cost,
                          initial_quantity_natural_kg, average_cost_per_natural_kg
                     FROM storage.feed_lots
                    WHERE id = %(lid)s FOR UPDATE""",
                {"lid": lot_id},
            )
            lot_row = cur.fetchone()
            if not lot_row:
                raise ValueError("Lot not found")

            dm_pct = Decimal(str(lot_row["dry_matter_pct"]))
            util_pct = Decimal(str(lot_row["utilization_pct"]))
            avg_cost = Decimal(str(lot_row["average_cost_per_natural_kg"])) if lot_row["average_cost_per_natural_kg"] is not None else None

            # 2. Calculate movement physical and usable DM
            qty_nat = Decimal(str(data["quantity_natural_kg"]))
            mv_dm_pct = Decimal(str(data.get("dry_matter_pct") if data.get("dry_matter_pct") is not None else dm_pct))
            phys_dm = calculate_physical_dm(qty_nat, mv_dm_pct)
            usab_dm = calculate_usable_dm(phys_dm, util_pct)

            movement_params = {
                "public_id": str(data["public_id"]),
                "organization_id": data["organization_id"],
                "farm_id": data["farm_id"],
                "lot_id": lot_id,
                "movement_type": data["movement_type"],
                "movement_at": data.get("reference_date"),
                "quantity_natural_kg": qty_nat,
                "dry_matter_pct_snapshot": mv_dm_pct,
                "utilization_pct_snapshot": util_pct,
                "physical_dm_kg": phys_dm,
                "usable_dm_kg": usab_dm,
                "unit_cost_snapshot": data.get("unit_cost"),
                "total_cost": data.get("total_cost"),
                "loss_reason": data.get("loss_reason") or "",
                "reason": data.get("reason", ""),
                "notes": data.get("notes", ""),
                "request_id": data.get("request_id", ""),
                "created_by_user_id": user_id,
            }

            try:
                cur.execute(
                    """INSERT INTO storage.feed_stock_movements
                       (public_id, organization_id, farm_id, lot_id,
                        movement_type, movement_at, quantity_natural_kg,
                        dry_matter_pct_snapshot, utilization_pct_snapshot,
                        physical_dm_kg, usable_dm_kg, unit_cost_snapshot,
                        total_cost, loss_reason, reason, notes,
                        request_id, created_by_user_id)
                       VALUES (%(public_id)s, %(organization_id)s, %(farm_id)s, %(lot_id)s,
                               %(movement_type)s, %(movement_at)s, %(quantity_natural_kg)s,
                               %(dry_matter_pct_snapshot)s, %(utilization_pct_snapshot)s,
                               %(physical_dm_kg)s, %(usable_dm_kg)s, %(unit_cost_snapshot)s,
                               %(total_cost)s, %(loss_reason)s, %(reason)s, %(notes)s,
                               %(request_id)s, %(created_by_user_id)s)
                       RETURNING id, public_id""",
                    movement_params,
                )
            except psycopg2.IntegrityError:
                raise ValueError("duplicate_request_id")
            row = cur.fetchone()

            # 3. Calculate new lot balances and update storage.feed_lots
            bal_nat = Decimal(str(lot_update["balance_natural_kg"]))
            new_phys = calculate_physical_dm(bal_nat, dm_pct)
            new_usab = calculate_usable_dm(new_phys, util_pct)
            new_inv_val = calculate_inventory_value(bal_nat, avg_cost)
            new_cost_per_usable = calculate_cost_per_usable_dm(new_inv_val, new_usab)

            cur.execute(
                """UPDATE storage.feed_lots SET
                   current_quantity_natural_kg = %(qty)s,
                   current_physical_dm_kg = %(phys)s,
                   current_usable_dm_kg = %(usab)s,
                   current_inventory_value = %(val)s,
                   cost_per_usable_dm_kg = %(cpudm)s,
                   status = %(status)s,
                   updated_at = now()
                 WHERE id = %(lid)s""",
                {
                    "qty": bal_nat,
                    "phys": new_phys,
                    "usab": new_usab,
                    "val": new_inv_val,
                    "cpudm": new_cost_per_usable,
                    "status": lot_update["status"],
                    "lid": lot_id,
                }
            )

            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", ""),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action=f"feed_inventory.movement_{data['movement_type']}",
                entity_type="feed_stock_movement",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={
                    "lot_id": lot_id,
                    "movement_type": data["movement_type"],
                    "quantity_natural_kg": str(qty_nat),
                },
            ))
        return {"id": row["id"], "public_id": row["public_id"]}

    def list_movements(self, lot_id: int, limit: int = 50,
                       offset: int = 0) -> list[dict]:
        return query(
            """SELECT m.id, m.public_id, m.movement_type, m.movement_at,
                      m.quantity_natural_kg, m.dry_matter_pct_snapshot,
                      m.utilization_pct_snapshot, m.physical_dm_kg,
                      m.usable_dm_kg, m.unit_cost_snapshot, m.total_cost,
                      m.loss_reason, m.reason, m.notes, m.request_id,
                      m.created_at, l.public_id AS lot_public_id, l.name AS lot_name,
                      SUM(CASE WHEN m.movement_type IN ('initial_balance', 'entry', 'adjustment_positive') THEN m.quantity_natural_kg
                               ELSE -m.quantity_natural_kg
                          END) OVER (PARTITION BY m.lot_id ORDER BY m.movement_at ASC, m.id ASC) AS balance_after_natural_kg
                 FROM storage.feed_stock_movements m
                 JOIN storage.feed_lots l ON l.id = m.lot_id
                WHERE m.lot_id = %(lid)s
                ORDER BY m.movement_at DESC, m.id DESC
                LIMIT %(limit)s OFFSET %(offset)s""",
            {"lid": lot_id, "limit": limit, "offset": offset},
        )

    def count_movements(self, lot_id: int) -> int:
        rows = query(
            """SELECT count(*) as n
               FROM storage.feed_stock_movements
              WHERE lot_id = %(lid)s""",
            {"lid": lot_id},
        )
        return rows[0]["n"] if rows else 0

    def get_movement(self, movement_public_id: UUID) -> dict | None:
        rows = query(
            """SELECT m.*, l.public_id AS lot_public_id, l.name AS lot_name,
                      (SELECT SUM(CASE WHEN m2.movement_type IN ('initial_balance', 'entry', 'adjustment_positive') THEN m2.quantity_natural_kg
                                       ELSE -m2.quantity_natural_kg
                                  END)
                         FROM storage.feed_stock_movements m2
                        WHERE m2.lot_id = m.lot_id
                          AND (m2.movement_at < m.movement_at OR (m2.movement_at = m.movement_at AND m2.id <= m.id))
                      ) AS balance_after_natural_kg
                 FROM storage.feed_stock_movements m
                 JOIN storage.feed_lots l ON l.id = m.lot_id
                WHERE m.public_id = %(pid)s""",
            {"pid": str(movement_public_id)},
        )
        return rows[0] if rows else None

    # ------------------------------------------------------------------ #
    # Reconciliation (ledger replay)                                      #
    # ------------------------------------------------------------------ #

    def get_all_movements_for_lot(self, lot_id: int) -> list[dict]:
        return query(
            """SELECT m.id, m.public_id, m.movement_type, m.movement_at,
                      m.quantity_natural_kg, m.dry_matter_pct_snapshot,
                      m.utilization_pct_snapshot, m.physical_dm_kg,
                      m.usable_dm_kg, m.unit_cost_snapshot, m.total_cost,
                      m.loss_reason, m.reason, m.notes, m.request_id,
                      m.created_by_user_id, m.created_at
                 FROM storage.feed_stock_movements m
                WHERE m.lot_id = %(lid)s
                ORDER BY m.movement_at ASC""",
            {"lid": lot_id},
        )

    # ------------------------------------------------------------------ #
    # Dashboard                                                           #
    # ------------------------------------------------------------------ #

    def get_dashboard(self, farm_id: int) -> dict:
        lots = query(
            """SELECT l.id, l.name, l.feed_type, l.facility_id, l.status,
                      l.current_quantity_natural_kg, l.current_physical_dm_kg,
                      l.current_usable_dm_kg, l.current_inventory_value,
                      l.cost_per_usable_dm_kg, l.dry_matter_pct, l.utilization_pct
                 FROM storage.feed_lots l
                WHERE l.farm_id = %(fid)s AND l.archived_at IS NULL""",
            {"fid": farm_id},
        )
        total_lots = len(lots)
        total_natural_kg = sum(l["current_quantity_natural_kg"] or 0 for l in lots)
        total_physical_dm_kg = sum(l["current_physical_dm_kg"] or 0 for l in lots)
        total_usable_dm_kg = sum(l["current_usable_dm_kg"] or 0 for l in lots)
        total_inventory_value = sum(l["current_inventory_value"] or 0 for l in lots)

        available_lots = [l for l in lots if l["status"] == "available"]
        opened_lots = [l for l in lots if l["status"] == "opened"]
        reserved_lots = [l for l in lots if l["status"] == "reserved"]
        depleted_lots = [l for l in lots if l["status"] == "depleted"]
        quarantined_lots = [l for l in lots if l["status"] == "quarantined"]

        feed_types: dict[str, float] = {}
        for l in lots:
            ft = l["feed_type"]
            feed_types[ft] = feed_types.get(ft, 0) + (l["current_quantity_natural_kg"] or 0)

        facilities = query(
            """SELECT f.id, f.name, f.facility_type, f.capacity_natural_kg
                 FROM storage.feed_storage_facilities f
                WHERE f.farm_id = %(fid)s AND f.archived_at IS NULL""",
            {"fid": farm_id},
        )
        total_facilities = len(facilities)

        recent_movements = query(
            """SELECT m.id, m.public_id, m.movement_type, m.movement_at,
                      m.quantity_natural_kg, m.lot_id, l.name as lot_name
                 FROM storage.feed_stock_movements m
                 JOIN storage.feed_lots l ON l.id = m.lot_id
                WHERE l.farm_id = %(fid)s
                ORDER BY m.movement_at DESC
                LIMIT 10""",
            {"fid": farm_id},
        )

        return {
            "total_lots": total_lots,
            "total_facilities": total_facilities,
            "total_natural_kg": float(total_natural_kg),
            "total_physical_dm_kg": float(total_physical_dm_kg),
            "total_usable_dm_kg": float(total_usable_dm_kg),
            "total_inventory_value": float(total_inventory_value),
            "available_count": len(available_lots),
            "opened_count": len(opened_lots),
            "reserved_count": len(reserved_lots),
            "depleted_count": len(depleted_lots),
            "quarantined_count": len(quarantined_lots),
            "feed_types_summary": {k: float(v) for k, v in feed_types.items()},
            "recent_movements": recent_movements,
        }

    # ------------------------------------------------------------------ #
    # Autonomy sources (importação para Autonomia Alimentar)              #
    # ------------------------------------------------------------------ #

    def get_autonomy_sources(self, farm_id: int) -> list[dict]:
        lots = query(
            """SELECT l.id, l.public_id, l.name, l.feed_type, l.status,
                      l.current_quantity_natural_kg, l.current_usable_dm_kg,
                      l.dry_matter_pct, l.utilization_pct,
                      l.current_inventory_value, l.cost_per_usable_dm_kg,
                      l.facility_id, f.name as facility_name
                 FROM storage.feed_lots l
                 JOIN storage.feed_storage_facilities f ON f.id = l.facility_id
                WHERE l.farm_id = %(fid)s
                  AND l.archived_at IS NULL
                  AND l.current_quantity_natural_kg > 0
                  AND l.status IN ('available', 'opened', 'reserved')""",
            {"fid": farm_id},
        )
        results = []
        for l in lots:
            results.append({
                "lot_public_id": str(l["public_id"]),
                "name": l["name"],
                "feed_type": l["feed_type"],
                "status": l["status"],
                "facility_id": l["facility_id"],
                "facility_name": l["facility_name"],
                "current_quantity_natural_kg": str(l["current_quantity_natural_kg"]),
                "current_usable_dm_kg": str(l["current_usable_dm_kg"]),
                "dry_matter_pct": str(l["dry_matter_pct"]),
                "utilization_pct": str(l["utilization_pct"]),
                "current_inventory_value": str(l["current_inventory_value"]),
                "cost_per_usable_dm_kg": str(l["cost_per_usable_dm_kg"]) if l["cost_per_usable_dm_kg"] else None,
            })
        return results

    def count_active_lots_for_facility(self, facility_id: int) -> int:
        rows = query(
            """SELECT count(*) as n FROM storage.feed_lots
              WHERE facility_id = %(fid)s""",
            {"fid": facility_id},
        )
        return rows[0]["n"] if rows else 0

    def list_active_lots(self, farm_id: int) -> list[dict]:
        return query(
            """SELECT l.*, l.public_id, f.name as facility_name
               FROM storage.feed_lots l
               JOIN storage.feed_storage_facilities f ON f.id = l.facility_id
              WHERE l.farm_id = %(fid)s AND l.archived_at IS NULL
                AND l.status NOT IN ('archived', 'depleted')
                AND l.current_quantity_natural_kg > 0
              ORDER BY l.name""",
            {"fid": farm_id},
        )

    def get_facility_by_id(self, facility_id: int) -> dict | None:
        rows = query(
            """SELECT f.*, f.public_id
               FROM storage.feed_storage_facilities f
              WHERE f.id = %(fid)s AND f.archived_at IS NULL""",
            {"fid": facility_id},
        )
        return rows[0] if rows else None

    def get_movements_for_reconciliation(self, lot_id: int) -> list[dict]:
        return query(
            """SELECT movement_type, quantity_natural_kg
               FROM storage.feed_stock_movements
              WHERE lot_id = %(lid)s
              ORDER BY movement_at ASC""",
            {"lid": lot_id},
        )

    def find_movement_by_request_id(self, lot_id: int, request_id: str) -> dict | None:
        if not request_id:
            return None
        rows = query(
            """SELECT m.*, l.public_id AS lot_public_id, l.name AS lot_name,
                      (SELECT SUM(CASE WHEN m2.movement_type IN ('initial_balance', 'entry', 'adjustment_positive') THEN m2.quantity_natural_kg
                                       ELSE -m2.quantity_natural_kg
                                  END)
                         FROM storage.feed_stock_movements m2
                        WHERE m2.lot_id = m.lot_id
                          AND (m2.movement_at < m.movement_at OR (m2.movement_at = m.movement_at AND m2.id <= m.id))
                      ) AS balance_after_natural_kg
                 FROM storage.feed_stock_movements m
                 JOIN storage.feed_lots l ON l.id = m.lot_id
                WHERE m.lot_id = %(lid)s AND m.request_id = %(rid)s""",
            {"lid": lot_id, "rid": request_id},
        )
        return rows[0] if rows else None
