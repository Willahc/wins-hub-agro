"""Testes unitários do domínio de Autonomia Alimentar — fórmulas com Decimal."""
import unittest
from decimal import Decimal
from datetime import date

from domain.food_autonomy import (
    FORMULA_VERSION, ScenarioStatus, HerdItem, PastureItem, FeedItem,
    SimulationInput, SimulationResult, calculate_autonomy,
)


class TestHerdItemDemand(unittest.TestCase):
    def test_single_category_demand(self):
        h = HerdItem(category="lactating_cows", head_count=20,
                     average_weight_kg=Decimal("450"), intake_pct_body_weight=Decimal("2.5"))
        self.assertEqual(h.daily_demand_dm_kg(), Decimal("225.00"))

    def test_zero_head_count(self):
        h = HerdItem(category="other", head_count=0,
                     average_weight_kg=Decimal("300"), intake_pct_body_weight=Decimal("2.5"))
        self.assertEqual(h.daily_demand_dm_kg(), Decimal("0.00"))

    def test_decimal_precision(self):
        h = HerdItem(category="dry_cows", head_count=15,
                     average_weight_kg=Decimal("520.50"), intake_pct_body_weight=Decimal("1.8"))
        demand = h.daily_demand_dm_kg()
        self.assertEqual(demand, Decimal("140.54"))

    def test_negative_head_count_raises(self):
        with self.assertRaises(ValueError):
            HerdItem(category="other", head_count=-1,
                     average_weight_kg=Decimal("300"), intake_pct_body_weight=Decimal("2.5"))

    def test_zero_weight_raises(self):
        with self.assertRaises(ValueError):
            HerdItem(category="other", head_count=10,
                     average_weight_kg=Decimal("0"), intake_pct_body_weight=Decimal("2.5"))

    def test_negative_intake_raises(self):
        with self.assertRaises(ValueError):
            HerdItem(category="other", head_count=10,
                     average_weight_kg=Decimal("300"), intake_pct_body_weight=Decimal("-1"))

    def test_intake_above_limit_raises(self):
        with self.assertRaises(ValueError):
            HerdItem(category="other", head_count=10,
                     average_weight_kg=Decimal("300"), intake_pct_body_weight=Decimal("11"))


class TestPastureItemUsable(unittest.TestCase):
    def test_basic_pasture(self):
        p = PastureItem(name="Norte", area_ha=Decimal("10"),
                        available_dm_kg_ha=Decimal("2000"), utilization_pct=Decimal("50"))
        self.assertEqual(p.usable_dm_kg(), Decimal("10000.00"))

    def test_full_utilization(self):
        p = PastureItem(name="Sul", area_ha=Decimal("5"),
                        available_dm_kg_ha=Decimal("3000"), utilization_pct=Decimal("100"))
        self.assertEqual(p.usable_dm_kg(), Decimal("15000.00"))

    def test_zero_utilization(self):
        p = PastureItem(name="Leste", area_ha=Decimal("8"),
                        available_dm_kg_ha=Decimal("1500"), utilization_pct=Decimal("0"))
        self.assertEqual(p.usable_dm_kg(), Decimal("0.00"))

    def test_zero_area_raises(self):
        with self.assertRaises(ValueError):
            PastureItem(name="X", area_ha=Decimal("0"),
                        available_dm_kg_ha=Decimal("2000"), utilization_pct=Decimal("50"))

    def test_negative_dm_ha_raises(self):
        with self.assertRaises(ValueError):
            PastureItem(name="X", area_ha=Decimal("10"),
                        available_dm_kg_ha=Decimal("-100"), utilization_pct=Decimal("50"))

    def test_utilization_over_100_raises(self):
        with self.assertRaises(ValueError):
            PastureItem(name="X", area_ha=Decimal("10"),
                        available_dm_kg_ha=Decimal("2000"), utilization_pct=Decimal("101"))


class TestFeedItemUsable(unittest.TestCase):
    def test_silage(self):
        f = FeedItem(feed_type="silage", name="Silo",
                     quantity_natural_kg=Decimal("10000"), dry_matter_pct=Decimal("35"),
                     utilization_pct=Decimal("90"))
        self.assertEqual(f.usable_dm_kg(), Decimal("3150.00"))

    def test_hay(self):
        f = FeedItem(feed_type="hay", name="Feno",
                     quantity_natural_kg=Decimal("5000"), dry_matter_pct=Decimal("85"),
                     utilization_pct=Decimal("95"))
        self.assertEqual(f.usable_dm_kg(), Decimal("4037.50"))

    def test_zero_quantity(self):
        f = FeedItem(feed_type="concentrate", name="Ração",
                     quantity_natural_kg=Decimal("0"), dry_matter_pct=Decimal("90"),
                     utilization_pct=Decimal("100"))
        self.assertEqual(f.usable_dm_kg(), Decimal("0.00"))

    def test_invalid_feed_type_raises(self):
        with self.assertRaises(ValueError):
            FeedItem(feed_type="invalid", name="X",
                     quantity_natural_kg=Decimal("100"), dry_matter_pct=Decimal("90"),
                     utilization_pct=Decimal("100"))

    def test_negative_quantity_raises(self):
        with self.assertRaises(ValueError):
            FeedItem(feed_type="silage", name="X",
                     quantity_natural_kg=Decimal("-1"), dry_matter_pct=Decimal("35"),
                     utilization_pct=Decimal("90"))


class TestCalculateAutonomy(unittest.TestCase):
    def _make_input(self, herd=None, pastures=None, feeds=None, target=90, safety=0):
        return SimulationInput(
            name="Teste", reference_date=date(2026, 7, 1),
            target_days=target, safety_margin_pct=Decimal(str(safety)),
            herd=tuple(herd or [HerdItem(category="lactating_cows", head_count=20,
                                         average_weight_kg=Decimal("450"),
                                         intake_pct_body_weight=Decimal("2.5"))]),
            pastures=tuple(pastures or []),
            feeds=tuple(feeds or []),
        )

    def test_basic_autonomy(self):
        inp = self._make_input(
            pastures=[PastureItem(name="P1", area_ha=Decimal("10"),
                                  available_dm_kg_ha=Decimal("2000"),
                                  utilization_pct=Decimal("50"))],
            feeds=[FeedItem(feed_type="silage", name="S1",
                            quantity_natural_kg=Decimal("10000"),
                            dry_matter_pct=Decimal("35"),
                            utilization_pct=Decimal("90"))],
        )
        r = calculate_autonomy(inp)
        self.assertEqual(r.formula_version, FORMULA_VERSION)
        self.assertEqual(r.daily_demand_dm_kg, Decimal("225.00"))
        self.assertEqual(r.pasture_usable_dm_kg, Decimal("10000.00"))
        self.assertEqual(r.stored_feed_usable_dm_kg, Decimal("3150.00"))
        self.assertEqual(r.physical_total_dm_kg, Decimal("13150.00"))
        self.assertEqual(r.autonomy_days, Decimal("58.44"))

    def test_status_adequate(self):
        inp = self._make_input(
            feeds=[FeedItem(feed_type="silage", name="S",
                            quantity_natural_kg=Decimal("100000"),
                            dry_matter_pct=Decimal("35"),
                            utilization_pct=Decimal("100"))],
            target=30,
        )
        r = calculate_autonomy(inp)
        self.assertEqual(r.status, ScenarioStatus.ADEQUATE)

    def test_status_warning(self):
        # Demanda = 225 kg/dia, meta = 30 dias → precisa de 6750 kg MS
        # Estoques: 50000 × 0.35 × 0.9 = 15750 kg MS → autonomia = 70 dias → warning
        inp = self._make_input(
            feeds=[FeedItem(feed_type="silage", name="S",
                            quantity_natural_kg=Decimal("50000"),
                            dry_matter_pct=Decimal("35"),
                            utilization_pct=Decimal("90"))],
            target=90,
        )
        r = calculate_autonomy(inp)
        self.assertEqual(r.status, ScenarioStatus.WARNING)

    def test_status_critical(self):
        inp = self._make_input(
            feeds=[FeedItem(feed_type="silage", name="S",
                            quantity_natural_kg=Decimal("5000"),
                            dry_matter_pct=Decimal("35"),
                            utilization_pct=Decimal("90"))],
            target=90,
        )
        r = calculate_autonomy(inp)
        self.assertEqual(r.status, ScenarioStatus.CRITICAL)

    def test_safety_margin(self):
        inp = self._make_input(
            feeds=[FeedItem(feed_type="silage", name="S",
                            quantity_natural_kg=Decimal("100000"),
                            dry_matter_pct=Decimal("35"),
                            utilization_pct=Decimal("100"))],
            safety=10,
            target=90,
        )
        r = calculate_autonomy(inp)
        self.assertEqual(r.reserve_dm_kg, Decimal("3500.00"))
        self.assertEqual(r.planning_available_dm_kg, Decimal("31500.00"))

    def test_estimated_end_date(self):
        inp = self._make_input(
            feeds=[FeedItem(feed_type="silage", name="S",
                            quantity_natural_kg=Decimal("100000"),
                            dry_matter_pct=Decimal("35"),
                            utilization_pct=Decimal("100"))],
            target=90,
        )
        r = calculate_autonomy(inp)
        self.assertIsNotNone(r.estimated_end_date)

    def test_zero_demand(self):
        h = HerdItem(category="other", head_count=0,
                     average_weight_kg=Decimal("300"), intake_pct_body_weight=Decimal("2.5"))
        inp = self._make_input(
            herd=[h],
            feeds=[FeedItem(feed_type="silage", name="S",
                            quantity_natural_kg=Decimal("10000"),
                            dry_matter_pct=Decimal("35"),
                            utilization_pct=Decimal("90"))],
        )
        r = calculate_autonomy(inp)
        self.assertEqual(r.status, ScenarioStatus.INCOMPLETE)

    def test_balance_calculation(self):
        inp = self._make_input(
            feeds=[FeedItem(feed_type="silage", name="S",
                            quantity_natural_kg=Decimal("50000"),
                            dry_matter_pct=Decimal("35"),
                            utilization_pct=Decimal("100"))],
            target=90,
        )
        r = calculate_autonomy(inp)
        self.assertEqual(r.balance_days, r.autonomy_days - Decimal("90"))

    def test_formula_version(self):
        inp = self._make_input(
            feeds=[FeedItem(feed_type="silage", name="S",
                            quantity_natural_kg=Decimal("10000"),
                            dry_matter_pct=Decimal("35"),
                            utilization_pct=Decimal("90"))],
        )
        r = calculate_autonomy(inp)
        self.assertEqual(r.formula_version, "food_autonomy.v1")

    def test_decimal_not_float(self):
        inp = self._make_input(
            pastures=[PastureItem(name="P", area_ha=Decimal("10"),
                                  available_dm_kg_ha=Decimal("2000"),
                                  utilization_pct=Decimal("50"))],
        )
        r = calculate_autonomy(inp)
        self.assertIsInstance(r.daily_demand_dm_kg, Decimal)
        self.assertIsInstance(r.autonomy_days, Decimal)
        self.assertIsInstance(r.balance_dm_kg, Decimal)


class TestSimulationInputValidation(unittest.TestCase):
    def test_zero_target_days_raises(self):
        with self.assertRaises(ValueError):
            SimulationInput(name="X", reference_date=date(2026, 1, 1),
                            target_days=0, safety_margin_pct=Decimal("0"),
                            herd=(HerdItem(category="other", head_count=1,
                                           average_weight_kg=Decimal("300"),
                                           intake_pct_body_weight=Decimal("2.5")),),
                            pastures=(), feeds=())

    def test_empty_herd_raises(self):
        with self.assertRaises(ValueError):
            SimulationInput(name="X", reference_date=date(2026, 1, 1),
                            target_days=90, safety_margin_pct=Decimal("0"),
                            herd=(), pastures=(),
                            feeds=(FeedItem(feed_type="silage", name="S",
                                            quantity_natural_kg=Decimal("1000"),
                                            dry_matter_pct=Decimal("35"),
                                            utilization_pct=Decimal("90")),))

    def test_no_food_source_raises(self):
        with self.assertRaises(ValueError):
            SimulationInput(name="X", reference_date=date(2026, 1, 1),
                            target_days=90, safety_margin_pct=Decimal("0"),
                            herd=(HerdItem(category="other", head_count=1,
                                           average_weight_kg=Decimal("300"),
                                           intake_pct_body_weight=Decimal("2.5")),),
                            pastures=(), feeds=())

    def test_negative_safety_raises(self):
        with self.assertRaises(ValueError):
            SimulationInput(name="X", reference_date=date(2026, 1, 1),
                            target_days=90, safety_margin_pct=Decimal("-1"),
                            herd=(HerdItem(category="other", head_count=1,
                                           average_weight_kg=Decimal("300"),
                                           intake_pct_body_weight=Decimal("2.5")),),
                            pastures=(), feeds=(
                                FeedItem(feed_type="silage", name="S",
                                         quantity_natural_kg=Decimal("1000"),
                                         dry_matter_pct=Decimal("35"),
                                         utilization_pct=Decimal("90")),))

    def test_safety_over_100_raises(self):
        with self.assertRaises(ValueError):
            SimulationInput(name="X", reference_date=date(2026, 1, 1),
                            target_days=90, safety_margin_pct=Decimal("101"),
                            herd=(HerdItem(category="other", head_count=1,
                                           average_weight_kg=Decimal("300"),
                                           intake_pct_body_weight=Decimal("2.5")),),
                            pastures=(), feeds=(
                                FeedItem(feed_type="silage", name="S",
                                         quantity_natural_kg=Decimal("1000"),
                                         dry_matter_pct=Decimal("35"),
                                         utilization_pct=Decimal("90")),))


if __name__ == "__main__":
    unittest.main()
