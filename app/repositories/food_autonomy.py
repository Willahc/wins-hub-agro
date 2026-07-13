"""Repositório de dados do módulo de Autonomia Alimentar."""
from uuid import UUID
from db import query, _tx, _cur
from domain.audit import AuditEvent, AuditService


class FoodAutonomyRepository:
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

    def list_scenarios(
        self, farm_id: int, limit: int = 25, offset: int = 0,
        status_filter: str | None = None, include_archived: bool = False,
    ) -> list[dict]:
        conditions = ["s.farm_id = %(farm_id)s"]
        if not include_archived:
            conditions.append("s.archived_at IS NULL")
        if status_filter:
            conditions.append("s.status = %(status_filter)s")
        where = " AND ".join(conditions)
        return query(
            f"""SELECT s.public_id, s.name, s.reference_date, s.target_days,
                       s.status, s.formula_version, s.autonomy_days,
                       s.total_daily_demand_dm_kg, s.total_physical_dm_kg,
                       s.balance_dm_kg, s.balance_days, s.estimated_end_date,
                       s.created_at, s.updated_at
                  FROM nutrition.food_autonomy_scenarios s
                 WHERE {where}
                 ORDER BY s.reference_date DESC, s.created_at DESC
                 LIMIT %(limit)s OFFSET %(offset)s""",
            {"farm_id": farm_id, "limit": limit, "offset": offset,
             "status_filter": status_filter},
        )

    def count_scenarios(self, farm_id: int, include_archived: bool = False) -> int:
        conditions = ["farm_id = %(farm_id)s"]
        if not include_archived:
            conditions.append("archived_at IS NULL")
        where = " AND ".join(conditions)
        rows = query(
            f"SELECT count(*) as n FROM nutrition.food_autonomy_scenarios WHERE {where}",
            {"farm_id": farm_id},
        )
        return rows[0]["n"] if rows else 0

    def get_scenario(self, scenario_public_id: UUID) -> dict | None:
        rows = query(
            """SELECT s.*, s.public_id
               FROM nutrition.food_autonomy_scenarios s
              WHERE s.public_id = %(pid)s""",
            {"pid": str(scenario_public_id)},
        )
        if not rows:
            return None
        s = rows[0]
        s["herd_items"] = query(
            """SELECT category, custom_category_name, head_count, average_weight_kg,
                      intake_pct_body_weight, calculated_daily_demand_dm_kg, display_order
                 FROM nutrition.food_autonomy_herd_items
                WHERE scenario_id = %(sid)s ORDER BY display_order""",
            {"sid": s["id"]},
        )
        s["pasture_items"] = query(
            """SELECT name, area_ha, available_dm_kg_ha, utilization_pct,
                      calculated_usable_dm_kg, notes, display_order
                 FROM nutrition.food_autonomy_pasture_items
                WHERE scenario_id = %(sid)s ORDER BY display_order""",
            {"sid": s["id"]},
        )
        s["feed_items"] = query(
            """SELECT feed_type, name, quantity_natural_kg, dry_matter_pct,
                      utilization_pct, calculated_usable_dm_kg, notes, display_order
                 FROM nutrition.food_autonomy_feed_items
                WHERE scenario_id = %(sid)s ORDER BY display_order""",
            {"sid": s["id"]},
        )
        return s

    def create_scenario(self, data: dict, herd: list[dict], pastures: list[dict],
                        feeds: list[dict], user_id: int) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """INSERT INTO nutrition.food_autonomy_scenarios
                   (public_id, organization_id, farm_id, name, reference_date,
                    target_days, safety_margin_pct, total_daily_demand_dm_kg,
                    total_pasture_dm_kg, total_stored_feed_dm_kg, total_physical_dm_kg,
                    reserve_dm_kg, planning_available_dm_kg, autonomy_days,
                    target_required_dm_kg, balance_dm_kg, balance_days, status,
                    estimated_end_date, formula_version, notes, created_by_user_id)
                   VALUES (%(public_id)s, %(organization_id)s, %(farm_id)s, %(name)s,
                           %(reference_date)s, %(target_days)s, %(safety_margin_pct)s,
                           %(total_daily_demand_dm_kg)s, %(total_pasture_dm_kg)s,
                           %(total_stored_feed_dm_kg)s, %(total_physical_dm_kg)s,
                           %(reserve_dm_kg)s, %(planning_available_dm_kg)s,
                           %(autonomy_days)s, %(target_required_dm_kg)s,
                           %(balance_dm_kg)s, %(balance_days)s, %(status)s,
                           %(estimated_end_date)s, %(formula_version)s, %(notes)s,
                           %(created_by_user_id)s)
                   RETURNING id, public_id""",
                data,
            )
            row = cur.fetchone()
            scenario_id = row["id"]
            self._insert_herd(cur, scenario_id, herd)
            self._insert_pasture(cur, scenario_id, pastures)
            self._insert_feed(cur, scenario_id, feeds)
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", ""),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="food_autonomy.scenario_created",
                entity_type="food_autonomy_scenario",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={
                    "formula_version": data["formula_version"],
                    "herd_item_count": len(herd),
                    "pasture_item_count": len(pastures),
                    "feed_item_count": len(feeds),
                    "status": data["status"],
                },
            ))
        return {"id": scenario_id, "public_id": data["public_id"]}

    def update_scenario(self, scenario_id: int, data: dict, herd: list[dict],
                        pastures: list[dict], feeds: list[dict], user_id: int) -> dict:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE nutrition.food_autonomy_scenarios SET
                   name = %(name)s, reference_date = %(reference_date)s,
                   target_days = %(target_days)s, safety_margin_pct = %(safety_margin_pct)s,
                   total_daily_demand_dm_kg = %(total_daily_demand_dm_kg)s,
                   total_pasture_dm_kg = %(total_pasture_dm_kg)s,
                   total_stored_feed_dm_kg = %(total_stored_feed_dm_kg)s,
                   total_physical_dm_kg = %(total_physical_dm_kg)s,
                   reserve_dm_kg = %(reserve_dm_kg)s,
                   planning_available_dm_kg = %(planning_available_dm_kg)s,
                   autonomy_days = %(autonomy_days)s,
                   target_required_dm_kg = %(target_required_dm_kg)s,
                   balance_dm_kg = %(balance_dm_kg)s,
                   balance_days = %(balance_days)s, status = %(status)s,
                   estimated_end_date = %(estimated_end_date)s, notes = %(notes)s,
                   updated_at = now()
                 WHERE id = %(id)s RETURNING id, public_id""",
                {**data, "id": scenario_id},
            )
            cur.execute("DELETE FROM nutrition.food_autonomy_herd_items WHERE scenario_id = %(sid)s", {"sid": scenario_id})
            cur.execute("DELETE FROM nutrition.food_autonomy_pasture_items WHERE scenario_id = %(sid)s", {"sid": scenario_id})
            cur.execute("DELETE FROM nutrition.food_autonomy_feed_items WHERE scenario_id = %(sid)s", {"sid": scenario_id})
            self._insert_herd(cur, scenario_id, herd)
            self._insert_pasture(cur, scenario_id, pastures)
            self._insert_feed(cur, scenario_id, feeds)
            AuditService().record(cur, AuditEvent(
                request_id=data.get("request_id", ""),
                actor_user_id=user_id,
                organization_id=data["organization_id"],
                farm_id=data["farm_id"],
                action="food_autonomy.scenario_updated",
                entity_type="food_autonomy_scenario",
                entity_public_id=data["public_id"],
                result="success",
                source="api",
                metadata={
                    "formula_version": data["formula_version"],
                    "herd_item_count": len(herd),
                    "pasture_item_count": len(pastures),
                    "feed_item_count": len(feeds),
                    "status": data["status"],
                },
            ))
        return {"id": scenario_id, "public_id": data["public_id"]}

    def archive_scenario(self, scenario_id: int, user_id: int, org_id: int, farm_id: int,
                         public_id: UUID) -> None:
        with _tx() as conn:
            cur = _cur(conn)
            cur.execute(
                """UPDATE nutrition.food_autonomy_scenarios
                   SET archived_at = now(), updated_at = now()
                 WHERE id = %(sid)s""",
                {"sid": scenario_id},
            )
            AuditService().record(cur, AuditEvent(
                request_id="",
                actor_user_id=user_id,
                organization_id=org_id,
                farm_id=farm_id,
                action="food_autonomy.scenario_archived",
                entity_type="food_autonomy_scenario",
                entity_public_id=public_id,
                result="success",
                source="api",
            ))

    def _insert_herd(self, cur, scenario_id: int, items: list[dict]) -> None:
        for i, item in enumerate(items):
            cur.execute(
                """INSERT INTO nutrition.food_autonomy_herd_items
                   (scenario_id, category, custom_category_name, head_count,
                    average_weight_kg, intake_pct_body_weight,
                    calculated_daily_demand_dm_kg, display_order)
                   VALUES (%(sid)s, %(category)s, %(custom_category_name)s,
                           %(head_count)s, %(average_weight_kg)s,
                           %(intake_pct_body_weight)s,
                           %(calculated_daily_demand_dm_kg)s, %(display_order)s)""",
                {**item, "sid": scenario_id, "display_order": item.get("display_order", i)},
            )

    def _insert_pasture(self, cur, scenario_id: int, items: list[dict]) -> None:
        for i, item in enumerate(items):
            cur.execute(
                """INSERT INTO nutrition.food_autonomy_pasture_items
                   (scenario_id, name, area_ha, available_dm_kg_ha,
                    utilization_pct, calculated_usable_dm_kg, notes, display_order)
                   VALUES (%(sid)s, %(name)s, %(area_ha)s, %(available_dm_kg_ha)s,
                           %(utilization_pct)s, %(calculated_usable_dm_kg)s,
                           %(notes)s, %(display_order)s)""",
                {**item, "sid": scenario_id, "display_order": item.get("display_order", i)},
            )

    def _insert_feed(self, cur, scenario_id: int, items: list[dict]) -> None:
        for i, item in enumerate(items):
            cur.execute(
                """INSERT INTO nutrition.food_autonomy_feed_items
                   (scenario_id, feed_type, name, quantity_natural_kg,
                    dry_matter_pct, utilization_pct, calculated_usable_dm_kg,
                    notes, display_order)
                   VALUES (%(sid)s, %(feed_type)s, %(name)s, %(quantity_natural_kg)s,
                           %(dry_matter_pct)s, %(utilization_pct)s,
                           %(calculated_usable_dm_kg)s, %(notes)s, %(display_order)s)""",
                {**item, "sid": scenario_id, "display_order": item.get("display_order", i)},
            )
