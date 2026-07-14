from datetime import date
from uuid import uuid4

import pytest
pytest.importorskip("pydantic", reason="Pydantic é validado dentro do staging_api")
from pydantic import ValidationError

from schemas.harvest_silos import CompleteRequest, PlanCreateRequest


def area():
    return {"name":"Talhão", "crop":"milho", "area_ha":"20", "expected_yield_t_ha":"40", "expected_dm_pct":"35"}


def test_plan_schema_accepts_valid_contract():
    value = PlanCreateRequest(name="Safra", main_crop="milho", purpose="silagem",
        expected_start_date=date.today(), expected_end_date=date.today(), expected_field_loss_pct="5",
        expected_ensiling_loss_pct="8", areas=[area()])
    assert value.areas[0].area_ha == "20"


def test_plan_schema_rejects_non_decimal_text():
    with pytest.raises(ValidationError):
        PlanCreateRequest(name="Safra", main_crop="milho", purpose="silagem", expected_start_date=date.today(),
            expected_end_date=date.today(), expected_field_loss_pct="x", expected_ensiling_loss_pct="8", areas=[area()])


def test_complete_schema_has_idempotency_key_and_multiple_allocations():
    payload = CompleteRequest(actual_start_date=date.today(), actual_end_date=date.today(), actual_natural_kg="100",
        actual_dm_pct="35", actual_loss_pct="5", request_id="completion-1", allocations=[{
            "facility_uuid":uuid4(), "actual_natural_kg":"40", "lot_name":"A", "feed_type":"silagem_milho"}, {
            "facility_uuid":uuid4(), "actual_natural_kg":"60", "lot_name":"B", "feed_type":"silagem_milho"}])
    assert len(payload.allocations) == 2


def test_router_exposes_required_operations(monkeypatch):
    monkeypatch.setenv("ENABLE_HARVEST_SILOS", "true")
    import importlib, routers.harvest_silos as module
    module = importlib.reload(module)
    paths = {(r.path, next(iter(r.methods))) for r in module.router.routes}
    rendered = "\n".join(f"{m} {p}" for p,m in paths)
    for fragment in ("/dashboard", "/simulate", "/plans", "/start", "/complete"):
        assert fragment in rendered
