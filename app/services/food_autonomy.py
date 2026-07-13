"""Serviço de Autonomia Alimentar — orquestra autorização, cálculo e persistência."""
import logging
from uuid import UUID, uuid4

from core.authorization import AuthorizationService, ForbiddenError, HiddenResourceError
from core.permissions import Permission, ORGANIZATION_WIDE_FARM_ROLES
from domain.food_autonomy import (
    FORMULA_VERSION, HerdItem, PastureItem, FeedItem,
    SimulationInput, SimulationResult, calculate_autonomy,
)
from decimal import Decimal

logger = logging.getLogger("wins_agro.food_autonomy")


class FoodAutonomyService:
    def __init__(self, repository, auth_repository=None):
        self.repository = repository
        self.auth_repository = auth_repository or repository

    def _resolve_farm_context(self, subject, farm_public_id, request_id, source="web"):
        auth_service = AuthorizationService(self.auth_repository)
        user = auth_service.require_authenticated_user(subject)

        farm = self.repository.find_farm(farm_public_id)
        if farm is None:
            raise HiddenResourceError()

        membership = self.repository.find_membership(user.id, farm["organization_id"])
        if membership is None:
            auth_service._deny("membership_missing", user_id=user.id,
                               organization_id=str(farm["organization_id"]))
            raise ForbiddenError("membership_missing")

        from domain.foundation import RecordStatus
        if membership["status"] != RecordStatus.ACTIVE.value:
            raise ForbiddenError("membership_inactive")

        from core.permissions import Role
        role = Role(membership["role"])
        context_org_id = farm["organization_id"]

        from core.authorization import AuthorizationContext
        from datetime import datetime, timezone
        ctx = AuthorizationContext(
            user_id=user.id,
            user_public_id=user.public_id,
            organization_id=context_org_id,
            organization_public_id=UUID("00000000-0000-0000-0000-000000000000"),
            membership_id=membership["id"],
            membership_public_id=UUID(membership["public_id"]),
            role=role,
            request_id=request_id,
            source=source,
            authenticated_at=datetime.now(timezone.utc),
            farm_id=farm["id"],
            farm_public_id=farm_public_id,
        )

        if farm["organization_id"] != context_org_id:
            raise HiddenResourceError()

        auth_service.require_organization_role(ctx, Permission.FARM_READ)

        if role not in ORGANIZATION_WIDE_FARM_ROLES:
            access = self.repository.find_farm_access(membership["id"], farm["id"])
            if access is None:
                raise ForbiddenError("farm_not_assigned")

        return ctx, farm

    def simulate(self, *, subject, farm_public_id, payload, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        inp = self._build_input(payload)
        result = calculate_autonomy(inp)

        return self._result_to_dict(result)

    def create_scenario(self, *, subject, farm_public_id, payload, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        auth_service.require_organization_role(ctx, Permission.FARM_OPERATE)

        inp = self._build_input(payload)
        result = calculate_autonomy(inp)

        public_id = uuid4()
        data = self._build_scenario_data(
            public_id, ctx, farm, inp, result, request_id
        )
        herd_dicts = [self._herd_to_dict(h, i) for i, h in enumerate(inp.herd)]
        pasture_dicts = [self._pasture_to_dict(p, i) for i, p in enumerate(inp.pastures)]
        feed_dicts = [self._feed_to_dict(f, i) for i, f in enumerate(inp.feeds)]

        created = self.repository.create_scenario(
            data, herd_dicts, pasture_dicts, feed_dicts, ctx.user_id
        )

        scenario = self.repository.get_scenario(created["public_id"])
        return self._scenario_response(scenario)

    def list_scenarios(self, *, subject, farm_public_id, limit, offset,
                       status_filter, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        total = self.repository.count_scenarios(farm["id"])
        items = self.repository.list_scenarios(
            farm["id"], limit=limit, offset=offset, status_filter=status_filter
        )

        return {
            "items": [self._scenario_summary(s) for s in items],
            "pagination": {
                "limit": limit, "offset": offset,
                "returned": len(items), "total": total,
                "has_more": offset + len(items) < total,
            },
        }

    def get_scenario(self, *, subject, farm_public_id, scenario_uuid, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        scenario = self.repository.get_scenario(scenario_uuid)
        if scenario is None or scenario["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        return self._scenario_response(scenario)

    def update_scenario(self, *, subject, farm_public_id, scenario_uuid, payload,
                        request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        auth_service.require_organization_role(ctx, Permission.FARM_OPERATE)

        scenario = self.repository.get_scenario(scenario_uuid)
        if scenario is None or scenario["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        inp = self._build_input(payload)
        result = calculate_autonomy(inp)

        data = self._build_scenario_data(
            scenario["public_id"], ctx, farm, inp, result, request_id
        )
        herd_dicts = [self._herd_to_dict(h, i) for i, h in enumerate(inp.herd)]
        pasture_dicts = [self._pasture_to_dict(p, i) for i, p in enumerate(inp.pastures)]
        feed_dicts = [self._feed_to_dict(f, i) for i, f in enumerate(inp.feeds)]

        self.repository.update_scenario(
            scenario["id"], data, herd_dicts, pasture_dicts, feed_dicts, ctx.user_id
        )

        updated = self.repository.get_scenario(scenario_uuid)
        return self._scenario_response(updated)

    def archive_scenario(self, *, subject, farm_public_id, scenario_uuid, request_id) -> None:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        auth_service.require_organization_role(ctx, Permission.FARM_OPERATE)

        scenario = self.repository.get_scenario(scenario_uuid)
        if scenario is None or scenario["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        self.repository.archive_scenario(
            scenario["id"], ctx.user_id, ctx.organization_id,
            farm["id"], scenario["public_id"],
        )

    def _build_input(self, payload: dict) -> SimulationInput:
        ref_date = payload["reference_date"]
        if isinstance(ref_date, str):
            from datetime import date as _date
            ref_date = _date.fromisoformat(ref_date)
        herd = []
        for h in payload.get("herd", []):
            herd.append(HerdItem(
                category=h["category"],
                head_count=int(h["head_count"]),
                average_weight_kg=Decimal(str(h["average_weight_kg"])),
                intake_pct_body_weight=Decimal(str(h["intake_pct_body_weight"])),
                custom_category_name=h.get("custom_category_name", ""),
            ))
        pastures = []
        for p in payload.get("pastures", []):
            pastures.append(PastureItem(
                name=p["name"],
                area_ha=Decimal(str(p["area_ha"])),
                available_dm_kg_ha=Decimal(str(p["available_dm_kg_ha"])),
                utilization_pct=Decimal(str(p.get("utilization_pct", 50))),
                notes=p.get("notes", ""),
            ))
        feeds = []
        for f in payload.get("feeds", []):
            feeds.append(FeedItem(
                feed_type=f["feed_type"],
                name=f["name"],
                quantity_natural_kg=Decimal(str(f["quantity_natural_kg"])),
                dry_matter_pct=Decimal(str(f["dry_matter_pct"])),
                utilization_pct=Decimal(str(f.get("utilization_pct", 100))),
                notes=f.get("notes", ""),
            ))

        return SimulationInput(
            name=payload.get("name", "Cenário"),
            reference_date=ref_date,
            target_days=int(payload.get("target_days", 90)),
            safety_margin_pct=Decimal(str(payload.get("safety_margin_pct", 0))),
            herd=tuple(herd),
            pastures=tuple(pastures),
            feeds=tuple(feeds),
            notes=payload.get("notes", ""),
        )

    def _build_scenario_data(self, public_id, ctx, farm, inp, result, request_id):
        return {
            "public_id": public_id,
            "organization_id": ctx.organization_id,
            "farm_id": farm["id"],
            "name": inp.name,
            "reference_date": inp.reference_date,
            "target_days": inp.target_days,
            "safety_margin_pct": inp.safety_margin_pct,
            "total_daily_demand_dm_kg": result.daily_demand_dm_kg,
            "total_pasture_dm_kg": result.pasture_usable_dm_kg,
            "total_stored_feed_dm_kg": result.stored_feed_usable_dm_kg,
            "total_physical_dm_kg": result.physical_total_dm_kg,
            "reserve_dm_kg": result.reserve_dm_kg,
            "planning_available_dm_kg": result.planning_available_dm_kg,
            "autonomy_days": result.autonomy_days,
            "target_required_dm_kg": result.target_required_dm_kg,
            "balance_dm_kg": result.balance_dm_kg,
            "balance_days": result.balance_days,
            "status": result.status.value,
            "estimated_end_date": result.estimated_end_date,
            "formula_version": result.formula_version,
            "notes": inp.notes,
            "created_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

    def _herd_to_dict(self, h: HerdItem, order: int) -> dict:
        return {
            "category": h.category,
            "custom_category_name": h.custom_category_name,
            "head_count": h.head_count,
            "average_weight_kg": h.average_weight_kg,
            "intake_pct_body_weight": h.intake_pct_body_weight,
            "calculated_daily_demand_dm_kg": h.daily_demand_dm_kg(),
            "display_order": order,
        }

    def _pasture_to_dict(self, p: PastureItem, order: int) -> dict:
        return {
            "name": p.name,
            "area_ha": p.area_ha,
            "available_dm_kg_ha": p.available_dm_kg_ha,
            "utilization_pct": p.utilization_pct,
            "calculated_usable_dm_kg": p.usable_dm_kg(),
            "notes": p.notes,
            "display_order": order,
        }

    def _feed_to_dict(self, f: FeedItem, order: int) -> dict:
        return {
            "feed_type": f.feed_type,
            "name": f.name,
            "quantity_natural_kg": f.quantity_natural_kg,
            "dry_matter_pct": f.dry_matter_pct,
            "utilization_pct": f.utilization_pct,
            "calculated_usable_dm_kg": f.usable_dm_kg(),
            "notes": f.notes,
            "display_order": order,
        }

    def _result_to_dict(self, r: SimulationResult) -> dict:
        return {
            "formula_version": r.formula_version,
            "daily_demand_dm_kg": str(r.daily_demand_dm_kg),
            "pasture_usable_dm_kg": str(r.pasture_usable_dm_kg),
            "stored_feed_usable_dm_kg": str(r.stored_feed_usable_dm_kg),
            "physical_total_dm_kg": str(r.physical_total_dm_kg),
            "reserve_dm_kg": str(r.reserve_dm_kg),
            "planning_available_dm_kg": str(r.planning_available_dm_kg),
            "autonomy_days": str(r.autonomy_days),
            "target_days": r.target_days,
            "target_required_dm_kg": str(r.target_required_dm_kg),
            "balance_dm_kg": str(r.balance_dm_kg),
            "balance_days": str(r.balance_days),
            "status": r.status.value,
            "estimated_end_date": r.estimated_end_date.isoformat() if r.estimated_end_date else None,
            "warnings": list(r.warnings),
        }

    def _scenario_summary(self, s: dict) -> dict:
        return {
            "public_id": s["public_id"],
            "name": s["name"],
            "reference_date": s["reference_date"].isoformat() if hasattr(s["reference_date"], "isoformat") else str(s["reference_date"]),
            "target_days": s["target_days"],
            "status": s["status"],
            "autonomy_days": str(s["autonomy_days"]),
            "formula_version": s["formula_version"],
            "created_at": s["created_at"].isoformat() if hasattr(s["created_at"], "isoformat") else str(s["created_at"]),
        }

    def _scenario_response(self, s: dict) -> dict:
        return {
            "public_id": s["public_id"],
            "name": s["name"],
            "reference_date": s["reference_date"].isoformat() if hasattr(s["reference_date"], "isoformat") else str(s["reference_date"]),
            "target_days": s["target_days"],
            "safety_margin_pct": str(s["safety_margin_pct"]),
            "total_daily_demand_dm_kg": str(s["total_daily_demand_dm_kg"]),
            "total_pasture_dm_kg": str(s["total_pasture_dm_kg"]),
            "total_stored_feed_dm_kg": str(s["total_stored_feed_dm_kg"]),
            "total_physical_dm_kg": str(s["total_physical_dm_kg"]),
            "reserve_dm_kg": str(s["reserve_dm_kg"]),
            "planning_available_dm_kg": str(s["planning_available_dm_kg"]),
            "autonomy_days": str(s["autonomy_days"]),
            "target_required_dm_kg": str(s["target_required_dm_kg"]),
            "balance_dm_kg": str(s["balance_dm_kg"]),
            "balance_days": str(s["balance_days"]),
            "status": s["status"],
            "estimated_end_date": s["estimated_end_date"].isoformat() if s.get("estimated_end_date") and hasattr(s["estimated_end_date"], "isoformat") else str(s["estimated_end_date"]) if s.get("estimated_end_date") else None,
            "formula_version": s["formula_version"],
            "notes": s.get("notes", ""),
            "herd": [
                {
                    "category": h["category"],
                    "custom_category_name": h.get("custom_category_name", ""),
                    "head_count": h["head_count"],
                    "average_weight_kg": str(h["average_weight_kg"]),
                    "intake_pct_body_weight": str(h["intake_pct_body_weight"]),
                    "calculated_daily_demand_dm_kg": str(h["calculated_daily_demand_dm_kg"]),
                }
                for h in s.get("herd_items", [])
            ],
            "pastures": [
                {
                    "name": p["name"],
                    "area_ha": str(p["area_ha"]),
                    "available_dm_kg_ha": str(p["available_dm_kg_ha"]),
                    "utilization_pct": str(p["utilization_pct"]),
                    "calculated_usable_dm_kg": str(p["calculated_usable_dm_kg"]),
                    "notes": p.get("notes", ""),
                }
                for p in s.get("pasture_items", [])
            ],
            "feeds": [
                {
                    "feed_type": f["feed_type"],
                    "name": f["name"],
                    "quantity_natural_kg": str(f["quantity_natural_kg"]),
                    "dry_matter_pct": str(f["dry_matter_pct"]),
                    "utilization_pct": str(f["utilization_pct"]),
                    "calculated_usable_dm_kg": str(f["calculated_usable_dm_kg"]),
                    "notes": f.get("notes", ""),
                }
                for f in s.get("feed_items", [])
            ],
            "created_at": s["created_at"].isoformat() if hasattr(s["created_at"], "isoformat") else str(s["created_at"]),
            "updated_at": s["updated_at"].isoformat() if hasattr(s["updated_at"], "isoformat") else str(s["updated_at"]),
        }
