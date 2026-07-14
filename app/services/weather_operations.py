"""Serviço de Clima e Janelas Operacionais — orquestra autorização, cache, provider e cálculos."""
import logging
import os
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from core.authorization import AuthorizationContext, AuthorizationService, ForbiddenError, HiddenResourceError
from core.permissions import ORGANIZATION_WIDE_FARM_ROLES, Permission, Role
from domain.foundation import RecordStatus
from domain.weather_operations import (
    FORMULA_VERSION, NORMALIZATION_VERSION, WindowType, WeatherStatus,
    SnapshotType, CacheStatus, WINDOW_TYPE_LABELS, WEATHER_STATUS_LABELS,
    normalize_weather_condition, classify_temperature,
    compute_window_score, check_freshness, compute_cache_expires_at,
    build_window_response,
)
from integrations.weather_provider import (
    WeatherProviderError, fetch_current_weather, fetch_hourly_forecast,
    fetch_daily_forecast, fetch_recent_history, compute_checksum,
)

logger = logging.getLogger("wins_agro.weather_operations")

WEATHER_CACHE_CURRENT_MINUTES = int(os.getenv("WEATHER_CACHE_CURRENT_MINUTES", "20"))
WEATHER_CACHE_HOURLY_MINUTES = int(os.getenv("WEATHER_CACHE_HOURLY_MINUTES", "45"))
WEATHER_CACHE_DAILY_MINUTES = int(os.getenv("WEATHER_CACHE_DAILY_MINUTES", "120"))
WEATHER_FALLBACK_MAX_AGE_HOURS = int(os.getenv("WEATHER_FALLBACK_MAX_AGE_HOURS", "12"))

_refresh_cooldown: dict[int, float] = {}
COOLDOWN_SECONDS = 60


class WeatherService:
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

    def _require_write(self, ctx, auth):
        auth.require_organization_role(ctx, Permission.FARM_OPERATE)

    def _require_profile(self, farm_id: int) -> dict:
        """Exige perfil configurado (operações de escrita / refresh)."""
        profile = self.repository.get_profile(farm_id)
        if not profile:
            raise ForbiddenError("weather_profile_not_configured")
        return profile

    @staticmethod
    def _not_configured_current() -> dict:
        """Leitura autorizada sem perfil: estado controlado (nunca 403)."""
        return {
            "temperature_c": None,
            "feels_like_c": None,
            "humidity_pct": None,
            "precipitation_mm": None,
            "wind_kmh": None,
            "gust_kmh": None,
            "wind_direction_deg": None,
            "cloud_cover_pct": None,
            "condition_code": None,
            "condition_description": None,
            "observation_time": None,
            "fetched_at": None,
            "expires_at": None,
            "source": "none",
            "cache_status": CacheStatus.UNAVAILABLE.value,
            "stale": True,
            "age_minutes": 0.0,
            "provider": "",
            "normalization_version": NORMALIZATION_VERSION,
            "status": WeatherStatus.NOT_CONFIGURED.value,
            "status_label": WEATHER_STATUS_LABELS.get(
                WeatherStatus.NOT_CONFIGURED, WeatherStatus.NOT_CONFIGURED.value
            ),
        }

    @staticmethod
    def _not_configured_series() -> dict:
        return {
            "items": [],
            "fetched_at": None,
            "expires_at": None,
            "source": "none",
            "cache_status": CacheStatus.UNAVAILABLE.value,
            "stale": True,
            "age_minutes": 0.0,
            "provider": "",
            "status": WeatherStatus.NOT_CONFIGURED.value,
            "status_label": WEATHER_STATUS_LABELS.get(
                WeatherStatus.NOT_CONFIGURED, WeatherStatus.NOT_CONFIGURED.value
            ),
        }

    @staticmethod
    def _not_configured_rainfall() -> dict:
        return {
            "items": [],
            "total_mm": 0,
            "fetched_at": None,
            "source": "none",
            "cache_status": CacheStatus.UNAVAILABLE.value,
            "stale": True,
            "age_minutes": 0.0,
            "provider": "",
            "status": WeatherStatus.NOT_CONFIGURED.value,
            "status_label": WEATHER_STATUS_LABELS.get(
                WeatherStatus.NOT_CONFIGURED, WeatherStatus.NOT_CONFIGURED.value
            ),
        }

    def _get_or_fetch(self, farm_id: int, snapshot_type: str, fetch_fn, cache_minutes: int):
        """Retorna (snapshot, cache_status, age, is_fallback) ou (None, 'not_configured', 0, False)."""
        now = datetime.now(timezone.utc)
        cached = self.repository.get_fresh_snapshot(farm_id, snapshot_type)
        if cached:
            cache_status, age = check_freshness(cached["fetched_at"], now)
            if cache_status in (CacheStatus.FRESH.value, CacheStatus.STALE.value):
                return cached, cache_status, age, False
            if cache_status == CacheStatus.FALLBACK.value and age <= WEATHER_FALLBACK_MAX_AGE_HOURS * 60:
                return cached, CacheStatus.FALLBACK.value, age, True

        profile = self.repository.get_profile(farm_id)
        if not profile:
            # Leitura autorizada sem perfil: não usar ForbiddenError (evita 403 indevido).
            return None, WeatherStatus.NOT_CONFIGURED.value, 0.0, False
        try:
            raw = fetch_fn(profile["latitude"], profile["longitude"], profile.get("timezone", "auto"))
        except WeatherProviderError as e:
            if cached and age_minutes(cached["fetched_at"], now) <= WEATHER_FALLBACK_MAX_AGE_HOURS * 60:
                return cached, CacheStatus.FALLBACK.value, age_minutes(cached["fetched_at"], now), True
            raise ForbiddenError("weather_provider_error")

        fetched_at = now
        expires_at = compute_cache_expires_at(snapshot_type, fetched_at, cache_minutes)
        payload = raw.get(snapshot_type.replace("_forecast", "").replace("recent_", ""), raw.get("current", raw.get("hourly", raw.get("daily", {}))))
        checksum = compute_checksum(payload)
        snapshot_data = {
            "public_id": uuid4(),
            "organization_id": profile["organization_id"],
            "farm_id": farm_id,
            "profile_id": profile["id"],
            "snapshot_type": snapshot_type,
            "period_start": fetched_at,
            "period_end": expires_at,
            "payload_normalized": payload,
            "provider": profile["provider"],
            "provider_reference": raw.get("raw_checksum"),
            "normalization_version": NORMALIZATION_VERSION,
            "fetched_at": fetched_at,
            "expires_at": expires_at,
            "stale_after": fetched_at + timedelta(minutes=cache_minutes),
            "checksum": checksum,
        }
        self.repository.save_snapshot(snapshot_data)
        return snapshot_data, CacheStatus.FRESH.value, 0.0, False

    def get_profile(self, *, subject, farm_public_id, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        profile = self.repository.get_profile(farm["id"])
        if not profile:
            return {
                "status": WeatherStatus.NOT_CONFIGURED.value,
                "status_label": WeatherStatus.NOT_CONFIGURED.value,
            }
        return self._profile_response(profile)

    def create_or_update_profile(self, *, subject, farm_public_id, payload, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        self._require_write(ctx, auth)
        existing = self.repository.get_profile(farm["id"])
        now = datetime.now(timezone.utc)

        if existing:
            data = {k: v for k, v in payload.items() if v is not None}
            data["request_id"] = request_id
            data["organization_id"] = ctx.organization_id
            data["farm_id"] = farm["id"]
            data["public_id"] = existing["public_id"]
            self.repository.update_profile(existing["id"], data, ctx.user_id)
            if "latitude" in data or "longitude" in data:
                self.repository.invalidate_cache_for_farm(farm["id"])
            profile = self.repository.get_profile(farm["id"])
            return self._profile_response(profile)
        else:
            data = {
                "public_id": uuid4(),
                "organization_id": ctx.organization_id,
                "farm_id": farm["id"],
                "latitude": payload.get("latitude", 0),
                "longitude": payload.get("longitude", 0),
                "timezone": payload.get("timezone", "America/Sao_Paulo"),
                "provider": payload.get("provider", "open-meteo"),
                "enabled": payload.get("enabled", True),
                "refresh_interval_minutes": payload.get("refresh_interval_minutes", 20),
                "forecast_days": payload.get("forecast_days", 7),
                "status": WeatherStatus.ACTIVE.value,
                "notes": payload.get("notes", ""),
                "created_by_user_id": ctx.user_id,
                "request_id": request_id,
            }
            created = self.repository.create_profile(data, ctx.user_id)
            profile = self.repository.get_profile(farm["id"])
            return self._profile_response(profile)

    def get_current(self, *, subject, farm_public_id, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        snapshot, cache_status, age, is_fallback = self._get_or_fetch(
            farm["id"], SnapshotType.CURRENT.value, fetch_current_weather, WEATHER_CACHE_CURRENT_MINUTES)
        if snapshot is None:
            return self._not_configured_current()
        payload = snapshot["payload_normalized"]
        if isinstance(payload, dict) and "current" in payload:
            payload = payload["current"]
        normalized = normalize_weather_condition(payload)
        return {
            **normalized,
            "fetched_at": snapshot["fetched_at"].isoformat() if hasattr(snapshot["fetched_at"], "isoformat") else str(snapshot["fetched_at"]),
            "expires_at": snapshot["expires_at"].isoformat() if hasattr(snapshot["expires_at"], "isoformat") else str(snapshot["expires_at"]),
            "source": "cache" if is_fallback else "provider",
            "cache_status": cache_status,
            "stale": cache_status in (CacheStatus.STALE.value, CacheStatus.FALLBACK.value),
            "age_minutes": age,
            "provider": snapshot.get("provider", "open-meteo"),
            "normalization_version": NORMALIZATION_VERSION,
        }

    def get_hourly_forecast(self, *, subject, farm_public_id, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        snapshot, cache_status, age, is_fallback = self._get_or_fetch(
            farm["id"], SnapshotType.HOURLY_FORECAST.value, fetch_hourly_forecast, WEATHER_CACHE_HOURLY_MINUTES)
        if snapshot is None:
            return self._not_configured_series()
        payload = snapshot["payload_normalized"]
        if isinstance(payload, dict) and "hourly" in payload:
            payload = payload["hourly"]
        items = payload if isinstance(payload, list) else []
        return {
            "items": items[:72],
            "fetched_at": snapshot["fetched_at"].isoformat() if hasattr(snapshot["fetched_at"], "isoformat") else str(snapshot["fetched_at"]),
            "expires_at": snapshot["expires_at"].isoformat() if hasattr(snapshot["expires_at"], "isoformat") else str(snapshot["expires_at"]),
            "source": "cache" if is_fallback else "provider",
            "cache_status": cache_status,
            "stale": cache_status in (CacheStatus.STALE.value, CacheStatus.FALLBACK.value),
            "age_minutes": age,
            "provider": snapshot.get("provider", "open-meteo"),
        }

    def get_daily_forecast(self, *, subject, farm_public_id, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        snapshot, cache_status, age, is_fallback = self._get_or_fetch(
            farm["id"], SnapshotType.DAILY_FORECAST.value, fetch_daily_forecast, WEATHER_CACHE_DAILY_MINUTES)
        if snapshot is None:
            return self._not_configured_series()
        payload = snapshot["payload_normalized"]
        if isinstance(payload, dict) and "daily" in payload:
            payload = payload["daily"]
        items = payload if isinstance(payload, list) else []
        return {
            "items": items[:16],
            "fetched_at": snapshot["fetched_at"].isoformat() if hasattr(snapshot["fetched_at"], "isoformat") else str(snapshot["fetched_at"]),
            "expires_at": snapshot["expires_at"].isoformat() if hasattr(snapshot["expires_at"], "isoformat") else str(snapshot["expires_at"]),
            "source": "cache" if is_fallback else "provider",
            "cache_status": cache_status,
            "stale": cache_status in (CacheStatus.STALE.value, CacheStatus.FALLBACK.value),
            "age_minutes": age,
            "provider": snapshot.get("provider", "open-meteo"),
        }

    def get_recent_rainfall(self, *, subject, farm_public_id, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        snapshot, cache_status, age, is_fallback = self._get_or_fetch(
            farm["id"], SnapshotType.RECENT_HISTORY.value, fetch_recent_history, WEATHER_CACHE_DAILY_MINUTES)
        if snapshot is None:
            return self._not_configured_rainfall()
        payload = snapshot["payload_normalized"]
        if isinstance(payload, dict) and "daily" in payload:
            payload = payload["daily"]
        items = payload if isinstance(payload, list) else []
        total = sum(float(i.get("precipitation_sum_mm") or 0) for i in items)
        return {
            "items": items,
            "total_mm": round(total, 2),
            "fetched_at": snapshot["fetched_at"].isoformat() if hasattr(snapshot["fetched_at"], "isoformat") else str(snapshot["fetched_at"]),
            "source": "cache" if is_fallback else "provider",
            "cache_status": cache_status,
            "stale": cache_status in (CacheStatus.STALE.value, CacheStatus.FALLBACK.value),
            "age_minutes": age,
            "provider": snapshot.get("provider", "open-meteo"),
        }

    def refresh(self, *, subject, farm_public_id, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        self._require_write(ctx, auth)
        # Perfil ausente: falha de negócio antes do cooldown (não misturar com refresh_cooldown).
        self._require_profile(farm["id"])
        import time
        now_ts = time.time()
        last = _refresh_cooldown.get(farm["id"], 0)
        if now_ts - last < COOLDOWN_SECONDS:
            # Código previsto pelo contrato: ForbiddenError refresh_cooldown (≠ role_denied).
            raise ForbiddenError("refresh_cooldown")
        _refresh_cooldown[farm["id"]] = now_ts
        self.repository.invalidate_cache_for_farm(farm["id"])
        current = self.get_current(subject=subject, farm_public_id=farm_public_id, request_id=request_id)
        return {"status": "refreshed", "current": current}

    def get_dashboard(self, *, subject, farm_public_id, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        now = datetime.now(timezone.utc)
        result = {
            "current": None,
            "forecast_summary": [],
            "recent_rainfall_mm": 0,
            "upcoming_favorable_windows": [],
            "risks": [],
            "integration_status": WeatherStatus.NOT_CONFIGURED.value,
            "last_updated": None,
            "provider": "",
            "source": "provider",
            "cache_status": CacheStatus.UNAVAILABLE.value,
        }
        profile = self.repository.get_profile(farm["id"])
        if not profile:
            return result
        result["integration_status"] = profile.get("status", WeatherStatus.ACTIVE.value)
        result["provider"] = profile.get("provider", "open-meteo")
        try:
            current_snap = self.repository.get_fresh_snapshot(farm["id"], SnapshotType.CURRENT.value)
            if current_snap:
                payload = current_snap["payload_normalized"]
                if isinstance(payload, dict) and "current" in payload:
                    payload = payload["current"]
                result["current"] = normalize_weather_condition(payload)
                result["last_updated"] = current_snap["fetched_at"].isoformat() if hasattr(current_snap["fetched_at"], "isoformat") else str(current_snap["fetched_at"])
                cache_status, age = check_freshness(current_snap["fetched_at"], now)
                result["cache_status"] = cache_status
        except Exception:
            logger.warning("dashboard_current_failed farm=%d", farm["id"])
        try:
            daily_snap = self.repository.get_fresh_snapshot(farm["id"], SnapshotType.DAILY_FORECAST.value)
            if daily_snap:
                payload = daily_snap["payload_normalized"]
                if isinstance(payload, dict) and "daily" in payload:
                    payload = payload["daily"]
                result["forecast_summary"] = (payload if isinstance(payload, list) else [])[:7]
        except Exception:
            pass
        try:
            history_snap = self.repository.get_fresh_snapshot(farm["id"], SnapshotType.RECENT_HISTORY.value)
            if history_snap:
                payload = history_snap["payload_normalized"]
                if isinstance(payload, dict) and "daily" in payload:
                    payload = payload["daily"]
                items = payload if isinstance(payload, list) else []
                result["recent_rainfall_mm"] = round(sum(float(i.get("precipitation_sum_mm") or 0) for i in items), 2)
        except Exception:
            pass
        try:
            windows = self.get_operational_windows(subject=subject, farm_public_id=farm_public_id, request_id=request_id)
            favorable = [w for w in windows.get("items", []) if w.get("classification") == "favorable"]
            result["upcoming_favorable_windows"] = favorable[:3]
            for w in windows.get("items", []):
                if w.get("classification") == "unfavorable":
                    for r in w.get("risk_factors", []):
                        result["risks"].append(r.get("description", ""))
        except Exception:
            pass
        return result

    def get_operational_windows(self, *, subject, farm_public_id, request_id,
                                window_type: str | None = None, start: datetime | None = None,
                                end: datetime | None = None) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        now = datetime.now(timezone.utc)
        profile = self.repository.get_profile(farm["id"])
        if not profile:
            return {"items": [], "evaluated_at": now.isoformat(), "rule_version": FORMULA_VERSION, "source": "none", "cache_status": CacheStatus.UNAVAILABLE.value}
        hourly_snap = self.repository.get_fresh_snapshot(farm["id"], SnapshotType.HOURLY_FORECAST.value)
        if not hourly_snap:
            hourly_snap = self.repository.get_any_snapshot(farm["id"], SnapshotType.HOURLY_FORECAST.value)
        if not hourly_snap:
            return {"items": [], "evaluated_at": now.isoformat(), "rule_version": FORMULA_VERSION, "source": "none", "cache_status": CacheStatus.UNAVAILABLE.value}
        payload = hourly_snap["payload_normalized"]
        if isinstance(payload, dict) and "hourly" in payload:
            payload = payload["hourly"]
        hourly_data = payload if isinstance(payload, list) else []
        cache_status, age = check_freshness(hourly_snap["fetched_at"], now)
        window_types_to_compute = [window_type] if window_type else [wt.value for wt in WindowType]
        items = []
        for wt in window_types_to_compute:
            best_window = None
            best_score = -1
            for i in range(len(hourly_data) - 1):
                h1 = hourly_data[i]
                h2 = hourly_data[i + 1] if i + 1 < len(hourly_data) else h1
                score, classification, positive, risks = compute_window_score(
                    wt,
                    precipitation_mm=h1.get("precipitation_mm"),
                    precipitation_probability=h1.get("precipitation_probability"),
                    wind_kmh=h1.get("wind_kmh"),
                    gust_kmh=h1.get("gust_kmh"),
                    temperature_c=h1.get("temperature_c"),
                    feels_like_c=None,
                    has_severe_alert=False,
                    data_age_minutes=age,
                )
                if score > best_score:
                    best_score = score
                    period_start = datetime.fromisoformat(h1["timestamp"]) if isinstance(h1.get("timestamp"), str) else now
                    period_end = datetime.fromisoformat(h2["timestamp"]) if isinstance(h2.get("timestamp"), str) else now + timedelta(hours=1)
                    best_window = build_window_response(
                        wt, period_start, period_end, score, classification,
                        positive, risks, [str(hourly_snap.get("public_id", ""))],
                        FORMULA_VERSION, now, hourly_snap["fetched_at"],
                    )
            if best_window:
                items.append(best_window)
        items.sort(key=lambda w: w["score"], reverse=True)
        return {"items": items, "evaluated_at": now.isoformat(), "rule_version": FORMULA_VERSION, "source": "provider", "cache_status": cache_status}

    def save_evaluation(self, *, subject, farm_public_id, payload, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        self._require_write(ctx, auth)
        import json
        now = datetime.now(timezone.utc)
        plan_id = None
        if payload.get("related_harvest_plan_uuid"):
            plan = self.repository.find_harvest_plan_by_uuid(UUID(str(payload["related_harvest_plan_uuid"])), farm["id"])
            if plan:
                plan_id = plan["id"]
        data = {
            "public_id": uuid4(),
            "organization_id": ctx.organization_id,
            "farm_id": farm["id"],
            "window_type": payload["window_type"],
            "period_start": payload["period_start"],
            "period_end": payload["period_end"],
            "score": payload["score"],
            "classification": payload["classification"],
            "positive_factors": json.dumps(payload.get("positive_factors", [])),
            "risk_factors": json.dumps(payload.get("risk_factors", [])),
            "data_snapshot_ids": json.dumps([]),
            "rule_version": FORMULA_VERSION,
            "evaluated_at": now,
            "expires_at": now + timedelta(hours=24),
            "related_harvest_plan_id": plan_id,
            "created_by_user_id": ctx.user_id,
        }
        created = self.repository.save_evaluation(data)
        return {"public_id": str(created["public_id"]), "status": "saved"}

    def list_evaluations(self, *, subject, farm_public_id, request_id,
                         limit: int = 25, offset: int = 0, window_type: str | None = None) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        items = self.repository.list_evaluations(farm["id"], limit, offset, window_type)
        total = self.repository.count_evaluations(farm["id"], window_type)
        return {"items": items, "total": total}

    def get_harvest_weather_context(self, *, subject, farm_public_id, plan_uuid, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        plan = self.repository.find_harvest_plan_by_uuid(UUID(str(plan_uuid)), farm["id"])
        if not plan:
            raise HiddenResourceError()
        now = datetime.now(timezone.utc)
        daily_snap = self.repository.get_any_snapshot(farm["id"], SnapshotType.DAILY_FORECAST.value)
        forecast_items = []
        expected_precip = 0.0
        max_probability = 0.0
        if daily_snap:
            payload = daily_snap["payload_normalized"]
            if isinstance(payload, dict) and "daily" in payload:
                payload = payload["daily"]
            items = payload if isinstance(payload, list) else []
            plan_start = plan["expected_start_date"]
            plan_end = plan["expected_end_date"]
            for item in items:
                d_str = item.get("date")
                if d_str:
                    try:
                        d = datetime.strptime(str(d_str), "%Y-%m-%d").date()
                    except ValueError:
                        continue
                    if plan_start <= d <= plan_end:
                        forecast_items.append(item)
                        expected_precip += float(item.get("precipitation_sum_mm") or 0)
                        prob = float(item.get("precipitation_probability_max") or 0)
                        if prob > max_probability:
                            max_probability = prob
        risk_factors = []
        warnings = []
        if expected_precip > 5:
            risk_factors.append(f"Precipitação prevista elevada ({round(expected_precip, 1)} mm)")
        if max_probability > 60:
            risk_factors.append(f"Alta probabilidade de chuva ({round(max_probability)}%)")
        if not daily_snap:
            warnings.append("Dados de previsão indisponíveis")
        return {
            "plan_uuid": str(plan["public_id"]),
            "plan_name": plan["name"],
            "plan_start_date": str(plan["expected_start_date"]),
            "plan_end_date": str(plan["expected_end_date"]),
            "forecast_during_plan": forecast_items,
            "expected_precipitation_mm": round(expected_precip, 2),
            "max_precipitation_probability": round(max_probability, 1),
            "cut_score": None,
            "ensiling_score": None,
            "risk_factors": risk_factors,
            "data_freshness": daily_snap["fetched_at"].isoformat() if daily_snap and hasattr(daily_snap["fetched_at"], "isoformat") else "unavailable",
            "warnings": warnings,
        }

    def get_pasture_weather_context(self, *, subject, farm_public_id, request_id) -> dict:
        ctx, farm, auth = self._context(subject, farm_public_id, request_id)
        now = datetime.now(timezone.utc)
        result = {
            "recent_rainfall_mm": 0,
            "forecast_rainfall_mm": 0,
            "current_temperature_c": None,
            "heat_status": "normal",
            "last_updated": None,
            "measurement_stale_days": None,
            "warnings": [],
        }
        try:
            history_snap = self.repository.get_any_snapshot(farm["id"], SnapshotType.RECENT_HISTORY.value)
            if history_snap:
                payload = history_snap["payload_normalized"]
                if isinstance(payload, dict) and "daily" in payload:
                    payload = payload["daily"]
                items = payload if isinstance(payload, list) else []
                result["recent_rainfall_mm"] = round(sum(float(i.get("precipitation_sum_mm") or 0) for i in items), 2)
        except Exception:
            pass
        try:
            daily_snap = self.repository.get_any_snapshot(farm["id"], SnapshotType.DAILY_FORECAST.value)
            if daily_snap:
                payload = daily_snap["payload_normalized"]
                if isinstance(payload, dict) and "daily" in payload:
                    payload = payload["daily"]
                items = payload if isinstance(payload, list) else []
                result["forecast_rainfall_mm"] = round(sum(float(i.get("precipitation_sum_mm") or 0) for i in items[:3]), 2)
        except Exception:
            pass
        try:
            current_snap = self.repository.get_any_snapshot(farm["id"], SnapshotType.CURRENT.value)
            if current_snap:
                payload = current_snap["payload_normalized"]
                if isinstance(payload, dict) and "current" in payload:
                    payload = payload["current"]
                norm = normalize_weather_condition(payload)
                result["current_temperature_c"] = norm.get("temperature_c")
                result["heat_status"] = classify_temperature(norm.get("temperature_c"), norm.get("feels_like_c"))
                result["last_updated"] = current_snap["fetched_at"].isoformat() if hasattr(current_snap["fetched_at"], "isoformat") else str(current_snap["fetched_at"])
        except Exception:
            pass
        result["warnings"].append("Os dados climáticos servem como contexto. Registre uma nova medição de campo antes de atualizar a disponibilidade de matéria seca.")
        return result

    def _profile_response(self, p: dict) -> dict:
        now = datetime.now(timezone.utc)
        status = p.get("status", WeatherStatus.ACTIVE.value)
        if p.get("last_error_at") and not p.get("last_success_at"):
            status = WeatherStatus.ERROR.value
        elif p.get("last_success_at"):
            if hasattr(p["last_success_at"], "timestamp"):
                age_hrs = (now - p["last_success_at"]).total_seconds() / 3600
                if age_hrs > 6:
                    status = WeatherStatus.STALE.value
        return {
            "public_id": str(p["public_id"]),
            "latitude": float(p["latitude"]),
            "longitude": float(p["longitude"]),
            "timezone": p.get("timezone", "America/Sao_Paulo"),
            "provider": p.get("provider", "open-meteo"),
            "enabled": p.get("enabled", True),
            "refresh_interval_minutes": p.get("refresh_interval_minutes", 20),
            "forecast_days": p.get("forecast_days", 7),
            "status": status,
            "status_label": WeatherStatus(status).value if status in [s.value for s in WeatherStatus] else status,
            "last_attempt_at": p.get("last_attempt_at").isoformat() if p.get("last_attempt_at") and hasattr(p["last_attempt_at"], "isoformat") else None,
            "last_success_at": p.get("last_success_at").isoformat() if p.get("last_success_at") and hasattr(p["last_success_at"], "isoformat") else None,
            "last_error_at": p.get("last_error_at").isoformat() if p.get("last_error_at") and hasattr(p["last_error_at"], "isoformat") else None,
            "last_error_code": p.get("last_error_code"),
            "notes": p.get("notes", ""),
            "created_at": p["created_at"].isoformat() if hasattr(p["created_at"], "isoformat") else str(p["created_at"]),
            "updated_at": p["updated_at"].isoformat() if hasattr(p["updated_at"], "isoformat") else str(p["updated_at"]),
        }


def age_minutes(fetched_at, now):
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return (now - fetched_at).total_seconds() / 60.0
