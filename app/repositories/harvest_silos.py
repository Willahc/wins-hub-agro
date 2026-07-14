"""Repositório de dados do módulo de Colheita e Silos."""
from uuid import UUID
from datetime import date
from decimal import Decimal
from db import query, _tx, _cur
from domain.audit import AuditEvent, AuditService

class HarvestSilosRepository:

    # ------------------------------------------------------------------ #
    # Foundation Lookups                                                 #
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
    # Facilities Lookups                                                 #
    # ------------------------------------------------------------------ #

    def get_facility_by_uuid(self, facility_uuid: UUID) -> dict | None:
        rows = query(
            """SELECT id, public_id, farm_id, name, capacity_natural_kg
               FROM storage.feed_storage_facilities
              WHERE public_id = %(pid)s AND archived_at IS NULL""",
            {"pid": str(facility_uuid)},
        )
        return rows[0] if rows else None

    def get_facility_by_id(self, facility_id: int) -> dict | None:
        rows = query(
            """SELECT id, public_id, farm_id, name, capacity_natural_kg
               FROM storage.feed_storage_facilities
              WHERE id = %(id)s AND archived_at IS NULL""",
            {"id": facility_id},
        )
        return rows[0] if rows else None

    def get_facility_capacity_and_stock(self, facility_id: int) -> tuple[Decimal | None, Decimal]:
        # Capacity
        fac = self.get_facility_by_id(facility_id)
        capacity = Decimal(str(fac["capacity_natural_kg"])) if fac and fac.get("capacity_natural_kg") is not None else None

        # Stock
        rows = query(
            """SELECT COALESCE(SUM(current_quantity_natural_kg), 0) as stock
               FROM storage.feed_lots
              WHERE facility_id = %(fid)s
                AND archived_at IS NULL
                AND status != 'archived'""",
            {"fid": facility_id},
        )
        stock = Decimal(str(rows[0]["stock"])) if rows else Decimal("0.00")
        return capacity, stock

    # ------------------------------------------------------------------ #
    # Harvest Plans DML                                                  #
    # ------------------------------------------------------------------ #

    def create_plan(self, plan_data: dict, areas: list[dict], allocations: list[dict]) -> dict:
        with _tx() as conn:
            cur = _cur(conn)

            # 1. Insert plan
            plan_params = {**plan_data, "public_id": str(plan_data["public_id"])}
            cur.execute(
                """INSERT INTO harvest.harvest_plans
                   (public_id, organization_id, farm_id, name, main_crop, purpose,
                    expected_start_date, expected_end_date, expected_field_loss_pct, expected_ensiling_loss_pct,
                    expected_gross_natural_kg, expected_net_natural_kg, expected_dm_kg, status, Notes, created_by_user_id)
                   VALUES
                   (%(public_id)s, %(organization_id)s, %(farm_id)s, %(name)s, %(main_crop)s, %(purpose)s,
                    %(expected_start_date)s, %(expected_end_date)s, %(expected_field_loss_pct)s, %(expected_ensiling_loss_pct)s,
                    %(expected_gross_natural_kg)s, %(expected_net_natural_kg)s, %(expected_dm_kg)s, %(status)s, %(notes)s, %(created_by_user_id)s)
                   RETURNING id, public_id""",
                plan_params
            )
            plan_row = cur.fetchone()
            plan_id = plan_row["id"]

            # 2. Insert areas
            for area in areas:
                area_params = {
                    **area,
                    "public_id": str(area["public_id"]),
                    "plan_id": plan_id,
                    "organization_id": plan_data["organization_id"],
                    "farm_id": plan_data["farm_id"]
                }
                cur.execute(
                    """INSERT INTO harvest.harvest_plan_areas
                       (public_id, plan_id, organization_id, farm_id, name, crop, cultivar, area_ha,
                        expected_yield_t_ha, expected_dm_pct, expected_harvest_date,
                        calculated_gross_natural_kg, calculated_net_natural_kg, calculated_dm_kg, notes, display_order)
                       VALUES
                       (%(public_id)s, %(plan_id)s, %(organization_id)s, %(farm_id)s, %(name)s, %(crop)s, %(cultivar)s, %(area_ha)s,
                        %(expected_yield_t_ha)s, %(expected_dm_pct)s, %(expected_harvest_date)s,
                        %(calculated_gross_natural_kg)s, %(calculated_net_natural_kg)s, %(calculated_dm_kg)s, %(notes)s, %(display_order)s)""",
                    area_params
                )

            # 3. Insert allocations
            for alloc in allocations:
                alloc_params = {
                    **alloc,
                    "public_id": str(alloc["public_id"]),
                    "plan_id": plan_id,
                    "organization_id": plan_data["organization_id"],
                    "farm_id": plan_data["farm_id"]
                }
                cur.execute(
                    """INSERT INTO harvest.harvest_storage_allocations
                       (public_id, plan_id, organization_id, farm_id, facility_id, expected_quantity_natural_kg,
                        expected_percentage, capacity_snapshot_kg, current_stock_snapshot_kg, projected_occupancy_kg,
                        projected_occupancy_pct, capacity_status)
                       VALUES
                       (%(public_id)s, %(plan_id)s, %(organization_id)s, %(farm_id)s, %(facility_id)s, %(expected_natural_kg)s,
                        %(percentage)s, %(capacity_snapshot_kg)s, %(current_stock_snapshot_kg)s, %(projected_occupancy_kg)s,
                        %(projected_occupancy_pct)s, %(capacity_status)s)""",
                    alloc_params
                )

            # Audit
            AuditService().record(cur, AuditEvent(
                request_id=plan_data.get("request_id", ""),
                actor_user_id=plan_data["created_by_user_id"],
                organization_id=plan_data["organization_id"],
                farm_id=plan_data["farm_id"],
                action="harvest.plan_created",
                entity_type="harvest_plan",
                entity_public_id=plan_row["public_id"],
                result="success",
                source="api",
                metadata={"name": plan_data["name"]}
            ))

            return {"id": plan_id, "public_id": plan_row["public_id"]}

    def update_plan(self, plan_id: int, plan_data: dict, areas: list[dict], allocations: list[dict]) -> None:
        with _tx() as conn:
            cur = _cur(conn)

            # 1. Update plan details
            cur.execute(
                """UPDATE harvest.harvest_plans
                      SET name = %(name)s,
                          main_crop = %(main_crop)s,
                          purpose = %(purpose)s,
                          expected_start_date = %(expected_start_date)s,
                          expected_end_date = %(expected_end_date)s,
                          expected_field_loss_pct = %(expected_field_loss_pct)s,
                          expected_ensiling_loss_pct = %(expected_ensiling_loss_pct)s,
                          expected_gross_natural_kg = %(expected_gross_natural_kg)s,
                          expected_net_natural_kg = %(expected_net_natural_kg)s,
                          expected_dm_kg = %(expected_dm_kg)s,
                          notes = %(notes)s,
                          updated_at = now()
                    WHERE id = %(plan_id)s""",
                {**plan_data, "plan_id": plan_id}
            )

            # 2. Delete existing areas and insert new ones
            cur.execute("DELETE FROM harvest.harvest_plan_areas WHERE plan_id = %(plan_id)s", {"plan_id": plan_id})
            for area in areas:
                area_params = {
                    **area,
                    "public_id": str(area["public_id"]),
                    "plan_id": plan_id,
                    "organization_id": plan_data["organization_id"],
                    "farm_id": plan_data["farm_id"]
                }
                cur.execute(
                    """INSERT INTO harvest.harvest_plan_areas
                       (public_id, plan_id, organization_id, farm_id, name, crop, cultivar, area_ha,
                        expected_yield_t_ha, expected_dm_pct, expected_harvest_date,
                        calculated_gross_natural_kg, calculated_net_natural_kg, calculated_dm_kg, notes, display_order)
                       VALUES
                       (%(public_id)s, %(plan_id)s, %(organization_id)s, %(farm_id)s, %(name)s, %(crop)s, %(cultivar)s, %(area_ha)s,
                        %(expected_yield_t_ha)s, %(expected_dm_pct)s, %(expected_harvest_date)s,
                        %(calculated_gross_natural_kg)s, %(calculated_net_natural_kg)s, %(calculated_dm_kg)s, %(notes)s, %(display_order)s)""",
                    area_params
                )

            # 3. Delete existing allocations and insert new ones
            cur.execute("DELETE FROM harvest.harvest_storage_allocations WHERE plan_id = %(plan_id)s", {"plan_id": plan_id})
            for alloc in allocations:
                alloc_params = {
                    **alloc,
                    "public_id": str(alloc["public_id"]),
                    "plan_id": plan_id,
                    "organization_id": plan_data["organization_id"],
                    "farm_id": plan_data["farm_id"]
                }
                cur.execute(
                    """INSERT INTO harvest.harvest_storage_allocations
                       (public_id, plan_id, organization_id, farm_id, facility_id, expected_quantity_natural_kg,
                        expected_percentage, capacity_snapshot_kg, current_stock_snapshot_kg, projected_occupancy_kg,
                        projected_occupancy_pct, capacity_status)
                       VALUES
                       (%(public_id)s, %(plan_id)s, %(organization_id)s, %(farm_id)s, %(facility_id)s, %(expected_natural_kg)s,
                        %(percentage)s, %(capacity_snapshot_kg)s, %(current_stock_snapshot_kg)s, %(projected_occupancy_kg)s,
                        %(projected_occupancy_pct)s, %(capacity_status)s)""",
                    alloc_params
                )

            # Audit
            AuditService().record(cur, AuditEvent(
                request_id=plan_data.get("request_id", ""),
                actor_user_id=plan_data["created_by_user_id"],
                organization_id=plan_data["organization_id"],
                farm_id=plan_data["farm_id"],
                action="harvest.plan_updated",
                entity_type="harvest_plan",
                entity_public_id=plan_data["public_id"],
                result="success",
                source="api",
                metadata={"name": plan_data["name"]}
            ))

    def archive_plan(self, plan_id: int, request_id: str, user_id: int) -> None:
        p = self.get_plan_by_id(plan_id)
        if not p:
            return
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE harvest.harvest_plans
                      SET archived_at = now(),
                          status = 'archived',
                          updated_at = now()
                    WHERE id = %(plan_id)s""",
                {"plan_id": plan_id}
            )
            # Audit
            AuditService().record(cur, AuditEvent(
                request_id=request_id,
                actor_user_id=user_id,
                organization_id=p["organization_id"],
                farm_id=p["farm_id"],
                action="harvest.plan_archived",
                entity_type="harvest_plan",
                entity_public_id=p["public_id"],
                result="success",
                source="api",
                metadata={}
            ))

    def start_plan(self, plan_id: int, actual_start_date: date, request_id: str, user_id: int) -> None:
        p = self.get_plan_by_id(plan_id)
        if not p:
            return
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE harvest.harvest_plans
                      SET status = 'in_progress',
                          actual_start_date = %(start_date)s,
                          updated_at = now()
                    WHERE id = %(plan_id)s""",
                {"plan_id": plan_id, "start_date": actual_start_date}
            )
            # Audit
            AuditService().record(cur, AuditEvent(
                request_id=request_id,
                actor_user_id=user_id,
                organization_id=p["organization_id"],
                farm_id=p["farm_id"],
                action="harvest.plan_started",
                entity_type="harvest_plan",
                entity_public_id=p["public_id"],
                result="success",
                source="api",
                metadata={}
            ))

    # ------------------------------------------------------------------ #
    # Retrieval                                                          #
    # ------------------------------------------------------------------ #

    def get_plan(self, plan_uuid: UUID) -> dict | None:
        rows = query(
            """SELECT * FROM harvest.harvest_plans
              WHERE public_id = %(pid)s AND archived_at IS NULL""",
            {"pid": str(plan_uuid)}
        )
        return rows[0] if rows else None

    def get_plan_by_id(self, plan_id: int) -> dict | None:
        rows = query(
            """SELECT * FROM harvest.harvest_plans
              WHERE id = %(id)s AND archived_at IS NULL""",
            {"id": plan_id}
        )
        return rows[0] if rows else None

    def get_plan_areas(self, plan_id: int) -> list[dict]:
        return query(
            """SELECT * FROM harvest.harvest_plan_areas
              WHERE plan_id = %(plan_id)s AND archived_at IS NULL
              ORDER BY display_order ASC, id ASC""",
            {"plan_id": plan_id}
        )

    def get_plan_allocations(self, plan_id: int) -> list[dict]:
        return query(
            """SELECT a.*, f.name as facility_name, f.public_id as facility_uuid,
                      l.public_id as created_feed_lot_uuid
               FROM harvest.harvest_storage_allocations a
               JOIN storage.feed_storage_facilities f ON f.id = a.facility_id
               LEFT JOIN storage.feed_lots l ON l.id = a.created_feed_lot_id
              WHERE a.plan_id = %(plan_id)s AND a.archived_at IS NULL
              ORDER BY a.id ASC""",
            {"plan_id": plan_id}
        )

    def list_plans(self, farm_id: int, limit: int, offset: int, status_filter: str | None,
                   crop_filter: str | None, start_date: date | None, end_date: date | None,
                   search_query: str | None) -> list[dict]:
        sql = """SELECT * FROM harvest.harvest_plans
                  WHERE farm_id = %(farm_id)s AND archived_at IS NULL"""
        params = {"farm_id": farm_id, "limit": limit, "offset": offset}

        if status_filter:
            sql += " AND status = %(status)s"
            params["status"] = status_filter
        if crop_filter:
            sql += " AND main_crop = %(crop)s"
            params["crop"] = crop_filter
        if start_date:
            sql += " AND expected_start_date >= %(start_date)s"
            params["start_date"] = start_date
        if end_date:
            sql += " AND expected_start_date <= %(end_date)s"
            params["end_date"] = end_date
        if search_query:
            sql += " AND name ILIKE %(search)s"
            params["search"] = f"%{search_query}%"

        sql += " ORDER BY expected_start_date DESC, id DESC LIMIT %(limit)s OFFSET %(offset)s"
        return query(sql, params)

    def count_plans(self, farm_id: int, status_filter: str | None,
                    crop_filter: str | None, start_date: date | None, end_date: date | None,
                    search_query: str | None) -> int:
        sql = """SELECT COUNT(*) as cnt FROM harvest.harvest_plans
                  WHERE farm_id = %(farm_id)s AND archived_at IS NULL"""
        params = {"farm_id": farm_id}

        if status_filter:
            sql += " AND status = %(status)s"
            params["status"] = status_filter
        if crop_filter:
            sql += " AND main_crop = %(crop)s"
            params["crop"] = crop_filter
        if start_date:
            sql += " AND expected_start_date >= %(start_date)s"
            params["start_date"] = start_date
        if end_date:
            sql += " AND expected_start_date <= %(end_date)s"
            params["end_date"] = end_date
        if search_query:
            sql += " AND name ILIKE %(search)s"
            params["search"] = f"%{search_query}%"

        rows = query(sql, params)
        return rows[0]["cnt"] if rows else 0

    def get_dashboard(self, farm_id: int) -> dict:
        rows = query(
            """SELECT
                 COUNT(*) FILTER (WHERE status IN ('draft','planned','in_progress')) AS active_plans_count,
                 COALESCE(SUM((SELECT COALESCE(SUM(a.area_ha),0)
                                 FROM harvest.harvest_plan_areas a WHERE a.plan_id=p.id AND a.archived_at IS NULL))
                          FILTER (WHERE p.status IN ('draft','planned','in_progress')),0) AS planned_area_ha,
                 COALESCE(SUM(expected_gross_natural_kg) FILTER (WHERE status IN ('draft','planned','in_progress')),0) AS expected_gross_natural_kg,
                 COALESCE(SUM(expected_net_natural_kg) FILTER (WHERE status IN ('draft','planned','in_progress')),0) AS expected_net_natural_kg,
                 COALESCE(SUM(expected_dm_kg) FILTER (WHERE status IN ('draft','planned','in_progress')),0) AS expected_dm_kg,
                 COALESCE(SUM(expected_net_natural_kg) FILTER (WHERE status IN ('draft','planned','in_progress')),0) AS capacity_needed_kg,
                 COUNT(*) FILTER (WHERE EXISTS (
                   SELECT 1 FROM harvest.harvest_storage_allocations x
                    WHERE x.plan_id=p.id AND x.capacity_status='over_capacity' AND x.archived_at IS NULL
                 )) AS over_capacity_plans_count,
                 COUNT(*) FILTER (WHERE expected_start_date BETWEEN current_date AND current_date + 30
                                    AND status IN ('draft','planned')) AS upcoming_cuts_count
               FROM harvest.harvest_plans p
              WHERE p.farm_id=%(farm_id)s AND p.archived_at IS NULL""",
            {"farm_id": farm_id},
        )
        result = rows[0] if rows else {}
        capacity = query(
            """SELECT COALESCE(SUM(GREATEST(f.capacity_natural_kg-COALESCE(s.stock,0),0)),0) AS capacity_available_kg
                 FROM storage.feed_storage_facilities f
                 LEFT JOIN (SELECT facility_id, SUM(current_quantity_natural_kg) stock
                              FROM storage.feed_lots WHERE archived_at IS NULL AND status <> 'archived'
                             GROUP BY facility_id) s ON s.facility_id=f.id
                WHERE f.farm_id=%(farm_id)s AND f.archived_at IS NULL AND f.active=true""",
            {"farm_id": farm_id},
        )
        result["capacity_available_kg"] = capacity[0]["capacity_available_kg"] if capacity else Decimal("0")
        return result

    # ------------------------------------------------------------------ #
    # Completion & Lot Generation                                        #
    # ------------------------------------------------------------------ #

    def complete_plan_and_create_lots(
        self,
        plan_id: int,
        actual_start_date: date,
        actual_end_date: date,
        actual_natural_kg: Decimal,
        actual_dm_pct: Decimal,
        actual_loss_pct: Decimal,
        allocations_actual: list[dict],
        created_lots: list[dict],
        created_movements: list[dict],
        request_id: str,
        payload_hash: str,
        user_id: int
    ) -> None:
        with _tx() as conn:
            cur = _cur(conn)

            # 1. Lock harvest plan to prevent concurrent completions
            cur.execute(
                """SELECT id, status, organization_id, farm_id, public_id, name
                     FROM harvest.harvest_plans
                    WHERE id = %(plan_id)s
                      FOR UPDATE""",
                {"plan_id": plan_id}
            )
            plan = cur.fetchone()
            if not plan:
                raise ValueError("plan_not_found")
            if plan["status"] == "completed":
                raise ValueError("plan_already_completed")

            # 2. Lock facilities
            fac_ids = [alloc["facility_id"] for alloc in allocations_actual]
            if fac_ids:
                cur.execute(
                    """SELECT id FROM storage.feed_storage_facilities
                        WHERE id = ANY(%(fac_ids)s)
                          FOR UPDATE""",
                    {"fac_ids": fac_ids}
                )

            # 3. Create feed lots and movements
            for i, lot in enumerate(created_lots):
                m_data = created_movements[i]

                # Insert Lot
                cur.execute(
                    """INSERT INTO storage.feed_lots
                       (public_id, organization_id, farm_id, facility_id, name, feed_type,
                        custom_feed_type, production_date, ensiling_date, opened_at, source_description,
                        initial_quantity_natural_kg, current_quantity_natural_kg, dry_matter_pct, utilization_pct,
                        current_physical_dm_kg, current_usable_dm_kg, initial_total_cost, average_cost_per_natural_kg,
                        current_inventory_value, cost_per_usable_dm_kg, planned_daily_use_dm_kg, status, rule_version, notes,
                        created_by_user_id)
                       VALUES
                       (%(public_id)s, %(organization_id)s, %(farm_id)s, %(facility_id)s, %(name)s, %(feed_type)s,
                        %(custom_feed_type)s, %(production_date)s, %(ensiling_date)s, %(opened_at)s, %(source_description)s,
                        %(initial_quantity_natural_kg)s, %(current_quantity_natural_kg)s, %(dry_matter_pct)s, %(utilization_pct)s,
                        %(current_physical_dm_kg)s, %(current_usable_dm_kg)s, %(initial_total_cost)s, %(average_cost_per_natural_kg)s,
                        %(current_inventory_value)s, %(cost_per_usable_dm_kg)s, %(planned_daily_use_dm_kg)s, %(status)s,
                        %(rule_version)s, %(notes)s, %(created_by_user_id)s)
                       RETURNING id""",
                    {**lot, "public_id": str(lot["public_id"])}
                )
                lot_row = cur.fetchone()
                lot_db_id = lot_row["id"]

                # Insert Movement
                cur.execute(
                    """INSERT INTO storage.feed_stock_movements
                       (public_id, organization_id, farm_id, lot_id, movement_type, movement_at, quantity_natural_kg,
                        dry_matter_pct_snapshot, utilization_pct_snapshot, physical_dm_kg, usable_dm_kg,
                        unit_cost_snapshot, total_cost, loss_reason, reason, notes, request_id, created_by_user_id)
                       VALUES
                       (%(public_id)s, %(organization_id)s, %(farm_id)s, %(lot_id)s, %(movement_type)s, %(movement_at)s,
                        %(quantity_natural_kg)s, %(dry_matter_pct_snapshot)s, %(utilization_pct_snapshot)s, %(physical_dm_kg)s,
                        %(usable_dm_kg)s, %(unit_cost_snapshot)s, %(total_cost)s, %(loss_reason)s, %(reason)s, %(notes)s,
                        %(request_id)s, %(created_by_user_id)s)""",
                    {**m_data, "public_id": str(m_data["public_id"]), "lot_id": lot_db_id}
                )

                # Record Feed Inventory Audit
                AuditService().record(cur, AuditEvent(
                    request_id=request_id,
                    actor_user_id=user_id,
                    organization_id=plan["organization_id"],
                    farm_id=plan["farm_id"],
                    action="feed_inventory.lot_created",
                    entity_type="feed_lot",
                    entity_public_id=lot["public_id"],
                    result="success",
                    source="api",
                    metadata={"name": lot["name"], "feed_type": lot["feed_type"], "facility_id": lot["facility_id"]}
                ))

                # Update Allocation with actual quantity and created feed lot ID
                alloc = allocations_actual[i]
                cur.execute(
                    """UPDATE harvest.harvest_storage_allocations
                          SET actual_quantity_natural_kg = %(actual_qty)s,
                              created_feed_lot_id = %(lot_id)s,
                              updated_at = now()
                        WHERE public_id = %(alloc_uuid)s""",
                    {"actual_qty": alloc["actual_natural_kg"], "lot_id": lot_db_id, "alloc_uuid": str(alloc["public_id"])}
                )

            # 4. Update Plan status to completed
            cur.execute(
                """UPDATE harvest.harvest_plans
                      SET status = 'completed',
                          actual_start_date = %(actual_start_date)s,
                          actual_end_date = %(actual_end_date)s,
                          actual_natural_kg = %(actual_natural_kg)s,
                          actual_dm_pct = %(actual_dm_pct)s,
                          actual_loss_pct = %(actual_loss_pct)s,
                          completion_request_id = %(request_id)s,
                          completion_payload_hash = %(payload_hash)s,
                          completed_by_user_id = %(user_id)s,
                          completed_at = now(),
                          updated_at = now()
                    WHERE id = %(plan_id)s""",
                {
                    "plan_id": plan_id,
                    "actual_start_date": actual_start_date,
                    "actual_end_date": actual_end_date,
                    "actual_natural_kg": actual_natural_kg,
                    "actual_dm_pct": actual_dm_pct,
                    "actual_loss_pct": actual_loss_pct,
                    "request_id": request_id,
                    "payload_hash": payload_hash,
                    "user_id": user_id
                }
            )

            # 5. Record Harvest Plan Audit
            AuditService().record(cur, AuditEvent(
                request_id=request_id,
                actor_user_id=user_id,
                organization_id=plan["organization_id"],
                farm_id=plan["farm_id"],
                action="harvest.plan_completed",
                entity_type="harvest_plan",
                entity_public_id=plan["public_id"],
                result="success",
                source="api",
                metadata={"name": plan["name"]}
            ))

            AuditService().record(cur, AuditEvent(
                request_id=request_id,
                actor_user_id=user_id,
                organization_id=plan["organization_id"],
                farm_id=plan["farm_id"],
                action="harvest.inventory_lots_created",
                entity_type="harvest_plan",
                entity_public_id=plan["public_id"],
                result="success",
                source="api",
                metadata={"lot_count": len(created_lots)}
            ))
