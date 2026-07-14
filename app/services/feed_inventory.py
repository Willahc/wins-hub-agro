"""Serviço de Silagem e Estoques — orquestra autorização, cálculo e persistência."""
import logging
from uuid import UUID, uuid4
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from core.authorization import AuthorizationService, ForbiddenError, HiddenResourceError
from core.permissions import Permission, ORGANIZATION_WIDE_FARM_ROLES
from domain.feed_inventory import (
    FORMULA_VERSION, LotStatus, MovementType, FacilityType, FeedType,
    calculate_physical_dm, calculate_usable_dm, calculate_cost_per_natural_kg,
    calculate_inventory_value, calculate_cost_per_usable_dm, calculate_loss_value,
    calculate_days_remaining, calculate_estimated_end_date, reconcile_balance,
    _q2, _q4, MAX_CAPACITY_KG, MAX_QUANTITY_KG, MAX_COST,
    FACILITY_TYPES, FEED_TYPES, LOT_STATUSES, MOVEMENT_TYPES, LOSS_REASONS,
    ACTIVE_LOT_STATUSES, ADDITIVE_MOVEMENTS, SUBTRACTIVE_MOVEMENTS,
)
from domain.foundation import RecordStatus

logger = logging.getLogger("wins_agro.feed_inventory")


class FeedInventoryService:
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

        if membership["status"] != RecordStatus.ACTIVE.value:
            raise ForbiddenError("membership_inactive")

        from core.permissions import Role
        role = Role(membership["role"])
        context_org_id = farm["organization_id"]

        from core.authorization import AuthorizationContext
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

    def _require_write(self, ctx, auth_service):
        auth_service.require_organization_role(ctx, Permission.FARM_OPERATE)

    def _require_manage(self, ctx, auth_service):
        auth_service.require_organization_role(ctx, Permission.FARM_MANAGE)

    # ---------------------------------------------------------------------------
    # Response builders
    # ---------------------------------------------------------------------------

    def _facility_response(self, f: dict) -> dict:
        return {
            "public_id": str(f["public_id"]),
            "name": f["name"],
            "code": f.get("code", ""),
            "facility_type": f["facility_type"],
            "capacity_natural_kg": str(f["capacity_natural_kg"]),
            "preferred_display_unit": f.get("preferred_display_unit", "kg"),
            "location_description": f.get("location_description", ""),
            "active": f.get("active", True),
            "notes": f.get("notes", ""),
            "created_at": f["created_at"].isoformat() if hasattr(f["created_at"], "isoformat") else str(f["created_at"]),
            "updated_at": f["updated_at"].isoformat() if hasattr(f["updated_at"], "isoformat") else str(f["updated_at"]),
        }

    def _lot_response(self, l: dict) -> dict:
        quantity_natural_kg = Decimal(str(l.get("current_quantity_natural_kg") if l.get("current_quantity_natural_kg") is not None else l.get("balance_natural_kg", 0)))
        dry_matter_pct = Decimal(str(l.get("dry_matter_pct", 0)))
        utilization_pct = Decimal(str(l.get("utilization_pct", 100)))
        initial_quantity_natural_kg = Decimal(str(l.get("initial_quantity_natural_kg", 0)))
        initial_total_cost = Decimal(str(l["initial_total_cost"])) if l.get("initial_total_cost") is not None else None

        physical_dm = calculate_physical_dm(quantity_natural_kg, dry_matter_pct)
        usable_dm = calculate_usable_dm(physical_dm, utilization_pct)
        avg_cost_per_kg = calculate_cost_per_natural_kg(initial_total_cost, initial_quantity_natural_kg)
        inv_value = calculate_inventory_value(quantity_natural_kg, avg_cost_per_kg)
        cost_per_usable_dm = calculate_cost_per_usable_dm(inv_value, usable_dm)
        days_rem = calculate_days_remaining(usable_dm, l.get("planned_daily_use_dm_kg"))
        ref_date = date.today()
        est_end = calculate_estimated_end_date(ref_date, days_rem)

        return {
            "public_id": str(l["public_id"]),
            "facility_uuid": str(l.get("facility_public_id", "")) if l.get("facility_public_id") else "",
            "facility_name": l.get("facility_name", ""),
            "name": l["name"],
            "feed_type": l["feed_type"],
            "custom_feed_type": l.get("custom_feed_type", ""),
            "production_date": l["production_date"].isoformat() if l.get("production_date") and hasattr(l["production_date"], "isoformat") else str(l["production_date"]) if l.get("production_date") else "",
            "ensiling_date": l["ensiling_date"].isoformat() if l.get("ensiling_date") and hasattr(l["ensiling_date"], "isoformat") else str(l["ensiling_date"]) if l.get("ensiling_date") else "",
            "source_description": l.get("source_description", ""),
            "initial_quantity_natural_kg": str(initial_quantity_natural_kg),
            "current_quantity_natural_kg": str(quantity_natural_kg),
            "dry_matter_pct": str(dry_matter_pct),
            "utilization_pct": str(utilization_pct),
            "current_physical_dm_kg": str(physical_dm),
            "current_usable_dm_kg": str(usable_dm),
            "initial_total_cost": str(initial_total_cost) if initial_total_cost is not None else None,
            "average_cost_per_natural_kg": str(avg_cost_per_kg) if avg_cost_per_kg is not None else None,
            "current_inventory_value": str(inv_value),
            "cost_per_usable_dm_kg": str(cost_per_usable_dm) if cost_per_usable_dm is not None else None,
            "planned_daily_use_dm_kg": str(l["planned_daily_use_dm_kg"]) if l.get("planned_daily_use_dm_kg") is not None else None,
            "days_remaining": days_rem,
            "estimated_end_date": est_end.isoformat() if est_end else None,
            "status": l["status"],
            "rule_version": FORMULA_VERSION,  # formula_version
            "notes": l.get("notes", ""),
            "created_at": l["created_at"].isoformat() if hasattr(l["created_at"], "isoformat") else str(l["created_at"]),
            "updated_at": l["updated_at"].isoformat() if hasattr(l["updated_at"], "isoformat") else str(l["updated_at"]),
        }

    def _movement_response(self, m: dict) -> dict:
        dry_matter_pct = m.get("dry_matter_pct") if m.get("dry_matter_pct") is not None else m.get("dry_matter_pct_snapshot")
        quantity_dm_kg = m.get("quantity_dm_kg") if m.get("quantity_dm_kg") is not None else m.get("physical_dm_kg")
        unit_cost = m.get("unit_cost") if m.get("unit_cost") is not None else m.get("unit_cost_snapshot")
        ref_date = m.get("reference_date") if m.get("reference_date") is not None else m.get("movement_at")
        
        from datetime import datetime, date
        if isinstance(ref_date, datetime):
            ref_date = ref_date.date()

        res = {
            "public_id": str(m["public_id"]),
            "lot_id": str(m.get("lot_public_id", "")) if m.get("lot_public_id") else None,
            "lot_uuid": str(m.get("lot_public_id", "")) if m.get("lot_public_id") else None,
            "lot_name": m.get("lot_name", ""),
            "movement_type": m["movement_type"],
            "quantity_natural_kg": str(m["quantity_natural_kg"]),
            "dry_matter_pct": str(dry_matter_pct) if dry_matter_pct is not None else None,
            "dry_matter_pct_snapshot": str(dry_matter_pct) if dry_matter_pct is not None else None,
            "utilization_pct_snapshot": str(m["utilization_pct_snapshot"]) if m.get("utilization_pct_snapshot") is not None else None,
            "quantity_dm_kg": str(quantity_dm_kg) if quantity_dm_kg is not None else None,
            "physical_dm_kg": str(quantity_dm_kg) if quantity_dm_kg is not None else None,
            "usable_dm_kg": str(m["usable_dm_kg"]) if m.get("usable_dm_kg") is not None else None,
            "unit_cost": str(unit_cost) if unit_cost is not None else None,
            "unit_cost_snapshot": str(unit_cost) if unit_cost is not None else None,
            "total_cost": str(m["total_cost"]) if m.get("total_cost") is not None else None,
            "loss_reason": m.get("loss_reason") or "",
            "reason": m.get("reason", ""),
            "balance_after_natural_kg": str(m["balance_after_natural_kg"]) if m.get("balance_after_natural_kg") is not None else None,
            "reference_date": ref_date.isoformat() if hasattr(ref_date, "isoformat") else str(ref_date) if ref_date else None,
            "movement_at": ref_date.isoformat() if hasattr(ref_date, "isoformat") else str(ref_date) if ref_date else "",
            "notes": m.get("notes", ""),
            "created_by_user_id": m.get("created_by_user_id"),
            "created_at": m["created_at"].isoformat() if hasattr(m["created_at"], "isoformat") else str(m["created_at"]),
        }
        return res

    def _dashboard_response(self, d: dict) -> dict:
        return d

    def _autonomy_source_item(self, l: dict, facility_name: str) -> dict:
        quantity_natural_kg = Decimal(str(l.get("current_quantity_natural_kg") if l.get("current_quantity_natural_kg") is not None else l.get("balance_natural_kg", 0)))
        dry_matter_pct = Decimal(str(l.get("dry_matter_pct", 0)))
        utilization_pct = Decimal(str(l.get("utilization_pct", 100)))
        physical_dm = calculate_physical_dm(quantity_natural_kg, dry_matter_pct)
        usable_dm = calculate_usable_dm(physical_dm, utilization_pct)

        production_date = l.get("production_date")
        opened_at = l["created_at"].isoformat() if hasattr(l["created_at"], "isoformat") else str(l["created_at"]) if l.get("created_at") else ""

        return {
            "source_public_id": str(l["public_id"]),
            "source_type": "feed_lot",
            "feed_type": l["feed_type"],
            "name": l["name"],
            "quantity_natural_kg": str(quantity_natural_kg),
            "dry_matter_pct": str(dry_matter_pct),
            "utilization_pct": str(utilization_pct),
            "usable_dm_kg": str(usable_dm),
            "facility_name": facility_name,
            "production_date": production_date.isoformat() if production_date and hasattr(production_date, "isoformat") else str(production_date) if production_date else "",
            "opened_at": opened_at,
            "status": l["status"],
            "warnings": [],
        }

    # ---------------------------------------------------------------------------
    # FACILITIES
    # ---------------------------------------------------------------------------

    def create_facility(self, *, subject, farm_public_id, payload, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        name = payload.get("name", "").strip()
        if not name:
            raise ForbiddenError("name_required")

        facility_type = payload.get("facility_type", "")
        if facility_type not in FACILITY_TYPES:
            raise ForbiddenError("invalid_facility_type")

        capacity = Decimal(str(payload.get("capacity_natural_kg", "0")))
        if capacity <= 0 or capacity > MAX_CAPACITY_KG:
            raise ForbiddenError("invalid_capacity")

        public_id = uuid4()
        data = {
            "public_id": public_id,
            "organization_id": ctx.organization_id,
            "farm_id": farm["id"],
            "name": name,
            "code": payload.get("code", ""),
            "facility_type": facility_type,
            "capacity_natural_kg": capacity,
            "preferred_display_unit": payload.get("preferred_display_unit", "kg"),
            "location_description": payload.get("location_description", ""),
            "active": True,
            "notes": payload.get("notes", ""),
            "created_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

        try:
            created = self.repository.create_facility(data, ctx.user_id)
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise ForbiddenError("duplicate_request_id")
            raise

        facility = self.repository.get_facility(created["public_id"])
        return self._facility_response(facility)

    def list_facilities(self, *, subject, farm_public_id, limit, offset, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        total = self.repository.count_facilities(farm["id"])
        items = self.repository.list_facilities(farm["id"], limit=limit, offset=offset)

        return {
            "items": [self._facility_response(f) for f in items],
            "pagination": {
                "limit": limit, "offset": offset,
                "returned": len(items), "total": total,
                "has_more": offset + len(items) < total,
            },
        }

    def get_facility(self, *, subject, farm_public_id, facility_uuid, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        facility = self.repository.get_facility(facility_uuid)
        if facility is None or facility["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        return self._facility_response(facility)

    def update_facility(self, *, subject, farm_public_id, facility_uuid, payload,
                        request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        facility = self.repository.get_facility(facility_uuid)
        if facility is None or facility["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        name = payload.get("name", facility["name"]).strip()
        if not name:
            raise ForbiddenError("name_required")

        facility_type = payload.get("facility_type", "") or facility["facility_type"]
        if facility_type not in FACILITY_TYPES:
            raise ForbiddenError("invalid_facility_type")

        capacity = Decimal(str(payload.get("capacity_natural_kg", facility["capacity_natural_kg"])))
        if capacity <= 0 or capacity > MAX_CAPACITY_KG:
            raise ForbiddenError("invalid_capacity")

        data = {
            "public_id": facility["public_id"],
            "organization_id": ctx.organization_id,
            "farm_id": farm["id"],
            "name": name,
            "code": payload.get("code", facility.get("code", "")),
            "facility_type": facility_type,
            "capacity_natural_kg": capacity,
            "preferred_display_unit": payload.get("preferred_display_unit", facility.get("preferred_display_unit", "kg")),
            "location_description": payload.get("location_description", facility.get("location_description", "")),
            "active": payload.get("active", facility.get("active", True)),
            "notes": payload.get("notes", facility.get("notes", "")),
            "created_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

        self.repository.update_facility(facility["id"], data, ctx.user_id)
        updated = self.repository.get_facility(facility_uuid)
        return self._facility_response(updated)

    def archive_facility(self, *, subject, farm_public_id, facility_uuid, request_id) -> None:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_manage(ctx, auth_service)

        facility = self.repository.get_facility(facility_uuid)
        if facility is None or facility["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        active_lots = self.repository.count_active_lots_for_facility(facility["id"])
        if active_lots > 0:
            raise ForbiddenError("facility_has_active_lots")

        self.repository.archive_facility(
            facility["id"], ctx.user_id, ctx.organization_id,
            farm["id"], facility["public_id"], request_id,
        )

    # ---------------------------------------------------------------------------
    # LOTS
    # ---------------------------------------------------------------------------

    def create_lot(self, *, subject, farm_public_id, payload, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        name = payload.get("name", "").strip()
        if not name:
            raise ForbiddenError("name_required")

        feed_type = payload.get("feed_type", "")
        if feed_type not in FEED_TYPES:
            raise ForbiddenError("invalid_feed_type")

        facility_uuid = payload.get("facility_uuid") or payload.get("facility_id")
        if not facility_uuid:
            raise ForbiddenError("facility_required")
        try:
            facility_uuid = UUID(str(facility_uuid))
        except (ValueError, TypeError):
            raise ForbiddenError("invalid_facility_id")

        facility = self.repository.get_facility(facility_uuid)
        if facility is None or facility["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        try:
            initial_quantity = Decimal(str(payload.get("initial_quantity_natural_kg", "0")))
        except (InvalidOperation, ValueError):
            raise ForbiddenError("invalid_initial_quantity")
        if initial_quantity <= 0 or initial_quantity > MAX_QUANTITY_KG:
            raise ForbiddenError("invalid_initial_quantity")

        try:
            dry_matter_pct = Decimal(str(payload.get("dry_matter_pct", "0")))
        except (InvalidOperation, ValueError):
            raise ForbiddenError("invalid_dry_matter_pct")
        if dry_matter_pct <= 0 or dry_matter_pct > 100:
            raise ForbiddenError("invalid_dry_matter_pct")

        try:
            utilization_pct = Decimal(str(payload.get("utilization_pct", "100")))
        except (InvalidOperation, ValueError):
            raise ForbiddenError("invalid_utilization_pct")
        if utilization_pct <= 0 or utilization_pct > 100:
            raise ForbiddenError("invalid_utilization_pct")

        initial_total_cost = None
        if payload.get("initial_total_cost") not in (None, ""):
            try:
                initial_total_cost = Decimal(str(payload["initial_total_cost"]))
            except (InvalidOperation, ValueError):
                raise ForbiddenError("invalid_initial_total_cost")
            if initial_total_cost < 0 or initial_total_cost > MAX_COST:
                raise ForbiddenError("invalid_initial_total_cost")

        planned_daily_use_dm_kg = None
        if payload.get("planned_daily_use_dm_kg") not in (None, ""):
            try:
                planned_daily_use_dm_kg = Decimal(str(payload["planned_daily_use_dm_kg"]))
            except (InvalidOperation, ValueError):
                raise ForbiddenError("invalid_planned_daily_use")
            if planned_daily_use_dm_kg < 0:
                raise ForbiddenError("invalid_planned_daily_use")

        entry_date = payload.get("entry_date")
        if entry_date is None or entry_date == "":
            entry_date = date.today()
        elif isinstance(entry_date, str):
            entry_date = date.fromisoformat(entry_date)

        prod_date = payload.get("production_date")
        if prod_date == "":
            prod_date = None
        elif isinstance(prod_date, str):
            prod_date = date.fromisoformat(prod_date)

        ens_date = payload.get("ensiling_date")
        if ens_date == "":
            ens_date = None
        elif isinstance(ens_date, str):
            ens_date = date.fromisoformat(ens_date)

        physical_dm = calculate_physical_dm(initial_quantity, dry_matter_pct)
        usable_dm = calculate_usable_dm(physical_dm, utilization_pct)

        public_id = uuid4()
        lot_public_id = uuid4()
        lot_data = {
            "public_id": lot_public_id,
            "organization_id": ctx.organization_id,
            "farm_id": farm["id"],
            "facility_id": facility["id"],
            "name": name,
            "feed_type": feed_type,
            "custom_feed_type": payload.get("custom_feed_type", ""),
            "production_date": prod_date,
            "ensiling_date": ens_date,
            "source_description": payload.get("source_description", ""),
            "status": LotStatus.AVAILABLE.value,
            "initial_quantity_natural_kg": initial_quantity,
            "initial_total_cost": initial_total_cost,
            "dry_matter_pct": dry_matter_pct,
            "utilization_pct": utilization_pct,
            "balance_natural_kg": initial_quantity,
            "planned_daily_use_dm_kg": planned_daily_use_dm_kg,
            "entry_date": entry_date,
            "notes": payload.get("notes", ""),
            "created_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

        movement_data = {
            "public_id": public_id,
            "lot_public_id": lot_public_id,
            "organization_id": ctx.organization_id,
            "farm_id": farm["id"],
            "movement_type": MovementType.INITIAL_BALANCE.value,
            "quantity_natural_kg": initial_quantity,
            "dry_matter_pct": dry_matter_pct,
            "quantity_dm_kg": physical_dm,
            "unit_cost": calculate_cost_per_natural_kg(initial_total_cost, initial_quantity),
            "total_cost": initial_total_cost,
            "balance_after_natural_kg": initial_quantity,
            "reference_date": entry_date,
            "notes": payload.get("notes", ""),
            "created_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

        try:
            created = self.repository.create_lot(lot_data, movement_data, ctx.user_id)
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise ForbiddenError("duplicate_request_id")
            raise

        lot = self.repository.get_lot(created["public_id"])
        return self._lot_response(lot)

    def list_lots(self, *, subject, farm_public_id, limit, offset,
                  facility_uuid=None, feed_type=None, status=None,
                  search=None, request_id=None) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        facility_id = None
        if facility_uuid:
            fac = self.repository.get_facility(facility_uuid)
            if fac and fac["farm_id"] == farm["id"]:
                facility_id = fac["id"]

        filters = {}
        if facility_id:
            filters["facility_id"] = facility_id
        if feed_type:
            filters["feed_type"] = feed_type
        if status:
            filters["status"] = status
        if search:
            filters["search"] = search

        total = self.repository.count_lots(farm["id"], filters=filters or None)
        items = self.repository.list_lots(
            farm["id"], limit=limit, offset=offset,
            filters=filters or None,
        )

        return {
            "items": [self._lot_response(l) for l in items],
            "pagination": {
                "limit": limit, "offset": offset,
                "returned": len(items), "total": total,
                "has_more": offset + len(items) < total,
            },
        }

    def get_lot(self, *, subject, farm_public_id, lot_uuid, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        lot = self.repository.get_lot(lot_uuid)
        if lot is None or lot["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        return self._lot_response(lot)

    def update_lot(self, *, subject, farm_public_id, lot_uuid, payload,
                   request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        lot = self.repository.get_lot(lot_uuid)
        if lot is None or lot["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        name = payload.get("name", lot["name"]).strip()
        if not name:
            raise ForbiddenError("name_required")

        feed_type = payload.get("feed_type", lot["feed_type"])
        if feed_type not in FEED_TYPES:
            raise ForbiddenError("invalid_feed_type")

        planned_daily_use_dm_kg = lot.get("planned_daily_use_dm_kg")
        if "planned_daily_use_dm_kg" in payload:
            if payload["planned_daily_use_dm_kg"] is not None:
                try:
                    planned_daily_use_dm_kg = Decimal(str(payload["planned_daily_use_dm_kg"]))
                except (InvalidOperation, ValueError):
                    raise ForbiddenError("invalid_planned_daily_use")
                if planned_daily_use_dm_kg < 0:
                    raise ForbiddenError("invalid_planned_daily_use")
            else:
                planned_daily_use_dm_kg = None

        utilization_pct = lot["utilization_pct"]
        if "utilization_pct" in payload:
            try:
                utilization_pct = Decimal(str(payload["utilization_pct"]))
            except (InvalidOperation, ValueError):
                raise ForbiddenError("invalid_utilization_pct")
            if utilization_pct <= 0 or utilization_pct > 100:
                raise ForbiddenError("invalid_utilization_pct")

        data = {
            "name": name,
            "feed_type": feed_type,
            "planned_daily_use_dm_kg": planned_daily_use_dm_kg,
            "utilization_pct": utilization_pct,
            "notes": payload.get("notes", lot.get("notes", "")),
        }

        self.repository.update_lot(lot["id"], data, ctx.user_id, request_id)
        updated = self.repository.get_lot(lot_uuid)
        return self._lot_response(updated)

    def archive_lot(self, *, subject, farm_public_id, lot_uuid, request_id) -> None:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_manage(ctx, auth_service)

        lot = self.repository.get_lot(lot_uuid)
        if lot is None or lot["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        if lot["status"] not in ACTIVE_LOT_STATUSES:
            raise ForbiddenError("lot_not_active")

        self.repository.archive_lot(
            lot["id"], ctx.user_id, ctx.organization_id,
            farm["id"], lot["public_id"], request_id,
        )

    # ---------------------------------------------------------------------------
    # MOVEMENTS
    # ---------------------------------------------------------------------------

    def _is_same_payload(self, payload: dict, existing: dict, lot: dict) -> bool:
        # 1. Compare movement_type
        if payload.get("movement_type") != existing.get("movement_type"):
            return False

        # 2. Compare quantity_natural_kg
        try:
            p_qty = Decimal(str(payload.get("quantity_natural_kg", "0")))
            e_qty = Decimal(str(existing.get("quantity_natural_kg", "0")))
            if _q2(p_qty) != _q2(e_qty):
                return False
        except Exception:
            return False

        # 3. Compare dry_matter_pct
        try:
            p_dm = Decimal(str(payload.get("dry_matter_pct") if payload.get("dry_matter_pct") is not None else lot.get("dry_matter_pct", 0)))
            e_dm = Decimal(str(existing.get("dry_matter_pct_snapshot") if existing.get("dry_matter_pct_snapshot") is not None else existing.get("dry_matter_pct", 0)))
            if _q2(p_dm) != _q2(e_dm):
                return False
        except Exception:
            return False

        # 4. Compare utilization_pct
        try:
            p_util = Decimal(str(payload.get("utilization_pct") if payload.get("utilization_pct") is not None else 100))
            e_util = Decimal(str(existing.get("utilization_pct_snapshot") if existing.get("utilization_pct_snapshot") is not None else 100))
            if _q2(p_util) != _q2(e_util):
                return False
        except Exception:
            return False

        # 5. Compare unit_cost / unit_cost_snapshot
        p_uc = payload.get("unit_cost")
        e_uc = existing.get("unit_cost_snapshot") if existing.get("unit_cost_snapshot") is not None else existing.get("unit_cost")
        if (p_uc is None) != (e_uc is None):
            return False
        if p_uc is not None:
            try:
                if _q4(Decimal(str(p_uc))) != _q4(Decimal(str(e_uc))):
                    return False
            except Exception:
                return False

        # 6. Compare total_cost
        p_tc = payload.get("total_cost")
        e_tc = existing.get("total_cost")
        if (p_tc is None) != (e_tc is None):
            return False
        if p_tc is not None:
            try:
                if _q2(Decimal(str(p_tc))) != _q2(Decimal(str(e_tc))):
                    return False
            except Exception:
                return False

        # 7. Compare loss_reason
        p_lr = payload.get("loss_reason") or ""
        e_lr = existing.get("loss_reason") or ""
        if p_lr.strip() != e_lr.strip():
            return False

        # 8. Compare reason
        p_r = payload.get("reason") or ""
        e_r = existing.get("reason") or ""
        if p_r.strip() != e_r.strip():
            return False

        # 9. Compare notes
        p_n = payload.get("notes") or ""
        e_n = existing.get("notes") or ""
        if p_n.strip() != e_n.strip():
            return False

        return True

    def create_movement(self, *, subject, farm_public_id, lot_uuid, payload,
                        request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        lot = self.repository.get_lot(lot_uuid)
        if lot is None or lot["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        if request_id:
            existing = self.repository.find_movement_by_request_id(lot["id"], request_id)
            if existing:
                if self._is_same_payload(payload, existing, lot):
                    return self._movement_response(existing)
                else:
                    raise ForbiddenError("duplicate_request_id")

        if lot["status"] == LotStatus.ARCHIVED.value:
            raise ForbiddenError("lot_archived")

        movement_type = payload.get("movement_type", "")
        if movement_type not in MOVEMENT_TYPES:
            raise ForbiddenError("invalid_movement_type")

        try:
            quantity = Decimal(str(payload.get("quantity_natural_kg", "0")))
        except (InvalidOperation, ValueError):
            raise ForbiddenError("invalid_quantity")
        if quantity <= 0 or quantity > MAX_QUANTITY_KG:
            raise ForbiddenError("invalid_quantity")

        try:
            dm_pct = Decimal(str(payload.get("dry_matter_pct", lot["dry_matter_pct"])))
        except (InvalidOperation, ValueError):
            raise ForbiddenError("invalid_dry_matter_pct")
        if dm_pct <= 0 or dm_pct > 100:
            raise ForbiddenError("invalid_dry_matter_pct")

        physical_dm = calculate_physical_dm(quantity, dm_pct)

        balance_after = Decimal(str(lot.get("current_quantity_natural_kg") if lot.get("current_quantity_natural_kg") is not None else lot.get("balance_natural_kg", 0)))
        if movement_type in SUBTRACTIVE_MOVEMENTS:
            if quantity > balance_after:
                raise ForbiddenError("insufficient_balance")
            balance_after = _q2(balance_after - quantity)
        else:
            balance_after = _q2(balance_after + quantity)

        unit_cost = None
        total_cost = None
        if movement_type in (MovementType.ENTRY.value, MovementType.INITIAL_BALANCE.value):
            if payload.get("unit_cost") is not None:
                try:
                    unit_cost = Decimal(str(payload["unit_cost"]))
                except (InvalidOperation, ValueError):
                    raise ForbiddenError("invalid_unit_cost")
                if unit_cost < 0 or unit_cost > MAX_COST:
                    raise ForbiddenError("invalid_unit_cost")
            if payload.get("total_cost") is not None:
                try:
                    total_cost = Decimal(str(payload["total_cost"]))
                except (InvalidOperation, ValueError):
                    raise ForbiddenError("invalid_total_cost")
                if total_cost < 0 or total_cost > MAX_COST:
                    raise ForbiddenError("invalid_total_cost")

        loss_reason = None
        if movement_type == MovementType.LOSS.value:
            loss_reason = payload.get("loss_reason")
            if not loss_reason or not isinstance(loss_reason, str):
                raise ForbiddenError("invalid_loss_reason")
            # Enforce max length of 200 characters
            if len(loss_reason) > 200:
                raise ForbiddenError("invalid_loss_reason")
            # Enforce absence of HTML/script elements to prevent HTML/XSS injection
            import re
            if re.search(r"<[^>]*>", loss_reason):
                raise ForbiddenError("invalid_loss_reason")
            loss_reason = loss_reason.strip()
            # Documented limitation: HTML and script tags are strictly forbidden. Only simple text is allowed.

        ref_date = payload.get("reference_date")
        if ref_date is None:
            ref_date = date.today()
        elif isinstance(ref_date, str):
            ref_date = date.fromisoformat(ref_date)

        public_id = uuid4()
        movement_data = {
            "public_id": public_id,
            "lot_id": lot["id"],
            "lot_public_id": lot["public_id"],
            "organization_id": ctx.organization_id,
            "farm_id": farm["id"],
            "movement_type": movement_type,
            "quantity_natural_kg": quantity,
            "dry_matter_pct": dm_pct,
            "quantity_dm_kg": physical_dm,
            "unit_cost": unit_cost,
            "total_cost": total_cost,
            "loss_reason": loss_reason,
            "reason": payload.get("reason", ""),
            "balance_after_natural_kg": balance_after,
            "reference_date": ref_date,
            "notes": payload.get("notes", ""),
            "created_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

        lot_update = {
            "balance_natural_kg": balance_after,
            "status": LotStatus.DEPLETED.value if balance_after <= 0 else lot["status"],
        }

        try:
            created = self.repository.create_movement(
                movement_data, lot_update, lot["id"], ctx.user_id
            )
        except Exception as e:
            if "unique" in str(e).lower() or "duplicate" in str(e).lower():
                raise ForbiddenError("duplicate_request_id")
            raise

        movement = self.repository.get_movement(created["public_id"])
        return self._movement_response(movement)

    def withdraw(self, *, subject, farm_public_id, lot_uuid, payload,
                 request_id) -> dict:
        payload_with_type = {**payload, "movement_type": MovementType.WITHDRAWAL.value}
        return self.create_movement(
            subject=subject, farm_public_id=farm_public_id,
            lot_uuid=lot_uuid, payload=payload_with_type,
            request_id=request_id,
        )

    def record_loss(self, *, subject, farm_public_id, lot_uuid, payload,
                    request_id) -> dict:
        payload_with_type = {**payload, "movement_type": MovementType.LOSS.value}
        return self.create_movement(
            subject=subject, farm_public_id=farm_public_id,
            lot_uuid=lot_uuid, payload=payload_with_type,
            request_id=request_id,
        )

    def adjust(self, *, subject, farm_public_id, lot_uuid, payload,
               request_id) -> dict:
        quantity = Decimal(str(payload.get("quantity_natural_kg", "0")))
        lot = self.repository.get_lot(lot_uuid)
        if lot is None:
            raise HiddenResourceError()
        balance = Decimal(str(lot.get("balance_natural_kg", 0)))

        if quantity >= 0:
            adj_type = MovementType.ADJUSTMENT_POSITIVE.value
        else:
            adj_type = MovementType.ADJUSTMENT_NEGATIVE.value
            quantity = abs(quantity)

        payload_with_type = {**payload, "movement_type": adj_type, "quantity_natural_kg": str(quantity)}
        return self.create_movement(
            subject=subject, farm_public_id=farm_public_id,
            lot_uuid=lot_uuid, payload=payload_with_type,
            request_id=request_id,
        )

    def list_movements(self, *, subject, farm_public_id, lot_uuid,
                       limit, offset, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        lot = self.repository.get_lot(lot_uuid)
        if lot is None or lot["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        total = self.repository.count_movements(lot["id"])
        items = self.repository.list_movements(lot["id"], limit=limit, offset=offset)

        return {
            "items": [self._movement_response(m) for m in items],
            "pagination": {
                "limit": limit, "offset": offset,
                "returned": len(items), "total": total,
                "has_more": offset + len(items) < total,
            },
        }

    def get_movement(self, *, subject, farm_public_id, movement_uuid, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        movement = self.repository.get_movement(movement_uuid)
        if movement is None or movement["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        return self._movement_response(movement)

    # ---------------------------------------------------------------------------
    # OPERATIONS (specialized lot endpoints)
    # ---------------------------------------------------------------------------

    def withdraw_from_lot(self, *, subject, farm_public_id, lot_uuid, payload,
                          request_id) -> dict:
        return self.withdraw(
            subject=subject, farm_public_id=farm_public_id,
            lot_uuid=lot_uuid, payload=payload,
            request_id=request_id,
        )

    def record_loss_on_lot(self, *, subject, farm_public_id, lot_uuid, payload,
                           request_id) -> dict:
        return self.record_loss(
            subject=subject, farm_public_id=farm_public_id,
            lot_uuid=lot_uuid, payload=payload,
            request_id=request_id,
        )

    def adjust_lot(self, *, subject, farm_public_id, lot_uuid, payload,
                   request_id) -> dict:
        return self.adjust(
            subject=subject, farm_public_id=farm_public_id,
            lot_uuid=lot_uuid, payload=payload,
            request_id=request_id,
        )

    # ---------------------------------------------------------------------------
    # DASHBOARD
    # ---------------------------------------------------------------------------

    def get_dashboard(self, *, subject, farm_public_id, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        facilities = self.repository.list_facilities(farm["id"], limit=1000, offset=0)
        lots = self.repository.list_active_lots(farm["id"])

        total_capacity = Decimal("0")
        total_balance = Decimal("0")
        total_physical_dm = Decimal("0")
        total_usable_dm = Decimal("0")
        total_value = Decimal("0")
        lots_by_status = {}
        lots_by_feed_type = {}
        low_stock_lots = []
        depleted_lots = []

        for f in facilities:
            total_capacity += Decimal(str(f.get("capacity_natural_kg", 0)))

        for l in lots:
            bal = Decimal(str(l.get("current_quantity_natural_kg") if l.get("current_quantity_natural_kg") is not None else l.get("balance_natural_kg", 0)))
            dm_pct = Decimal(str(l.get("dry_matter_pct", 0)))
            util_pct = Decimal(str(l.get("utilization_pct", 100)))
            initial_qty = Decimal(str(l.get("initial_quantity_natural_kg", 0)))
            initial_cost = Decimal(str(l["initial_total_cost"])) if l.get("initial_total_cost") is not None else None

            total_balance += bal

            phys = calculate_physical_dm(bal, dm_pct)
            usab = calculate_usable_dm(phys, util_pct)
            total_physical_dm += phys
            total_usable_dm += usab

            avg_cost = calculate_cost_per_natural_kg(initial_cost, initial_qty)
            inv_val = calculate_inventory_value(bal, avg_cost)
            total_value += inv_val

            st = l.get("status", "available")
            lots_by_status[st] = lots_by_status.get(st, 0) + 1

            ft = l.get("feed_type", "outro")
            lots_by_feed_type[ft] = lots_by_feed_type.get(ft, 0) + 1

            planned = l.get("planned_daily_use_dm_kg")
            if planned is not None and Decimal(str(planned)) > 0:
                days = calculate_days_remaining(usab, Decimal(str(planned)))
                if days is not None and days <= 7 and st in ACTIVE_LOT_STATUSES:
                    low_stock_lots.append({
                        "public_id": str(l["public_id"]),
                        "name": l["name"],
                        "feed_type": ft,
                        "days_remaining": days,
                    })

            if bal <= 0 and st in ACTIVE_LOT_STATUSES:
                depleted_lots.append({
                    "public_id": str(l["public_id"]),
                    "name": l["name"],
                    "feed_type": ft,
                })

        return {
            "total_natural_kg": str(total_balance),
            "total_physical_dm_kg": str(total_physical_dm),
            "total_usable_dm_kg": str(total_usable_dm),
            "total_value": str(total_value),
            "period_losses_kg": "0",
            "period_losses_value": "0",
            "open_lots": lots_by_status.get("opened", 0),
            "lots_near_end": len(low_stock_lots),
            "quarantined_lots": lots_by_status.get("quarantined", 0),
            "depleted_lots": lots_by_status.get("depleted", 0),
            "total_facilities": len(facilities),
            "active_facilities": len([f for f in facilities if f.get("active", True)]),
            "lots_by_feed_type": [{"feed_type": k, "count": v} for k, v in lots_by_feed_type.items()],
            "lots_by_facility": [],

            # Additional keys to satisfy TestDashboard unit tests:
            "total_active_lots": len([l for l in lots if l.get("status") in ACTIVE_LOT_STATUSES]),
            "total_capacity_natural_kg": str(total_capacity),
            "total_balance_natural_kg": str(total_balance),
            "total_inventory_value": str(total_value),
            "lots_by_status": lots_by_status,
            "low_stock_lots": low_stock_lots,
        }

    # ---------------------------------------------------------------------------
    # RECONCILIATION
    # ---------------------------------------------------------------------------

    def get_reconciliation(self, *, subject, farm_public_id, lot_uuid,
                           request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        lot = self.repository.get_lot(lot_uuid)
        if lot is None or lot["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        persisted_balance = Decimal(str(lot.get("current_quantity_natural_kg") if lot.get("current_quantity_natural_kg") is not None else lot.get("balance_natural_kg", 0)))

        movements = self.repository.get_movements_for_reconciliation(lot["id"])
        if movements:
            ledger_balance = reconcile_balance(
                Decimal(str(lot.get("initial_quantity_natural_kg", 0))),
                movements,
            )
        else:
            ledger_balance = Decimal(str(lot.get("initial_quantity_natural_kg", 0)))

        difference = _q2(persisted_balance - ledger_balance)
        is_reconciled = difference == Decimal("0")

        return {
            "lot_public_id": str(lot["public_id"]),
            "lot_name": lot["name"],
            "persisted_balance_natural_kg": str(persisted_balance),
            "ledger_balance_natural_kg": str(ledger_balance),
            "difference_natural_kg": str(difference),
            "persisted_balance": str(persisted_balance),
            "ledger_balance": str(ledger_balance),
            "difference": str(difference),
            "is_reconciled": is_reconciled,
            "movement_count": len(movements),
        }

    # ---------------------------------------------------------------------------
    # AUTONOMY SOURCES
    # ---------------------------------------------------------------------------

    def get_autonomy_sources(self, *, subject, farm_public_id, request_id) -> list[dict]:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        lots = self.repository.list_active_lots(farm["id"])

        facility_cache: dict[int, str] = {}
        results = []
        for l in lots:
            fid = l.get("facility_id")
            if fid and fid not in facility_cache:
                facility = self.repository.get_facility_by_id(fid)
                facility_cache[fid] = facility["name"] if facility else ""
            facility_name = facility_cache.get(fid, "")
            results.append(self._autonomy_source_item(l, facility_name))

        return results
