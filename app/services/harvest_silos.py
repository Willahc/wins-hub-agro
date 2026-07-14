"""Aplicação do módulo Colheita e Silos."""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from uuid import UUID, uuid4

from core.authorization import AuthorizationContext, AuthorizationService, ForbiddenError, HiddenResourceError
from core.permissions import ORGANIZATION_WIDE_FARM_ROLES, Permission, Role
from domain.foundation import RecordStatus
from domain.harvest_silos import (
    RULE_VERSION, VALID_CROPS, VALID_PURPOSES, VALID_STATUSES,
    calculate_dm_kg, calculate_gross_natural, calculate_net_natural,
    calculate_occupancy_pct, calculate_projected_occupancy,
    calculate_variation, determine_capacity_status,
)
from domain.feed_inventory import (
    FORMULA_VERSION as FEED_RULE_VERSION, FEED_TYPES,
    calculate_physical_dm, calculate_usable_dm,
)


class ConflictError(Exception):
    code = "conflict"


class ValidationError(Exception):
    code = "validation_error"


class HarvestSilosService:
    def __init__(self, repository, auth_repository=None):
        self.repository = repository
        self.auth_repository = auth_repository or repository

    def _context(self, subject, farm_public_id, request_id):
        auth = AuthorizationService(self.auth_repository)
        user = auth.require_authenticated_user(subject)
        farm = self.repository.find_farm(farm_public_id)
        if not farm:
            raise HiddenResourceError()
        membership = self.repository.find_membership(user.id, farm["organization_id"])
        if not membership or membership["status"] != RecordStatus.ACTIVE.value:
            raise ForbiddenError("membership_missing")
        role = Role(membership["role"])
        ctx = AuthorizationContext(
            user_id=user.id, user_public_id=user.public_id,
            organization_id=farm["organization_id"],
            organization_public_id=UUID("00000000-0000-0000-0000-000000000000"),
            membership_id=membership["id"], membership_public_id=UUID(membership["public_id"]),
            role=role, request_id=request_id, source="web",
            authenticated_at=datetime.now(timezone.utc), farm_id=farm["id"],
            farm_public_id=farm_public_id,
        )
        auth.require_organization_role(ctx, Permission.FARM_READ)
        if role not in ORGANIZATION_WIDE_FARM_ROLES and not self.repository.find_farm_access(membership["id"], farm["id"]):
            raise ForbiddenError("farm_not_assigned")
        return ctx, farm, auth

    @staticmethod
    def _decimal(value, field):
        try:
            result = Decimal(str(value))
        except (InvalidOperation, TypeError):
            raise ValidationError(f"invalid_{field}")
        if not result.is_finite():
            raise ValidationError(f"invalid_{field}")
        return result

    def _plan_response(self, plan):
        areas = self.repository.get_plan_areas(plan["id"])
        allocations = self.repository.get_plan_allocations(plan["id"])
        def iso(v): return v.isoformat() if hasattr(v, "isoformat") else str(v) if v is not None else None
        return {
            "public_id": str(plan["public_id"]), "name": plan["name"],
            "main_crop": plan["main_crop"], "purpose": plan["purpose"],
            "expected_start_date": iso(plan["expected_start_date"]), "expected_end_date": iso(plan["expected_end_date"]),
            "expected_field_loss_pct": str(plan["expected_field_loss_pct"]),
            "expected_ensiling_loss_pct": str(plan["expected_ensiling_loss_pct"]),
            "expected_gross_natural_kg": str(plan["expected_gross_natural_kg"]),
            "expected_net_natural_kg": str(plan["expected_net_natural_kg"]), "expected_dm_kg": str(plan["expected_dm_kg"]),
            "actual_start_date": iso(plan.get("actual_start_date")), "actual_end_date": iso(plan.get("actual_end_date")),
            "actual_natural_kg": str(plan["actual_natural_kg"]) if plan.get("actual_natural_kg") is not None else None,
            "actual_dm_pct": str(plan["actual_dm_pct"]) if plan.get("actual_dm_pct") is not None else None,
            "actual_loss_pct": str(plan["actual_loss_pct"]) if plan.get("actual_loss_pct") is not None else None,
            "status": plan["status"], "notes": plan.get("notes", ""), "rule_version": plan.get("rule_version", RULE_VERSION),
            "completed_at": iso(plan.get("completed_at")), "created_at": iso(plan["created_at"]), "updated_at": iso(plan["updated_at"]),
            "areas": [{
                "public_id": str(a["public_id"]), "name": a["name"], "crop": a["crop"], "cultivar": a.get("cultivar", ""),
                "area_ha": str(a["area_ha"]), "expected_yield_t_ha": str(a["expected_yield_t_ha"]),
                "expected_dm_pct": str(a["expected_dm_pct"]), "expected_harvest_date": iso(a.get("expected_harvest_date")),
                "calculated_gross_natural_kg": str(a["calculated_gross_natural_kg"]),
                "calculated_net_natural_kg": str(a["calculated_net_natural_kg"]), "calculated_dm_kg": str(a["calculated_dm_kg"]),
                "notes": a.get("notes", "")
            } for a in areas],
            "allocations": [self._allocation_response(a) for a in allocations],
        }

    @staticmethod
    def _allocation_response(a):
        return {"public_id": str(a["public_id"]), "facility_uuid": str(a["facility_uuid"]),
                "facility_name": a.get("facility_name", ""),
                "expected_quantity_natural_kg": str(a["expected_quantity_natural_kg"]),
                "actual_quantity_natural_kg": str(a["actual_quantity_natural_kg"]) if a.get("actual_quantity_natural_kg") is not None else None,
                "expected_percentage": str(a["expected_percentage"]),
                "capacity_snapshot_kg": str(a["capacity_snapshot_kg"]) if a.get("capacity_snapshot_kg") is not None else None,
                "current_stock_snapshot_kg": str(a["current_stock_snapshot_kg"]) if a.get("current_stock_snapshot_kg") is not None else None,
                "projected_occupancy_kg": str(a["projected_occupancy_kg"]) if a.get("projected_occupancy_kg") is not None else None,
                "projected_occupancy_pct": str(a["projected_occupancy_pct"]) if a.get("projected_occupancy_pct") is not None else None,
                "capacity_status": a["capacity_status"],
                "created_feed_lot_uuid": str(a["created_feed_lot_uuid"]) if a.get("created_feed_lot_uuid") else None}

    def _prepare(self, payload, farm, ctx, public_id=None):
        if payload["main_crop"] not in VALID_CROPS or payload["purpose"] not in VALID_PURPOSES:
            raise ValidationError("invalid_crop_or_purpose")
        if payload["expected_end_date"] < payload["expected_start_date"] or not payload.get("areas"):
            raise ValidationError("invalid_dates_or_areas")
        field_loss = self._decimal(payload["expected_field_loss_pct"], "field_loss")
        ensiling_loss = self._decimal(payload["expected_ensiling_loss_pct"], "ensiling_loss")
        areas, gross, net, dm = [], Decimal("0"), Decimal("0"), Decimal("0")
        for index, item in enumerate(payload["areas"]):
            area = self._decimal(item["area_ha"], "area")
            yield_value = self._decimal(item["expected_yield_t_ha"], "yield")
            dm_pct = self._decimal(item["expected_dm_pct"], "dm_pct")
            ag = calculate_gross_natural(area, yield_value)
            an = calculate_net_natural(ag, field_loss, ensiling_loss)
            ad = calculate_dm_kg(an, dm_pct)
            gross += ag; net += an; dm += ad
            areas.append({**item, "public_id": uuid4(), "area_ha": area, "expected_yield_t_ha": yield_value,
                          "expected_dm_pct": dm_pct, "calculated_gross_natural_kg": ag,
                          "calculated_net_natural_kg": an, "calculated_dm_kg": ad, "display_order": index})
        allocations = []
        allocated = Decimal("0")
        for item in payload.get("allocations", []):
            facility = self.repository.get_facility_by_uuid(item["facility_uuid"])
            if not facility or facility["farm_id"] != farm["id"]:
                raise HiddenResourceError()
            quantity = self._decimal(item["expected_natural_kg"], "allocation")
            percentage = self._decimal(item["percentage"], "percentage")
            capacity, stock = self.repository.get_facility_capacity_and_stock(facility["id"])
            projected = calculate_projected_occupancy(stock, quantity)
            occupancy_pct = calculate_occupancy_pct(projected, capacity)
            allocations.append({"public_id": uuid4(), "facility_id": facility["id"], "expected_natural_kg": quantity,
                "percentage": percentage, "capacity_snapshot_kg": capacity, "current_stock_snapshot_kg": stock,
                "projected_occupancy_kg": projected, "projected_occupancy_pct": occupancy_pct,
                "capacity_status": determine_capacity_status(occupancy_pct)})
            allocated += quantity
        if allocations and allocated != net:
            raise ValidationError("allocation_sum_must_equal_expected_net")
        plan = {"public_id": public_id or uuid4(), "organization_id": ctx.organization_id, "farm_id": farm["id"],
                "name": payload["name"].strip(), "main_crop": payload["main_crop"], "purpose": payload["purpose"],
                "expected_start_date": payload["expected_start_date"], "expected_end_date": payload["expected_end_date"],
                "expected_field_loss_pct": field_loss, "expected_ensiling_loss_pct": ensiling_loss,
                "expected_gross_natural_kg": gross, "expected_net_natural_kg": net, "expected_dm_kg": dm,
                "status": "planned", "notes": payload.get("notes", ""), "created_by_user_id": ctx.user_id,
                "request_id": ctx.request_id}
        return plan, areas, allocations

    def simulate(self, *, subject, farm_public_id, payload, request_id):
        ctx, farm, _ = self._context(subject, farm_public_id, request_id)
        plan, areas, allocations = self._prepare(payload, farm, ctx)
        return {"expected_gross_natural_kg": str(plan["expected_gross_natural_kg"]),
                "expected_net_natural_kg": str(plan["expected_net_natural_kg"]), "expected_dm_kg": str(plan["expected_dm_kg"]),
                "allocations": [self._allocation_response({**a, "facility_uuid": self.repository.get_facility_by_id(a["facility_id"])["public_id"],
                    "facility_name": self.repository.get_facility_by_id(a["facility_id"])["name"],
                    "expected_quantity_natural_kg": a["expected_natural_kg"], "expected_percentage": a["percentage"]}) for a in allocations]}

    def create_plan(self, *, subject, farm_public_id, payload, request_id):
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        auth.require_organization_role(ctx, Permission.FARM_OPERATE)
        plan, areas, allocations = self._prepare(payload, farm, ctx)
        created = self.repository.create_plan(plan, areas, allocations)
        return self._plan_response(self.repository.get_plan_by_id(created["id"]))

    def get_plan(self, *, subject, farm_public_id, plan_public_id, request_id):
        _, farm, _ = self._context(subject, farm_public_id, request_id)
        plan = self.repository.get_plan(plan_public_id)
        if not plan or plan["farm_id"] != farm["id"]:
            raise HiddenResourceError()
        return self._plan_response(plan)

    def list_plans(self, *, subject, farm_public_id, request_id, limit=25, offset=0, status=None, crop=None, start_date=None, end_date=None, search=None):
        _, farm, _ = self._context(subject, farm_public_id, request_id)
        if status and status not in VALID_STATUSES: raise ValidationError("invalid_status")
        items = self.repository.list_plans(farm["id"], limit, offset, status, crop, start_date, end_date, search)
        return {"items": [self._plan_response(p) for p in items],
                "total": self.repository.count_plans(farm["id"], status, crop, start_date, end_date, search)}

    def update_plan(self, *, subject, farm_public_id, plan_public_id, payload, request_id):
        ctx, farm, auth = self._context(subject, farm_public_id, request_id); auth.require_organization_role(ctx, Permission.FARM_OPERATE)
        old = self.repository.get_plan(plan_public_id)
        if not old or old["farm_id"] != farm["id"]: raise HiddenResourceError()
        if old["status"] == "completed": raise ConflictError("completed_plan_is_immutable")
        plan, areas, allocations = self._prepare(payload, farm, ctx, old["public_id"])
        self.repository.update_plan(old["id"], plan, areas, allocations)
        return self._plan_response(self.repository.get_plan_by_id(old["id"]))

    def archive_plan(self, *, subject, farm_public_id, plan_public_id, request_id):
        ctx, farm, auth = self._context(subject, farm_public_id, request_id); auth.require_organization_role(ctx, Permission.FARM_OPERATE)
        plan = self.repository.get_plan(plan_public_id)
        if not plan or plan["farm_id"] != farm["id"]: raise HiddenResourceError()
        if plan["status"] == "completed": raise ConflictError("completed_plan_cannot_be_archived")
        self.repository.archive_plan(plan["id"], request_id, ctx.user_id)

    def start_plan(self, *, subject, farm_public_id, plan_public_id, actual_start_date, request_id):
        ctx, farm, auth = self._context(subject, farm_public_id, request_id); auth.require_organization_role(ctx, Permission.FARM_OPERATE)
        plan = self.repository.get_plan(plan_public_id)
        if not plan or plan["farm_id"] != farm["id"]: raise HiddenResourceError()
        if plan["status"] not in ("draft", "planned"): raise ConflictError("invalid_plan_transition")
        self.repository.start_plan(plan["id"], actual_start_date, request_id, ctx.user_id)
        return self._plan_response(self.repository.get_plan_by_id(plan["id"]))

    def complete_plan(self, *, subject, farm_public_id, plan_public_id, payload, request_id):
        ctx, farm, auth = self._context(subject, farm_public_id, request_id); auth.require_organization_role(ctx, Permission.FARM_OPERATE)
        plan = self.repository.get_plan(plan_public_id)
        if not plan or plan["farm_id"] != farm["id"]: raise HiddenResourceError()
        effective_request_id = payload.get("request_id") or request_id
        def normalized(value):
            if isinstance(value, (date, datetime)): return value.isoformat()
            if isinstance(value, UUID): return str(value)
            return value
        payload_hash = hashlib.sha256(json.dumps(payload, default=normalized, sort_keys=True,
                                                  separators=(",", ":")).encode()).hexdigest()
        if plan["status"] == "completed":
            if plan.get("completion_request_id") == effective_request_id:
                if plan.get("completion_payload_hash") == payload_hash: return self._plan_response(plan)
                raise ConflictError("request_id_payload_conflict")
            raise ConflictError("plan_already_completed")
        if plan["status"] != "in_progress":
            raise ConflictError("plan_must_be_in_progress")
        actual = self._decimal(payload["actual_natural_kg"], "actual_natural")
        dm_pct = self._decimal(payload["actual_dm_pct"], "actual_dm")
        loss_pct = self._decimal(payload["actual_loss_pct"], "actual_loss")
        if payload["actual_end_date"] < payload["actual_start_date"] or not (0 <= dm_pct <= 100) or not (0 <= loss_pct <= 100):
            raise ValidationError("invalid_completion")
        allocations, lots, movements, total = [], [], [], Decimal("0")
        existing = {str(a["facility_uuid"]): a for a in self.repository.get_plan_allocations(plan["id"])}
        for item in payload.get("allocations", []):
            facility = self.repository.get_facility_by_uuid(item["facility_uuid"])
            alloc = existing.get(str(item["facility_uuid"]))
            if not facility or facility["farm_id"] != farm["id"] or not alloc: raise HiddenResourceError()
            qty = self._decimal(item["actual_natural_kg"], "allocation")
            capacity, stock = self.repository.get_facility_capacity_and_stock(facility["id"])
            if capacity is not None and stock + qty > capacity: raise ConflictError("facility_over_capacity")
            if item["feed_type"] not in FEED_TYPES: raise ValidationError("invalid_feed_type")
            utilization = self._decimal(item.get("utilization_pct", "100"), "utilization")
            lot_id, movement_id = uuid4(), uuid4(); total += qty
            physical = calculate_physical_dm(qty, dm_pct); usable = calculate_usable_dm(physical, utilization)
            cost = self._decimal(item["cost"], "cost") if item.get("cost") is not None else None
            lots.append({"public_id": lot_id, "organization_id": ctx.organization_id, "farm_id": farm["id"], "facility_id": facility["id"],
                "name": item["lot_name"], "feed_type": item["feed_type"], "custom_feed_type": "", "production_date": payload["actual_end_date"],
                "ensiling_date": payload["actual_end_date"], "opened_at": None, "source_description": "Colheita e Silos",
                "initial_quantity_natural_kg": qty, "current_quantity_natural_kg": qty, "dry_matter_pct": dm_pct,
                "utilization_pct": utilization, "current_physical_dm_kg": physical, "current_usable_dm_kg": usable,
                "initial_total_cost": cost, "average_cost_per_natural_kg": (cost / qty if cost is not None and qty else None),
                "current_inventory_value": cost if cost is not None else Decimal("0"),
                "cost_per_usable_dm_kg": (cost / usable if cost is not None and usable else None),
                "planned_daily_use_dm_kg": None, "status": "available", "rule_version": FEED_RULE_VERSION,
                "notes": f"Origem: Colheita e Silos — plano {plan['public_id']}. {item.get('notes', '')}".strip(), "created_by_user_id": ctx.user_id})
            movements.append({"public_id": movement_id, "organization_id": ctx.organization_id, "farm_id": farm["id"],
                "movement_type": "initial_balance", "movement_at": datetime.now(timezone.utc), "quantity_natural_kg": qty,
                "dry_matter_pct_snapshot": dm_pct, "utilization_pct_snapshot": utilization, "physical_dm_kg": physical,
                "usable_dm_kg": usable, "unit_cost_snapshot": (cost / qty if cost is not None and qty else None), "total_cost": cost,
                "loss_reason": "", "reason": "Colheita concluída", "notes": item.get("notes", ""),
                "request_id": f"{effective_request_id}:{lot_id}", "created_by_user_id": ctx.user_id})
            allocations.append({"public_id": alloc["public_id"], "facility_id": facility["id"], "actual_natural_kg": qty})
        if total != actual: raise ValidationError("allocation_sum_must_equal_actual")
        self.repository.complete_plan_and_create_lots(plan["id"], payload["actual_start_date"], payload["actual_end_date"],
            actual, dm_pct, loss_pct, allocations, lots, movements, effective_request_id, payload_hash, ctx.user_id)
        return self._plan_response(self.repository.get_plan_by_id(plan["id"]))

    def get_dashboard(self, *, subject, farm_public_id, request_id):
        _, farm, _ = self._context(subject, farm_public_id, request_id)
        result = self.repository.get_dashboard(farm["id"])
        for key in ("planned_area_ha", "expected_gross_natural_kg", "expected_net_natural_kg",
                    "expected_dm_kg", "capacity_needed_kg", "capacity_available_kg"):
            result[key] = str(result.get(key, 0))
        return result
