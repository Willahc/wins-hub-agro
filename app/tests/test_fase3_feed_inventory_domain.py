"""Testes unitários do domínio de Estoque de Ração — fórmulas com Decimal."""
import unittest
from datetime import date, timedelta
from decimal import Decimal

from domain.feed_inventory import (
    FORMULA_VERSION,
    FacilityType, FeedType, LotStatus, MovementType, LossReason,
    calculate_physical_dm, calculate_usable_dm, calculate_cost_per_natural_kg,
    calculate_inventory_value, calculate_cost_per_usable_dm, calculate_loss_value,
    calculate_days_remaining, calculate_estimated_end_date, reconcile_balance,
    _q2, _q4,
    MAX_CAPACITY_KG, MAX_QUANTITY_KG, MAX_COST,
    FACILITY_TYPES, FEED_TYPES, LOT_STATUSES, MOVEMENT_TYPES, LOSS_REASONS,
    ACTIVE_LOT_STATUSES, ADDITIVE_MOVEMENTS, SUBTRACTIVE_MOVEMENTS,
)


class TestFormulaVersion(unittest.TestCase):
    def test_version_string(self):
        self.assertEqual(FORMULA_VERSION, "feed_inventory.v1")

    def test_version_constant_type(self):
        self.assertIsInstance(FORMULA_VERSION, str)


class TestPhysicalDM(unittest.TestCase):
    def test_basic_calculation(self):
        result = calculate_physical_dm(Decimal("10000"), Decimal("35"))
        self.assertEqual(result, Decimal("3500.00"))

    def test_zero_quantity(self):
        result = calculate_physical_dm(Decimal("0"), Decimal("0"))
        self.assertEqual(result, Decimal("0.00"))

    def test_100pct_dm(self):
        result = calculate_physical_dm(Decimal("100"), Decimal("100"))
        self.assertEqual(result, Decimal("100.00"))

    def test_boundary_0pct(self):
        result = calculate_physical_dm(Decimal("5000"), Decimal("0"))
        self.assertEqual(result, Decimal("0.00"))

    def test_boundary_100pct(self):
        result = calculate_physical_dm(Decimal("5000"), Decimal("100"))
        self.assertEqual(result, Decimal("5000.00"))

    def test_returns_decimal(self):
        result = calculate_physical_dm(Decimal("1000"), Decimal("35"))
        self.assertIsInstance(result, Decimal)


class TestUsableDM(unittest.TestCase):
    def test_basic_calculation(self):
        result = calculate_usable_dm(Decimal("3500"), Decimal("90"))
        self.assertEqual(result, Decimal("3150.00"))

    def test_zero_input(self):
        result = calculate_usable_dm(Decimal("0"), Decimal("0"))
        self.assertEqual(result, Decimal("0.00"))

    def test_boundary_0pct(self):
        result = calculate_usable_dm(Decimal("5000"), Decimal("0"))
        self.assertEqual(result, Decimal("0.00"))

    def test_boundary_100pct(self):
        result = calculate_usable_dm(Decimal("5000"), Decimal("100"))
        self.assertEqual(result, Decimal("5000.00"))

    def test_returns_decimal(self):
        result = calculate_usable_dm(Decimal("3500"), Decimal("90"))
        self.assertIsInstance(result, Decimal)


class TestCostPerNaturalKg(unittest.TestCase):
    def test_basic_calculation(self):
        result = calculate_cost_per_natural_kg(Decimal("12000"), Decimal("10000"))
        self.assertEqual(result, Decimal("1.2000"))

    def test_none_when_no_cost(self):
        result = calculate_cost_per_natural_kg(None, Decimal("10000"))
        self.assertIsNone(result)

    def test_none_when_qty_zero(self):
        result = calculate_cost_per_natural_kg(Decimal("12000"), Decimal("0"))
        self.assertIsNone(result)

    def test_none_when_qty_negative(self):
        result = calculate_cost_per_natural_kg(Decimal("12000"), Decimal("-1"))
        self.assertIsNone(result)

    def test_none_when_cost_zero(self):
        result = calculate_cost_per_natural_kg(Decimal("0"), Decimal("10000"))
        self.assertIsNone(result)


class TestInventoryValue(unittest.TestCase):
    def test_basic_calculation(self):
        result = calculate_inventory_value(Decimal("9000"), Decimal("1.20"))
        self.assertEqual(result, Decimal("10800.00"))

    def test_zero_when_no_cost(self):
        result = calculate_inventory_value(Decimal("9000"), None)
        self.assertEqual(result, Decimal("0"))

    def test_zero_when_cost_zero(self):
        result = calculate_inventory_value(Decimal("9000"), Decimal("0"))
        self.assertEqual(result, Decimal("0"))

    def test_returns_decimal(self):
        result = calculate_inventory_value(Decimal("9000"), Decimal("1.20"))
        self.assertIsInstance(result, Decimal)


class TestCostPerUsableDM(unittest.TestCase):
    def test_basic_calculation(self):
        result = calculate_cost_per_usable_dm(Decimal("12000"), Decimal("3150"))
        self.assertEqual(result, Decimal("3.8095"))

    def test_none_when_usable_dm_zero(self):
        result = calculate_cost_per_usable_dm(Decimal("12000"), Decimal("0"))
        self.assertIsNone(result)

    def test_none_when_value_zero(self):
        result = calculate_cost_per_usable_dm(Decimal("0"), Decimal("3150"))
        self.assertIsNone(result)

    def test_none_when_usable_dm_negative(self):
        result = calculate_cost_per_usable_dm(Decimal("12000"), Decimal("-1"))
        self.assertIsNone(result)


class TestLossValue(unittest.TestCase):
    def test_basic_calculation(self):
        result = calculate_loss_value(Decimal("500"), Decimal("1.20"))
        self.assertEqual(result, Decimal("600.00"))

    def test_zero_when_no_cost(self):
        result = calculate_loss_value(Decimal("500"), None)
        self.assertEqual(result, Decimal("0"))

    def test_zero_when_cost_zero(self):
        result = calculate_loss_value(Decimal("500"), Decimal("0"))
        self.assertEqual(result, Decimal("0"))

    def test_returns_decimal(self):
        result = calculate_loss_value(Decimal("500"), Decimal("1.20"))
        self.assertIsInstance(result, Decimal)


class TestDaysRemaining(unittest.TestCase):
    def test_basic_calculation(self):
        result = calculate_days_remaining(Decimal("3150"), Decimal("100"))
        self.assertEqual(result, 31)

    def test_none_when_no_daily_use(self):
        result = calculate_days_remaining(Decimal("3150"), None)
        self.assertIsNone(result)

    def test_zero_when_usable_dm_zero(self):
        result = calculate_days_remaining(Decimal("0"), Decimal("100"))
        self.assertEqual(result, 0)

    def test_none_when_daily_use_zero(self):
        result = calculate_days_remaining(Decimal("3150"), Decimal("0"))
        self.assertIsNone(result)

    def test_returns_int(self):
        result = calculate_days_remaining(Decimal("3150"), Decimal("100"))
        self.assertIsInstance(result, int)


class TestEstimatedEndDate(unittest.TestCase):
    def test_basic_calculation(self):
        result = calculate_estimated_end_date(date(2026, 1, 1), 31)
        self.assertEqual(result, date(2026, 2, 1))

    def test_none_when_no_days(self):
        result = calculate_estimated_end_date(date(2026, 1, 1), None)
        self.assertIsNone(result)

    def test_reference_date_when_zero_days(self):
        result = calculate_estimated_end_date(date(2026, 1, 1), 0)
        self.assertEqual(result, date(2026, 1, 1))

    def test_returns_date_type(self):
        result = calculate_estimated_end_date(date(2026, 1, 1), 31)
        self.assertIsInstance(result, date)


class TestDecimalPrecision(unittest.TestCase):
    def test_q2_rounds_to_2_places(self):
        result = _q2(Decimal("1.235"))
        self.assertEqual(result, Decimal("1.24"))

    def test_q2_already_2_places(self):
        result = _q2(Decimal("1.23"))
        self.assertEqual(result, Decimal("1.23"))

    def test_q2_integer(self):
        result = _q2(Decimal("5"))
        self.assertEqual(result, Decimal("5.00"))

    def test_q4_rounds_to_4_places(self):
        result = _q4(Decimal("3.80952"))
        self.assertEqual(result, Decimal("3.8095"))

    def test_q4_already_4_places(self):
        result = _q4(Decimal("3.8095"))
        self.assertEqual(result, Decimal("3.8095"))

    def test_no_float_in_domain(self):
        from domain import feed_inventory
        content = open(feed_inventory.__file__).read()
        self.assertNotIn("float(", content)
        self.assertIn("Decimal", content)


class TestDivideByZero(unittest.TestCase):
    def test_physical_dm_handles_zero(self):
        result = calculate_physical_dm(Decimal("0"), Decimal("0"))
        self.assertEqual(result, Decimal("0.00"))

    def test_usable_dm_handles_zero(self):
        result = calculate_usable_dm(Decimal("0"), Decimal("0"))
        self.assertEqual(result, Decimal("0.00"))

    def test_cost_per_natural_kg_handles_zero(self):
        result = calculate_cost_per_natural_kg(Decimal("0"), Decimal("0"))
        self.assertIsNone(result)

    def test_inventory_value_handles_zero(self):
        result = calculate_inventory_value(Decimal("0"), None)
        self.assertEqual(result, Decimal("0"))

    def test_cost_per_usable_dm_handles_zero(self):
        result = calculate_cost_per_usable_dm(Decimal("0"), Decimal("0"))
        self.assertIsNone(result)

    def test_days_remaining_handles_zero(self):
        result = calculate_days_remaining(Decimal("0"), Decimal("0"))
        self.assertIsNone(result)


class TestEnums(unittest.TestCase):
    def test_facility_type_values(self):
        values = {ft.value for ft in FacilityType}
        self.assertIn("silo_trincheira", values)
        self.assertIn("galpao", values)
        self.assertIn("deposito_feno", values)
        self.assertEqual(len(FacilityType), 9)

    def test_feed_type_values(self):
        values = {ft.value for ft in FeedType}
        self.assertIn("silagem_milho", values)
        self.assertIn("feno", values)
        self.assertIn("concentrado", values)
        self.assertEqual(len(FeedType), 14)

    def test_lot_status_values(self):
        values = {ls.value for ls in LotStatus}
        self.assertEqual(values, {"available", "reserved", "opened",
                                  "depleted", "quarantined", "archived"})

    def test_movement_type_values(self):
        values = {mt.value for mt in MovementType}
        self.assertIn("initial_balance", values)
        self.assertIn("entry", values)
        self.assertIn("withdrawal", values)
        self.assertIn("loss", values)
        self.assertIn("adjustment_positive", values)
        self.assertIn("adjustment_negative", values)

    def test_loss_reason_values(self):
        values = {lr.value for lr in LossReason}
        self.assertIn("deterioracao", values)
        self.assertIn("chuva", values)
        self.assertIn("descarte", values)
        self.assertEqual(len(LossReason), 9)


class TestConstants(unittest.TestCase):
    def test_max_capacity_is_positive_decimal(self):
        self.assertIsInstance(MAX_CAPACITY_KG, Decimal)
        self.assertGreater(MAX_CAPACITY_KG, Decimal("0"))

    def test_max_quantity_is_positive_decimal(self):
        self.assertIsInstance(MAX_QUANTITY_KG, Decimal)
        self.assertGreater(MAX_QUANTITY_KG, Decimal("0"))

    def test_max_cost_is_positive_decimal(self):
        self.assertIsInstance(MAX_COST, Decimal)
        self.assertGreater(MAX_COST, Decimal("0"))

    def test_frozen_sets_are_frozensets(self):
        self.assertIsInstance(FACILITY_TYPES, frozenset)
        self.assertIsInstance(FEED_TYPES, frozenset)
        self.assertIsInstance(LOT_STATUSES, frozenset)
        self.assertIsInstance(MOVEMENT_TYPES, frozenset)
        self.assertIsInstance(LOSS_REASONS, frozenset)
        self.assertIsInstance(ACTIVE_LOT_STATUSES, frozenset)
        self.assertIsInstance(ADDITIVE_MOVEMENTS, frozenset)
        self.assertIsInstance(SUBTRACTIVE_MOVEMENTS, frozenset)


if __name__ == "__main__":
    unittest.main()
