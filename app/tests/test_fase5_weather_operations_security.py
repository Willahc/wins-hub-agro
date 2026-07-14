"""Testes de Segurança do módulo de Clima e Janelas Operacionais."""
import pytest
from unittest.mock import MagicMock, patch
from uuid import uuid4

from core.authorization import HiddenResourceError, ForbiddenError
from services.weather_operations import WeatherService


@pytest.fixture
def mock_repo():
    return MagicMock()


@pytest.fixture
def mock_auth_repo():
    return MagicMock()


@pytest.fixture
def service(mock_repo, mock_auth_repo):
    return WeatherService(mock_repo, mock_auth_repo)


class TestFeatureFlag:
    def test_feature_disabled_returns_404(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WEATHER_OPERATIONS", "false")
        from routers.weather_operations import _check_feature
        with pytest.raises(Exception) as exc_info:
            _check_feature()
        assert exc_info.value.status_code == 404

    def test_feature_enabled_passes(self, monkeypatch):
        monkeypatch.setenv("ENABLE_WEATHER_OPERATIONS", "true")
        from routers.weather_operations import _check_feature
        _check_feature()


class TestCrossTenant:
    def test_cross_tenant_farm_hidden(self, service, mock_repo):
        mock_repo.find_farm.return_value = None
        with pytest.raises(HiddenResourceError):
            service.get_profile(subject="user@test.com", farm_public_id=uuid4(), request_id="req1")


class TestViewerReadOnly:
    def test_viewer_cannot_update_profile(self, service, mock_repo, mock_auth_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "viewer", "status": "active",
        }
        mock_repo.find_farm_access.return_value = {"id": 1, "access_level": "read", "status": "active"}
        with pytest.raises(ForbiddenError):
            service.create_or_update_profile(
                subject="viewer@test.com", farm_public_id=uuid4(),
                payload={"latitude": -12.64, "longitude": -55.72}, request_id="req1")


class TestMembershipRevoked:
    def test_revoked_membership_blocked(self, service, mock_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "revoked",
        }
        with pytest.raises(ForbiddenError):
            service.get_profile(subject="user@test.com", farm_public_id=uuid4(), request_id="req1")


class TestFarmAccessRequired:
    def test_no_farm_access_blocked(self, service, mock_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "technician", "status": "active",
        }
        mock_repo.find_farm_access.return_value = None
        with pytest.raises(ForbiddenError):
            service.get_profile(subject="tech@test.com", farm_public_id=uuid4(), request_id="req1")


class TestInternalIdsNotExposed:
    def test_profile_response_no_internal_id(self, service, mock_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "active",
        }
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
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "active",
        }
        result = service.get_pasture_weather_context(
            subject="user@test.com", farm_public_id=uuid4(), request_id="req1")
        assert "recent_rainfall_mm" in result
        mock_repo.update_paddock_manual_status.assert_not_called()

    def test_weather_does_not_change_harvest_plan(self, service, mock_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "active",
        }
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
