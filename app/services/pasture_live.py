"""Serviço de Pasto Vivo — orquestra autorização, cálculo e persistência."""
import logging
from uuid import UUID, uuid4
from datetime import date, datetime, timezone

from core.authorization import AuthorizationService, ForbiddenError, HiddenResourceError
from core.permissions import Permission, ORGANIZATION_WIDE_FARM_ROLES
from domain.pasture_live import (
    FORMULA_VERSION, PaddockStatus, EventType, MeasurementMethod,
    MeasurementResult, PaddockState,
    calculate_next_release_date, suggest_paddock_state, is_measurement_fresh,
    _q2, MAX_AREA_HA, MAX_DM_KG_HA, MAX_UTILIZATION_PCT, MAX_REST_DAYS,
    _FORAGE_SPECIES,
)
from decimal import Decimal

logger = logging.getLogger("wins_agro.pasture_live")


class PastureLiveService:
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

    def create_paddock(self, *, subject, farm_public_id, payload, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        name = payload.get("name", "").strip()
        if not name:
            raise ForbiddenError("name_required")

        area_ha = Decimal(str(payload.get("area_ha", "0")))
        if area_ha <= 0 or area_ha > MAX_AREA_HA:
            raise ForbiddenError("invalid_area_ha")

        forage_species = payload.get("forage_species", "other")
        if forage_species not in _FORAGE_SPECIES:
            raise ForbiddenError("invalid_forage_species")

        rest_days = int(payload.get("planned_rest_days", payload.get("rest_days", 30)))
        if rest_days < 0 or rest_days > MAX_REST_DAYS:
            raise ForbiddenError("invalid_rest_days")

        public_id = uuid4()
        data = {
            "public_id": public_id,
            "organization_id": ctx.organization_id,
            "farm_id": farm["id"],
            "name": name,
            "code": payload.get("code", ""),
            "area_ha": area_ha,
            "forage_species": forage_species,
            "cultivar": payload.get("cultivar", ""),
            "target_entry_height_cm": payload.get("target_entry_height_cm"),
            "target_exit_height_cm": payload.get("target_exit_height_cm"),
            "planned_rest_days": rest_days,
            "default_utilization_pct": Decimal(str(payload.get("default_utilization_pct", "50"))),
            "manual_status": PaddockStatus.NO_MEASUREMENT.value,
            "active": True,
            "notes": payload.get("notes", ""),
            "created_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

        created = self.repository.create_paddock(data, ctx.user_id)
        paddock = self.repository.get_paddock(created["public_id"])
        return self._paddock_response(paddock)

    def list_paddocks(self, *, subject, farm_public_id, limit, offset, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        total = self.repository.count_paddocks(farm["id"])
        items = self.repository.list_paddocks(farm["id"], limit=limit, offset=offset)

        return {
            "items": [self._paddock_summary(p) for p in items],
            "pagination": {
                "limit": limit, "offset": offset,
                "returned": len(items), "total": total,
                "has_more": offset + len(items) < total,
            },
        }

    def get_paddock(self, *, subject, farm_public_id, paddock_uuid, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        paddock = self.repository.get_paddock(paddock_uuid)
        if paddock is None or paddock["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        return self._paddock_response(paddock)

    def update_paddock(self, *, subject, farm_public_id, paddock_uuid, payload,
                       request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        paddock = self.repository.get_paddock(paddock_uuid)
        if paddock is None or paddock["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        name = payload.get("name", paddock["name"]).strip()
        if not name:
            raise ForbiddenError("name_required")

        area_ha = Decimal(str(payload.get("area_ha", paddock["area_ha"])))
        if area_ha <= 0 or area_ha > MAX_AREA_HA:
            raise ForbiddenError("invalid_area_ha")

        planned_rest_days = int(payload.get("planned_rest_days", paddock["planned_rest_days"]))
        if planned_rest_days < 0 or planned_rest_days > MAX_REST_DAYS:
            raise ForbiddenError("invalid_rest_days")

        data = {
            "public_id": paddock["public_id"],
            "organization_id": ctx.organization_id,
            "farm_id": farm["id"],
            "name": name,
            "code": payload.get("code", paddock.get("code", "")),
            "area_ha": area_ha,
            "forage_species": payload.get("forage_species", paddock["forage_species"]),
            "cultivar": payload.get("cultivar", paddock.get("cultivar", "")),
            "target_entry_height_cm": payload.get("target_entry_height_cm", paddock.get("target_entry_height_cm")),
            "target_exit_height_cm": payload.get("target_exit_height_cm", paddock.get("target_exit_height_cm")),
            "planned_rest_days": planned_rest_days,
            "default_utilization_pct": Decimal(str(payload.get("default_utilization_pct", paddock.get("default_utilization_pct", "50")))),
            "manual_status": payload.get("manual_status", paddock["manual_status"]),
            "active": payload.get("active", paddock["active"]),
            "notes": payload.get("notes", paddock.get("notes", "")),
            "request_id": request_id,
        }

        self.repository.update_paddock(paddock["id"], data, ctx.user_id)
        updated = self.repository.get_paddock(paddock_uuid)
        return self._paddock_response(updated)

    def archive_paddock(self, *, subject, farm_public_id, paddock_uuid, request_id) -> None:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        paddock = self.repository.get_paddock(paddock_uuid)
        if paddock is None or paddock["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        self.repository.archive_paddock(
            paddock["id"], ctx.user_id, ctx.organization_id,
            farm["id"], paddock["public_id"], request_id,
        )

    def create_measurement(self, *, subject, farm_public_id, paddock_uuid, payload,
                           request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        paddock = self.repository.get_paddock(paddock_uuid)
        if paddock is None or paddock["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        method = payload.get("measurement_method", "visual")
        measured_at = payload.get("measured_at") or date.today().isoformat()
        if isinstance(measured_at, str):
            measured_at = date.fromisoformat(measured_at)

        available_dm_kg_ha = Decimal(str(payload.get("available_dm_kg_ha", "0")))
        utilization_pct = Decimal(str(payload.get("utilization_pct", "100")))
        area_ha = Decimal(str(paddock["area_ha"]))
        average_height_cm = Decimal(str(payload["average_height_cm"])) if payload.get("average_height_cm") else None

        total_dm = _q2(area_ha * available_dm_kg_ha)
        usable_dm = _q2(area_ha * available_dm_kg_ha * utilization_pct / Decimal("100"))

        public_id = uuid4()
        data = {
            "public_id": public_id,
            "paddock_id": paddock["id"],
            "farm_id": farm["id"],
            "organization_id": ctx.organization_id,
            "measurement_method": method,
            "measured_at": measured_at,
            "available_dm_kg_ha": available_dm_kg_ha,
            "utilization_pct": utilization_pct,
            "calculated_total_dm_kg": total_dm,
            "calculated_usable_dm_kg": usable_dm,
            "average_height_cm": average_height_cm,
            "notes": payload.get("notes", ""),
            "measured_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

        created = self.repository.create_measurement(data, ctx.user_id)

        measurement = self.repository.get_measurement(created["public_id"])
        return self._measurement_response(measurement)

    def list_measurements(self, *, subject, farm_public_id, paddock_uuid,
                          limit, offset, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        paddock = self.repository.get_paddock(paddock_uuid)
        if paddock is None or paddock["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        total = self.repository.count_measurements(paddock["id"])
        items = self.repository.list_measurements(paddock["id"], limit=limit, offset=offset)

        return {
            "items": [self._measurement_summary(m) for m in items],
            "pagination": {
                "limit": limit, "offset": offset,
                "returned": len(items), "total": total,
                "has_more": offset + len(items) < total,
            },
        }

    def get_measurement(self, *, subject, farm_public_id, paddock_uuid,
                        measurement_uuid, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        paddock = self.repository.get_paddock(paddock_uuid)
        if paddock is None or paddock["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        measurement = self.repository.get_measurement(measurement_uuid)
        if measurement is None or measurement["paddock_id"] != paddock["id"]:
            raise HiddenResourceError()

        return self._measurement_response(measurement)

    def create_event(self, *, subject, farm_public_id, paddock_uuid, payload,
                     request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        paddock = self.repository.get_paddock(paddock_uuid)
        if paddock is None or paddock["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        event_type = payload.get("event_type", "")

        if event_type == EventType.GRAZING_STARTED.value:
            open_event = self.repository.get_open_grazing_event(paddock["id"])
            if open_event is not None:
                raise ForbiddenError("double_grazing_prevented")

        status_before = paddock["manual_status"]
        status_after = self._compute_event_status(event_type, status_before, paddock)

        public_id = uuid4()
        data = {
            "public_id": public_id,
            "paddock_id": paddock["id"],
            "farm_id": farm["id"],
            "organization_id": ctx.organization_id,
            "event_type": event_type,
            "event_at": datetime.now(timezone.utc),
            "expected_end_at": payload.get("expected_end_at"),
            "actual_end_at": payload.get("actual_end_at"),
            "head_count": payload.get("head_count"),
            "average_weight_kg": payload.get("average_weight_kg"),
            "management_group_name": payload.get("management_group_name", ""),
            "notes": payload.get("notes", ""),
            "created_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

        self.repository.create_event(data, ctx.user_id)

        self.repository.update_paddock_manual_status(paddock["id"], status_after, ctx.user_id)

        return {"status": status_after}

    def list_events(self, *, subject, farm_public_id, paddock_uuid,
                    limit, offset, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)

        paddock = self.repository.get_paddock(paddock_uuid)
        if paddock is None or paddock["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        total = self.repository.count_events(paddock["id"])
        items = self.repository.list_events(paddock["id"], limit=limit, offset=offset)

        return {
            "items": [self._event_summary(e) for e in items],
            "pagination": {
                "limit": limit, "offset": offset,
                "returned": len(items), "total": total,
                "has_more": offset + len(items) < total,
            },
        }

    def start_grazing(self, *, subject, farm_public_id, paddock_uuid,
                      payload, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        paddock = self.repository.get_paddock(paddock_uuid)
        if paddock is None or paddock["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        open_event = self.repository.get_open_grazing_event(paddock["id"])
        if open_event is not None:
            raise ForbiddenError("double_grazing_prevented")

        public_id = uuid4()
        data = {
            "public_id": public_id,
            "paddock_id": paddock["id"],
            "farm_id": farm["id"],
            "organization_id": ctx.organization_id,
            "event_type": EventType.GRAZING_STARTED.value,
            "event_at": datetime.now(timezone.utc),
            "expected_end_at": payload.get("expected_end_at") if payload else None,
            "actual_end_at": None,
            "head_count": payload.get("head_count") if payload else None,
            "average_weight_kg": payload.get("average_weight_kg") if payload else None,
            "management_group_name": (payload.get("management_group_name", "") if payload else ""),
            "notes": payload.get("notes", "") if payload else "",
            "created_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

        self.repository.create_event(data, ctx.user_id)
        self.repository.update_paddock_manual_status(paddock["id"], PaddockStatus.GRAZING.value, ctx.user_id)

        return {"status": PaddockStatus.GRAZING.value}

    def finish_grazing(self, *, subject, farm_public_id, paddock_uuid,
                       payload, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        auth_service = AuthorizationService(self.auth_repository)
        self._require_write(ctx, auth_service)

        paddock = self.repository.get_paddock(paddock_uuid)
        if paddock is None or paddock["farm_id"] != farm["id"]:
            raise HiddenResourceError()

        open_event = self.repository.get_open_grazing_event(paddock["id"])
        if open_event is None:
            raise ForbiddenError("no_open_grazing")

        public_id = uuid4()
        data = {
            "public_id": public_id,
            "paddock_id": paddock["id"],
            "farm_id": farm["id"],
            "organization_id": ctx.organization_id,
            "event_type": EventType.GRAZING_FINISHED.value,
            "event_at": datetime.now(timezone.utc),
            "expected_end_at": None,
            "actual_end_at": datetime.now(timezone.utc),
            "head_count": None,
            "average_weight_kg": None,
            "management_group_name": "",
            "notes": payload.get("notes", "") if payload else "",
            "created_by_user_id": ctx.user_id,
            "request_id": request_id,
        }

        self.repository.create_event(data, ctx.user_id)
        self.repository.update_paddock_manual_status(paddock["id"], PaddockStatus.RESTING.value, ctx.user_id)

        return {"status": PaddockStatus.RESTING.value}

        return {
            "status": PaddockStatus.RESTING.value,
            "next_release_date": next_release.isoformat(),
        }

    def get_dashboard(self, *, subject, farm_public_id, request_id) -> dict:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        return self.repository.get_dashboard(farm["id"])

    def get_autonomy_sources(self, *, subject, farm_public_id, request_id) -> list[dict]:
        ctx, farm = self._resolve_farm_context(subject, farm_public_id, request_id)
        return self.repository.get_autonomy_sources(farm["id"])

    def _compute_event_status(self, event_type: str, current_status: str,
                              paddock: dict) -> str:
        if event_type == EventType.GRAZING_STARTED.value:
            return PaddockStatus.GRAZING.value
        elif event_type == EventType.GRAZING_FINISHED.value:
            return PaddockStatus.RESTING.value
        elif event_type == EventType.REST_STARTED.value:
            return PaddockStatus.RESTING.value
        elif event_type == EventType.RELEASED.value:
            return PaddockStatus.READY.value
        elif event_type == EventType.MARKED_UNAVAILABLE.value:
            return PaddockStatus.UNAVAILABLE.value
        elif event_type == EventType.REACTIVATED.value:
            return PaddockStatus.READY.value
        elif event_type == EventType.STATUS_ADJUSTED.value:
            return current_status
        return current_status

    def _paddock_summary(self, p: dict) -> dict:
        return {
            "public_id": str(p["public_id"]),
            "name": p["name"],
            "area_ha": str(p["area_ha"]),
            "forage_species": p["forage_species"],
            "rest_days": p["planned_rest_days"],
            "status": p["manual_status"],
            "is_inactive": not p.get("active", True),
            "is_unavailable": p.get("manual_status") == "unavailable",
            "created_at": p["created_at"].isoformat() if hasattr(p["created_at"], "isoformat") else str(p["created_at"]),
        }

    def _paddock_response(self, p: dict) -> dict:
        return {
            "public_id": str(p["public_id"]),
            "name": p["name"],
            "area_ha": str(p["area_ha"]),
            "forage_species": p["forage_species"],
            "rest_days": p["planned_rest_days"],
            "planned_rest_days": p.get("planned_rest_days"),
            "status": p["manual_status"],
            "is_inactive": not p.get("active", True),
            "is_unavailable": p.get("manual_status") == "unavailable",
            "notes": p.get("notes", ""),
            "created_at": p["created_at"].isoformat() if hasattr(p["created_at"], "isoformat") else str(p["created_at"]),
            "updated_at": p["updated_at"].isoformat() if hasattr(p["updated_at"], "isoformat") else str(p["updated_at"]),
        }

    def _measurement_summary(self, m: dict) -> dict:
        return {
            "public_id": str(m["public_id"]),
            "measurement_method": m.get("measurement_method", ""),
            "measured_at": m["measured_at"].isoformat() if hasattr(m["measured_at"], "isoformat") else str(m["measured_at"]),
            "available_dm_kg_ha": str(m["available_dm_kg_ha"]),
            "utilization_pct": str(m["utilization_pct"]),
            "calculated_usable_dm_kg": str(m.get("calculated_usable_dm_kg", "")),
            "created_at": m["created_at"].isoformat() if hasattr(m["created_at"], "isoformat") else str(m["created_at"]),
        }

    def _measurement_response(self, m: dict) -> dict:
        return {
            "public_id": str(m["public_id"]),
            "paddock_id": m["paddock_id"],
            "measurement_method": m["measurement_method"],
            "measured_at": m["measured_at"].isoformat() if hasattr(m["measured_at"], "isoformat") else str(m["measured_at"]),
            "available_dm_kg_ha": str(m["available_dm_kg_ha"]),
            "utilization_pct": str(m["utilization_pct"]),
            "calculated_total_dm_kg": str(m["calculated_total_dm_kg"]),
            "calculated_usable_dm_kg": str(m["calculated_usable_dm_kg"]),
            "average_height_cm": str(m["average_height_cm"]) if m.get("average_height_cm") else None,
            "notes": m.get("notes", ""),
            "formula_version": FORMULA_VERSION,
            "created_at": m["created_at"].isoformat() if hasattr(m["created_at"], "isoformat") else str(m["created_at"]),
        }

    def _event_summary(self, e: dict) -> dict:
        return {
            "public_id": str(e["public_id"]),
            "event_type": e["event_type"],
            "notes": e.get("notes", ""),
            "created_at": e["created_at"].isoformat() if hasattr(e["created_at"], "isoformat") else str(e["created_at"]),
        }
