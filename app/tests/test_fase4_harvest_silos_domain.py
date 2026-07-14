from decimal import Decimal

import pytest

from domain.harvest_silos import (
    calculate_dm_kg, calculate_gross_natural, calculate_net_natural,
    calculate_occupancy_pct, calculate_projected_occupancy,
    calculate_variation, determine_capacity_status,
)


def test_manual_scenario():
    gross = calculate_gross_natural(Decimal("20"), Decimal("40"))
    net = calculate_net_natural(gross, Decimal("5"), Decimal("8"))
    assert gross == Decimal("800000.00")
    assert net == Decimal("699200.00")
    assert calculate_dm_kg(net, Decimal("35")) == Decimal("244720.00")


@pytest.mark.parametrize("pct,status", [(Decimal("84.99"), "available"), (Decimal("85"), "near_capacity"),
                                          (Decimal("100"), "near_capacity"), (Decimal("100.01"), "over_capacity")])
def test_capacity_boundaries(pct, status):
    assert determine_capacity_status(pct) == status


def test_unknown_and_zero_capacity():
    assert calculate_occupancy_pct(Decimal("10"), None) is None
    assert calculate_occupancy_pct(Decimal("10"), Decimal("0")) is None
    assert determine_capacity_status(None) == "unknown_capacity"


def test_projected_occupancy_and_percentage():
    projected = calculate_projected_occupancy(Decimal("100"), Decimal("750"))
    assert projected == Decimal("850.00")
    assert calculate_occupancy_pct(projected, Decimal("1000")) == Decimal("85.00")


def test_variation_and_division_by_zero():
    assert calculate_variation(Decimal("100"), Decimal("90")) == (Decimal("-10.00"), Decimal("-10.00"))
    assert calculate_variation(Decimal("0"), Decimal("10")) == (Decimal("10.00"), None)


@pytest.mark.parametrize("args", [(Decimal("0"), Decimal("1")), (Decimal("1"), Decimal("0"))])
def test_area_and_yield_must_be_positive(args):
    with pytest.raises(ValueError): calculate_gross_natural(*args)


def test_decimal_rounding_is_deterministic():
    assert calculate_dm_kg(Decimal("1"), Decimal("33.333")) == Decimal("0.33")
