"""Testes de Service do módulo de Clima e Janelas Operacionais."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from core.authorization import ForbiddenError
from domain.foundation import RecordStatus, UserRecord
from domain.weather_operations import (
    WeatherStatus, CacheStatus, SnapshotType, FORMULA_VERSION,
    normalize_weather_condition,
)
from services.weather_operations import WeatherService, age_minutes, _refresh_cooldown, COOLDOWN_SECONDS


def _user(subject="test@test.com"):
    return UserRecord(1, uuid4(), subject, RecordStatus.ACTIVE)


def _auth_repo(subject="test@test.com"):
    repo = MagicMock()
    repo.find_user_by_subject.return_value = _user(subject)
    return repo


def _farm_membership(repo, role="owner"):
    repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
    repo.find_membership.return_value = {
        "id": 1, "public_id": str(uuid4()), "organization_id": 1,
        "role": role, "status": "active",
    }
    if role not in {"owner", "admin"}:
        repo.find_farm_access.return_value = {
            "id": 1, "access_level": "read" if role == "viewer" else "operate", "status": "active",
        }
    return repo


@pytest.fixture
def mock_repo():
    return _farm_membership(MagicMock(), role="owner")


@pytest.fixture
def mock_auth_repo():
    return _auth_repo()


@pytest.fixture
def service(mock_repo, mock_auth_repo):
    return WeatherService(mock_repo, mock_auth_repo)


class TestAgeMinutes:
    def test_age_minutes(self):
        now = datetime.now(timezone.utc)
        fetched = now - timedelta(minutes=30)
        age = age_minutes(fetched, now)
        assert abs(age - 30) < 1


class TestServiceProfile:
    def test_get_profile_not_configured(self, service, mock_repo):
        mock_repo.get_profile.return_value = None
        result = service.get_profile(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["status"] == WeatherStatus.NOT_CONFIGURED.value

    def test_get_profile_configured(self, service, mock_repo):
        mock_repo.get_profile.return_value = {
            "id": 1, "public_id": uuid4(), "latitude": -12.64, "longitude": -55.72,
            "timezone": "America/Cuiaba", "provider": "open-meteo", "enabled": True,
            "refresh_interval_minutes": 20, "forecast_days": 7,
            "status": "active", "notes": "test",
            "last_attempt_at": None, "last_success_at": None,
            "last_error_at": None, "last_error_code": None,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }
        result = service.get_profile(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["latitude"] == -12.64


class TestServiceCache:
    def test_fresh_cache_used(self, service, mock_repo):
        mock_repo.get_profile.return_value = {
            "id": 1, "public_id": uuid4(), "latitude": -12.64, "longitude": -55.72,
            "timezone": "America/Cuiaba", "provider": "open-meteo", "enabled": True,
            "refresh_interval_minutes": 20, "forecast_days": 7,
            "status": "active", "notes": "",
            "last_attempt_at": None, "last_success_at": None,
            "last_error_at": None, "last_error_code": None,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }
        now = datetime.now(timezone.utc)
        mock_repo.get_fresh_snapshot.return_value = {
            "id": 1, "public_id": uuid4(),
            "snapshot_type": "current",
            "fetched_at": now - timedelta(minutes=5),
            "expires_at": now + timedelta(minutes=15),
            "payload_normalized": {"temperature_c": 25, "humidity_pct": 60},
            "provider": "open-meteo",
        }
        result = service.get_current(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["temperature_c"] == 25
        assert result["cache_status"] == CacheStatus.FRESH.value

    def test_stale_cache_returns_stale_status(self, service, mock_repo):
        mock_repo.get_profile.return_value = {
            "id": 1, "public_id": uuid4(), "latitude": -12.64, "longitude": -55.72,
            "timezone": "America/Cuiaba", "provider": "open-meteo", "enabled": True,
            "refresh_interval_minutes": 20, "forecast_days": 7,
            "status": "active", "notes": "",
            "last_attempt_at": None, "last_success_at": None,
            "last_error_at": None, "last_error_code": None,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }
        now = datetime.now(timezone.utc)
        mock_repo.get_fresh_snapshot.return_value = {
            "id": 1, "public_id": uuid4(),
            "snapshot_type": "current",
            "fetched_at": now - timedelta(minutes=60),
            "expires_at": now - timedelta(minutes=40),
            "payload_normalized": {"temperature_c": 25},
            "provider": "open-meteo",
        }
        result = service.get_current(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["temperature_c"] == 25
        assert result["cache_status"] == CacheStatus.STALE.value

    def test_fallback_cache_when_age_in_fallback_window(self, service, mock_repo):
        mock_repo.get_profile.return_value = {
            "id": 1, "public_id": uuid4(), "latitude": -12.64, "longitude": -55.72,
            "timezone": "America/Cuiaba", "provider": "open-meteo", "enabled": True,
            "refresh_interval_minutes": 20, "forecast_days": 7,
            "status": "active", "notes": "",
            "last_attempt_at": None, "last_success_at": None,
            "last_error_at": None, "last_error_code": None,
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }
        now = datetime.now(timezone.utc)
        # 200 min → FALLBACK (entre 180 e 720); _get_or_fetch marca is_fallback=True
        mock_repo.get_fresh_snapshot.return_value = {
            "id": 1, "public_id": uuid4(),
            "snapshot_type": "current",
            "fetched_at": now - timedelta(minutes=200),
            "expires_at": now - timedelta(minutes=180),
            "payload_normalized": {"temperature_c": 25},
            "provider": "open-meteo",
        }
        result = service.get_current(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["source"] == "cache"
        assert result["cache_status"] == CacheStatus.FALLBACK.value


class TestServiceWindows:
    def test_no_profile_returns_empty(self, service, mock_repo):
        mock_repo.get_profile.return_value = None
        result = service.get_operational_windows(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["items"] == []

    def test_windows_computed_from_hourly(self, service, mock_repo):
        mock_repo.get_profile.return_value = {
            "id": 1, "public_id": uuid4(), "latitude": -12.64, "longitude": -55.72,
            "timezone": "America/Cuiaba", "provider": "open-meteo", "enabled": True,
            "refresh_interval_minutes": 20, "forecast_days": 7,
            "status": "active", "notes": "",
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }
        now = datetime.now(timezone.utc)
        mock_repo.get_fresh_snapshot.return_value = {
            "id": 1, "public_id": uuid4(),
            "snapshot_type": "hourly_forecast",
            "fetched_at": now - timedelta(minutes=5),
            "expires_at": now + timedelta(minutes=40),
            "payload_normalized": {
                "hourly": [
                    {"timestamp": (now + timedelta(hours=i)).isoformat(),
                     "temperature_c": 25 + i, "precipitation_mm": 0 if i < 3 else 5,
                     "precipitation_probability": 10 if i < 3 else 80,
                     "wind_kmh": 10, "gust_kmh": 15}
                    for i in range(6)
                ]
            },
            "provider": "open-meteo",
        }
        result = service.get_operational_windows(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert len(result["items"]) > 0
        assert all("score" in w for w in result["items"])


class TestAuthorizedReadNotConfigured:
    """Contrato: leitura autorizada sem perfil → estado controlado, nunca 403."""

    def test_current_not_configured_no_forbidden(self, service, mock_repo):
        mock_repo.get_profile.return_value = None
        mock_repo.get_fresh_snapshot.return_value = None
        result = service.get_current(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["status"] == WeatherStatus.NOT_CONFIGURED.value
        assert result["cache_status"] == CacheStatus.UNAVAILABLE.value
        assert result["temperature_c"] is None

    def test_hourly_not_configured_no_forbidden(self, service, mock_repo):
        mock_repo.get_profile.return_value = None
        mock_repo.get_fresh_snapshot.return_value = None
        result = service.get_hourly_forecast(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["status"] == WeatherStatus.NOT_CONFIGURED.value
        assert result["items"] == []

    def test_daily_not_configured_no_forbidden(self, service, mock_repo):
        mock_repo.get_profile.return_value = None
        mock_repo.get_fresh_snapshot.return_value = None
        result = service.get_daily_forecast(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["status"] == WeatherStatus.NOT_CONFIGURED.value
        assert result["items"] == []

    def test_rainfall_not_configured_no_forbidden(self, service, mock_repo):
        mock_repo.get_profile.return_value = None
        mock_repo.get_fresh_snapshot.return_value = None
        result = service.get_recent_rainfall(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["status"] == WeatherStatus.NOT_CONFIGURED.value
        assert result["total_mm"] == 0


class TestRefreshCooldown:
    def test_refresh_without_profile_does_not_set_cooldown(self, service, mock_repo):
        mock_repo.get_profile.return_value = None
        _refresh_cooldown.clear()
        with pytest.raises(ForbiddenError) as exc:
            service.refresh(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert exc.value.code == "weather_profile_not_configured"
        assert 1 not in _refresh_cooldown

    def test_refresh_cooldown_code_distinct_from_role_denied(self, service, mock_repo):
        mock_repo.get_profile.return_value = {
            "id": 1, "public_id": uuid4(), "latitude": -12.64, "longitude": -55.72,
            "timezone": "America/Cuiaba", "provider": "open-meteo", "enabled": True,
            "refresh_interval_minutes": 20, "forecast_days": 7,
            "status": "active", "notes": "",
            "created_at": datetime.now(timezone.utc), "updated_at": datetime.now(timezone.utc),
        }
        now = datetime.now(timezone.utc)
        mock_repo.get_fresh_snapshot.return_value = {
            "id": 1, "public_id": uuid4(),
            "snapshot_type": "current",
            "fetched_at": now - timedelta(minutes=5),
            "expires_at": now + timedelta(minutes=15),
            "payload_normalized": {"temperature_c": 25},
            "provider": "open-meteo",
        }
        _refresh_cooldown.clear()
        farm_id = 1
        first = service.refresh(subject="test@test.com", farm_public_id=uuid4(), request_id="req1")
        assert first["status"] == "refreshed"
        with pytest.raises(ForbiddenError) as exc:
            service.refresh(subject="test@test.com", farm_public_id=uuid4(), request_id="req2")
        assert exc.value.code == "refresh_cooldown"
        assert exc.value.code != "role_denied"
        assert farm_id in _refresh_cooldown
