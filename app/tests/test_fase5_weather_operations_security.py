"""Testes de Segurança do módulo de Clima e Janelas Operacionais."""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from core.authorization import HiddenResourceError, ForbiddenError
from domain.foundation import RecordStatus, UserRecord
from domain.weather_operations import WeatherStatus, CacheStatus
from services.weather_operations import WeatherService


def _user(subject="user@test.com"):
    return UserRecord(1, uuid4(), subject, RecordStatus.ACTIVE)


def _auth_repo(subject="user@test.com"):
    repo = MagicMock()
    repo.find_user_by_subject.return_value = _user(subject)
    return repo


def _wire_farm(repo, role="owner", access_level="operate"):
    repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
    repo.find_membership.return_value = {
        "id": 1, "public_id": str(uuid4()), "organization_id": 1,
        "role": role, "status": "active",
    }
    if role not in {"owner", "admin"}:
        repo.find_farm_access.return_value = {
            "id": 1, "access_level": access_level, "status": "active",
        }
    return repo


@pytest.fixture
def mock_repo():
    return _wire_farm(MagicMock(), role="owner")


@pytest.fixture
def mock_auth_repo():
    return _auth_repo()


@pytest.fixture
def service(mock_repo, mock_auth_repo):
    return WeatherService(mock_repo, mock_auth_repo)


class TestFeatureFlag:
    def test_feature_disabled_returns_404(self, monkeypatch):
        pytest.importorskip("fastapi")
        monkeypatch.setenv("ENABLE_WEATHER_OPERATIONS", "false")
        import importlib
        import routers.weather_operations as module
        module = importlib.reload(module)
        with pytest.raises(Exception) as exc_info:
            module._check_feature()
        assert exc_info.value.status_code == 404

    def test_feature_enabled_passes(self, monkeypatch):
        pytest.importorskip("fastapi")
        monkeypatch.setenv("ENABLE_WEATHER_OPERATIONS", "true")
        import importlib
        import routers.weather_operations as module
        module = importlib.reload(module)
        module._check_feature()


class TestCrossTenant:
    def test_cross_tenant_farm_hidden(self, service, mock_repo):
        mock_repo.find_farm.return_value = None
        with pytest.raises(HiddenResourceError):
            service.get_profile(subject="user@test.com", farm_public_id=uuid4(), request_id="req1")


class TestViewerReadOnly:
    def test_viewer_can_read_profile_and_current(self, mock_repo, mock_auth_repo):
        _wire_farm(mock_repo, role="viewer", access_level="read")
        mock_auth_repo.find_user_by_subject.return_value = _user("viewer@test.com")
        mock_repo.get_profile.return_value = None
        mock_repo.get_fresh_snapshot.return_value = None
        service = WeatherService(mock_repo, mock_auth_repo)
        farm = uuid4()
        profile = service.get_profile(subject="viewer@test.com", farm_public_id=farm, request_id="req1")
        current = service.get_current(subject="viewer@test.com", farm_public_id=farm, request_id="req1")
        assert profile["status"] == WeatherStatus.NOT_CONFIGURED.value
        assert current["status"] == WeatherStatus.NOT_CONFIGURED.value
        assert current["cache_status"] == CacheStatus.UNAVAILABLE.value

    def test_viewer_cannot_update_profile(self, mock_repo, mock_auth_repo):
        _wire_farm(mock_repo, role="viewer", access_level="read")
        mock_auth_repo.find_user_by_subject.return_value = _user("viewer@test.com")
        service = WeatherService(mock_repo, mock_auth_repo)
        with pytest.raises(ForbiddenError) as exc:
            service.create_or_update_profile(
                subject="viewer@test.com", farm_public_id=uuid4(),
                payload={"latitude": -12.64, "longitude": -55.72}, request_id="req1")
        assert exc.value.code == "role_denied"

    def test_viewer_cannot_refresh(self, mock_repo, mock_auth_repo):
        _wire_farm(mock_repo, role="viewer", access_level="read")
        mock_auth_repo.find_user_by_subject.return_value = _user("viewer@test.com")
        mock_repo.get_profile.return_value = {
            "id": 1, "public_id": uuid4(), "latitude": -12.64, "longitude": -55.72,
        }
        service = WeatherService(mock_repo, mock_auth_repo)
        with pytest.raises(ForbiddenError) as exc:
            service.refresh(subject="viewer@test.com", farm_public_id=uuid4(), request_id="req1")
        assert exc.value.code == "role_denied"

    def test_viewer_cannot_save_evaluation(self, mock_repo, mock_auth_repo):
        _wire_farm(mock_repo, role="viewer", access_level="read")
        mock_auth_repo.find_user_by_subject.return_value = _user("viewer@test.com")
        service = WeatherService(mock_repo, mock_auth_repo)
        with pytest.raises(ForbiddenError) as exc:
            service.save_evaluation(
                subject="viewer@test.com", farm_public_id=uuid4(),
                payload={
                    "window_type": "harvest_cut",
                    "period_start": "2026-07-14T00:00:00+00:00",
                    "period_end": "2026-07-14T06:00:00+00:00",
                    "score": 80,
                    "classification": "favorable",
                },
                request_id="req1",
            )
        assert exc.value.code == "role_denied"


class TestMembershipRevoked:
    def test_revoked_membership_blocked(self, service, mock_repo):
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "revoked",
        }
        with pytest.raises(ForbiddenError):
            service.get_profile(subject="user@test.com", farm_public_id=uuid4(), request_id="req1")


class TestFarmAccessRequired:
    def test_no_farm_access_blocked(self, service, mock_repo):
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "technician", "status": "active",
        }
        mock_repo.find_farm_access.return_value = None
        with pytest.raises(ForbiddenError):
            service.get_profile(subject="tech@test.com", farm_public_id=uuid4(), request_id="req1")


class TestInternalIdsNotExposed:
    def test_profile_response_no_internal_id(self, service, mock_repo):
        mock_repo.get_profile.return_value = {
            "id": 999, "public_id": uuid4(), "latitude": -12.64, "longitude": -55.72,
            "timezone": "America/Cuiaba", "provider": "open-meteo", "enabled": True,
            "refresh_interval_minutes": 20, "forecast_days": 7,
            "status": "active", "notes": "",
            "last_attempt_at": None, "last_success_at": None,
            "last_error_at": None, "last_error_code": None,
            "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            "updated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        }
        result = service.get_profile(subject="user@test.com", farm_public_id=uuid4(), request_id="req1")
        assert "id" not in result or result.get("public_id")
        assert "999" not in str(result)


class TestNoAutomaticChanges:
    def test_weather_does_not_change_paddock(self, service, mock_repo):
        result = service.get_pasture_weather_context(
            subject="user@test.com", farm_public_id=uuid4(), request_id="req1")
        assert "recent_rainfall_mm" in result
        mock_repo.update_paddock_manual_status.assert_not_called()

    def test_weather_does_not_change_harvest_plan(self, service, mock_repo):
        mock_repo.find_harvest_plan_by_uuid.return_value = {
            "id": 1, "public_id": uuid4(), "name": "Test Plan",
            "expected_start_date": "2026-07-20", "expected_end_date": "2026-07-25",
            "status": "planned", "farm_id": 1,
        }
        result = service.get_harvest_weather_context(
            subject="user@test.com", farm_public_id=uuid4(),
            plan_uuid=str(uuid4()), request_id="req1")
        assert "plan_uuid" in result
        mock_repo.update_plan.assert_not_called()
