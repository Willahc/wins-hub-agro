"""Testes de Integração do módulo de Clima e Janelas Operacionais."""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from domain.weather_operations import (
    WeatherStatus, SnapshotType, CacheStatus, FORMULA_VERSION,
    compute_window_score, normalize_weather_condition, classify_temperature,
)
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


class TestPastureContextIntegration:
    def test_pasture_context_returns_climate_data(self, service, mock_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "active",
        }
        now = datetime.now(timezone.utc)
        mock_repo.get_any_snapshot.side_effect = [
            {"payload_normalized": {"daily": [{"precipitation_sum_mm": 5}, {"precipitation_sum_mm": 3}]},
             "fetched_at": now, "provider": "open-meteo"},
            {"payload_normalized": {"daily": [{"precipitation_sum_mm": 0}, {"precipitation_sum_mm": 1}]},
             "fetched_at": now, "provider": "open-meteo"},
            {"payload_normalized": {"temperature_c": 30, "feels_like_c": 32, "humidity_pct": 50},
             "fetched_at": now, "provider": "open-meteo"},
        ]
        result = service.get_pasture_weather_context(
            subject="user@test.com", farm_public_id=uuid4(), request_id="req1")
        assert "recent_rainfall_mm" in result
        assert "forecast_rainfall_mm" in result
        assert "current_temperature_c" in result
        assert "heat_status" in result
        assert any("contexto" in w.lower() for w in result["warnings"])

    def test_pasture_context_does_not_modify_paddock(self, service, mock_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "active",
        }
        service.get_pasture_weather_context(
            subject="user@test.com", farm_public_id=uuid4(), request_id="req1")
        mock_repo.update_paddock_manual_status.assert_not_called()
        mock_repo.update_paddock.assert_not_called()


class TestHarvestContextIntegration:
    def test_harvest_context_with_plan(self, service, mock_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "active",
        }
        plan_uuid = uuid4()
        mock_repo.find_harvest_plan_by_uuid.return_value = {
            "id": 1, "public_id": plan_uuid, "name": "Plano Teste",
            "expected_start_date": "2026-07-20", "expected_end_date": "2026-07-25",
            "status": "planned", "farm_id": 1,
        }
        now = datetime.now(timezone.utc)
        mock_repo.get_any_snapshot.return_value = {
            "payload_normalized": {"daily": [
                {"date": "2026-07-20", "precipitation_sum_mm": 5, "precipitation_probability_max": 70},
                {"date": "2026-07-21", "precipitation_sum_mm": 10, "precipitation_probability_max": 85},
            ]},
            "fetched_at": now, "provider": "open-meteo",
        }
        result = service.get_harvest_weather_context(
            subject="user@test.com", farm_public_id=uuid4(),
            plan_uuid=str(plan_uuid), request_id="req1")
        assert result["plan_uuid"] == str(plan_uuid)
        assert result["expected_precipitation_mm"] == 15.0
        assert len(result["risk_factors"]) > 0

    def test_harvest_context_does_not_modify_plan(self, service, mock_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "active",
        }
        mock_repo.find_harvest_plan_by_uuid.return_value = {
            "id": 1, "public_id": uuid4(), "name": "Plano Teste",
            "expected_start_date": "2026-07-20", "expected_end_date": "2026-07-25",
            "status": "planned", "farm_id": 1,
        }
        service.get_harvest_weather_context(
            subject="user@test.com", farm_public_id=uuid4(),
            plan_uuid=str(uuid4()), request_id="req1")
        mock_repo.update_plan.assert_not_called()


class TestProviderFailureFallback:
    def test_provider_error_uses_cache(self, service, mock_repo):
        from integrations.weather_provider import WeatherProviderError
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "active",
        }
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
            "fetched_at": now - timedelta(minutes=120),
            "expires_at": now - timedelta(minutes=100),
            "payload_normalized": {"temperature_c": 28},
            "provider": "open-meteo",
        }
        result = service.get_current(subject="user@test.com", farm_public_id=uuid4(), request_id="req1")
        assert result["source"] == "cache"


class TestEvaluationPersistence:
    def test_evaluation_saved(self, service, mock_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "active",
        }
        mock_repo.save_evaluation.return_value = {"id": 1, "public_id": uuid4()}
        result = service.save_evaluation(
            subject="user@test.com", farm_public_id=uuid4(),
            payload={
                "window_type": "harvest_cut",
                "period_start": datetime.now(timezone.utc),
                "period_end": datetime.now(timezone.utc) + timedelta(hours=1),
                "score": 85.0,
                "classification": "favorable",
            },
            request_id="req1")
        assert result["status"] == "saved"
        mock_repo.save_evaluation.assert_called_once()


class TestDashboardIntegration:
    def test_dashboard_combines_all_sources(self, service, mock_repo):
        mock_repo.find_farm.return_value = {"id": 1, "organization_id": 1, "name": "Test", "status": "active"}
        mock_repo.find_membership.return_value = {
            "id": 1, "public_id": str(uuid4()), "organization_id": 1,
            "role": "owner", "status": "active",
        }
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
            "fetched_at": now,
            "expires_at": now + timedelta(minutes=20),
            "payload_normalized": {"temperature_c": 25, "humidity_pct": 60},
            "provider": "open-meteo",
        }
        mock_repo.get_any_snapshot.return_value = {
            "payload_normalized": {"daily": [{"precipitation_sum_mm": 2}]},
            "fetched_at": now, "provider": "open-meteo",
        }
        result = service.get_dashboard(
            subject="user@test.com", farm_public_id=uuid4(), request_id="req1")
        assert "integration_status" in result
        assert "recent_rainfall_mm" in result
