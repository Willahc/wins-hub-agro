from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_service_uses_decimal_not_float():
    text = (ROOT/"services/harvest_silos.py").read_text()
    assert "Decimal" in text
    assert "float(" not in text


def test_allocation_sums_are_enforced_for_plan_and_completion():
    text = (ROOT/"services/harvest_silos.py").read_text()
    assert "allocation_sum_must_equal_expected_net" in text
    assert "allocation_sum_must_equal_actual" in text


def test_completed_plan_is_immutable_and_not_silently_archived():
    text = (ROOT/"services/harvest_silos.py").read_text()
    assert "completed_plan_is_immutable" in text
    assert "completed_plan_cannot_be_archived" in text


def test_capacity_is_rechecked_at_completion():
    text = (ROOT/"services/harvest_silos.py").read_text()
    assert "facility_over_capacity" in text
    assert "get_facility_capacity_and_stock" in text


def test_feed_inventory_formulas_are_reused():
    text = (ROOT/"services/harvest_silos.py").read_text()
    assert "calculate_physical_dm" in text and "calculate_usable_dm" in text
