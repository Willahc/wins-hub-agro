"""Testes unitários do domínio de Pasto Vivo — fórmulas com Decimal."""
import unittest
from datetime import date, timedelta
from decimal import Decimal

from domain.pasture_live import (
    FORMULA_VERSION, PaddockStatus, EventType, MeasurementMethod,
    MeasurementResult, PaddockState,
    calculate_next_release_date, suggest_paddock_state, is_measurement_fresh,
    _q2, MAX_AREA_HA, MAX_DM_KG_HA, MAX_UTILIZATION_PCT, MAX_REST_DAYS,
    _FORAGE_SPECIES,
)


class TestMeasurementResultTotalDM(unittest.TestCase):
    def test_total_dm_basic(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("50"), forage_species="brachiaria",
        )
        result = mr.calculate_total_dm(Decimal("10"), Decimal("2000"))
        self.assertEqual(result, Decimal("20000.00"))

    def test_total_dm_area_times_dm_per_ha(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="ruler",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("3000"),
            utilization_pct=Decimal("100"), forage_species="mixed",
        )
        result = mr.calculate_total_dm(Decimal("5"), Decimal("3000"))
        self.assertEqual(result, Decimal("15000.00"))

    def test_total_dm_decimal_preserved(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("1500"),
            utilization_pct=Decimal("70"), forage_species="ryegrass",
        )
        result = mr.calculate_total_dm(Decimal("7.5"), Decimal("1500"))
        self.assertIsInstance(result, Decimal)
        self.assertEqual(result, result.quantize(Decimal("0.01")))


class TestMeasurementResultUsableDM(unittest.TestCase):
    def test_usable_dm_50pct(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("50"), forage_species="brachiaria",
        )
        result = mr.calculate_usable_dm(Decimal("10"), Decimal("2000"), Decimal("50"))
        self.assertEqual(result, Decimal("10000.00"))

    def test_usable_dm_full_utilization(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="ruler",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("3000"),
            utilization_pct=Decimal("100"), forage_species="mixed",
        )
        result = mr.calculate_usable_dm(Decimal("5"), Decimal("3000"), Decimal("100"))
        self.assertEqual(result, Decimal("15000.00"))

    def test_usable_dm_zero_utilization(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("0"), forage_species="bahiagrass",
        )
        result = mr.calculate_usable_dm(Decimal("10"), Decimal("2000"), Decimal("0"))
        self.assertEqual(result, Decimal("0.00"))

    def test_usable_dm_decimal_preserved_2_places(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("50"), forage_species="mixed",
        )
        result = mr.calculate_usable_dm(Decimal("10"), Decimal("2000"), Decimal("50"))
        self.assertEqual(result.as_tuple().exponent, -2)


class TestMeasurementResultValidation(unittest.TestCase):
    def test_negative_dm_raises(self):
        with self.assertRaises(ValueError):
            MeasurementResult(
                formula_version=FORMULA_VERSION, method="visual",
                measured_at="2026-07-01", available_dm_kg_ha=Decimal("-100"),
                utilization_pct=Decimal("50"), forage_species="mixed",
            )

    def test_utilization_over_100_raises(self):
        with self.assertRaises(ValueError):
            MeasurementResult(
                formula_version=FORMULA_VERSION, method="visual",
                measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
                utilization_pct=Decimal("101"), forage_species="mixed",
            )

    def test_utilization_negative_raises(self):
        with self.assertRaises(ValueError):
            MeasurementResult(
                formula_version=FORMULA_VERSION, method="visual",
                measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
                utilization_pct=Decimal("-1"), forage_species="mixed",
            )

    def test_zero_dm_valid(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("0"),
            utilization_pct=Decimal("50"), forage_species="mixed",
        )
        self.assertEqual(mr.available_dm_kg_ha, Decimal("0"))


class TestCalculateNextReleaseDate(unittest.TestCase):
    def test_basic_rest_period(self):
        result = calculate_next_release_date(date(2026, 7, 1), 30)
        self.assertEqual(result, date(2026, 7, 31))

    def test_zero_rest_days(self):
        result = calculate_next_release_date(date(2026, 7, 1), 0)
        self.assertEqual(result, date(2026, 7, 1))

    def test_large_rest_period(self):
        result = calculate_next_release_date(date(2026, 1, 1), 365)
        self.assertEqual(result, date(2027, 1, 1))

    def test_returns_date_type(self):
        result = calculate_next_release_date(date(2026, 7, 1), 14)
        self.assertIsInstance(result, date)


class TestSuggestPaddockState(unittest.TestCase):
    def test_ready_state(self):
        status = suggest_paddock_state(
            has_measurement=True, days_since_measurement=5,
            days_since_rest=10, rest_days=30,
            is_unavailable=False, is_inactive=False,
            open_grazing=False, area_ha=Decimal("10"),
            available_dm_kg_ha=Decimal("2000"),
        )
        self.assertEqual(status, PaddockStatus.READY)

    def test_grazing_state(self):
        status = suggest_paddock_state(
            has_measurement=True, days_since_measurement=5,
            days_since_rest=10, rest_days=30,
            is_unavailable=False, is_inactive=False,
            open_grazing=True, area_ha=Decimal("10"),
            available_dm_kg_ha=Decimal("2000"),
        )
        self.assertEqual(status, PaddockStatus.GRAZING)

    def test_resting_state(self):
        status = suggest_paddock_state(
            has_measurement=True, days_since_measurement=5,
            days_since_rest=30, rest_days=30,
            is_unavailable=False, is_inactive=False,
            open_grazing=False, area_ha=Decimal("10"),
            available_dm_kg_ha=Decimal("2000"),
        )
        self.assertEqual(status, PaddockStatus.RESTING)

    def test_attention_stale_measurement(self):
        status = suggest_paddock_state(
            has_measurement=True, days_since_measurement=15,
            days_since_rest=10, rest_days=30,
            is_unavailable=False, is_inactive=False,
            open_grazing=False, area_ha=Decimal("10"),
            available_dm_kg_ha=Decimal("2000"),
        )
        self.assertEqual(status, PaddockStatus.ATTENTION)

    def test_attention_low_dm(self):
        status = suggest_paddock_state(
            has_measurement=True, days_since_measurement=5,
            days_since_rest=10, rest_days=30,
            is_unavailable=False, is_inactive=False,
            open_grazing=False, area_ha=Decimal("10"),
            available_dm_kg_ha=Decimal("400"),
        )
        self.assertEqual(status, PaddockStatus.ATTENTION)

    def test_unavailable_state(self):
        status = suggest_paddock_state(
            has_measurement=True, days_since_measurement=5,
            days_since_rest=10, rest_days=30,
            is_unavailable=True, is_inactive=False,
            open_grazing=False, area_ha=Decimal("10"),
            available_dm_kg_ha=Decimal("2000"),
        )
        self.assertEqual(status, PaddockStatus.UNAVAILABLE)

    def test_no_measurement_state(self):
        status = suggest_paddock_state(
            has_measurement=False, days_since_measurement=None,
            days_since_rest=None, rest_days=30,
            is_unavailable=False, is_inactive=False,
            open_grazing=False, area_ha=Decimal("10"),
            available_dm_kg_ha=Decimal("2000"),
        )
        self.assertEqual(status, PaddockStatus.NO_MEASUREMENT)

    def test_inactive_state(self):
        status = suggest_paddock_state(
            has_measurement=True, days_since_measurement=5,
            days_since_rest=10, rest_days=30,
            is_unavailable=False, is_inactive=True,
            open_grazing=False, area_ha=Decimal("10"),
            available_dm_kg_ha=Decimal("2000"),
        )
        self.assertEqual(status, PaddockStatus.INACTIVE)

    def test_multiple_paddocks_states(self):
        paddocks = [
            dict(has_measurement=True, days_since_measurement=5, days_since_rest=30,
                 rest_days=30, is_unavailable=False, is_inactive=False, open_grazing=False,
                 area_ha=Decimal("10"), available_dm_kg_ha=Decimal("2000")),
            dict(has_measurement=True, days_since_measurement=5, days_since_rest=5,
                 rest_days=30, is_unavailable=False, is_inactive=False, open_grazing=True,
                 area_ha=Decimal("10"), available_dm_kg_ha=Decimal("2000")),
            dict(has_measurement=False, days_since_measurement=None, days_since_rest=None,
                 rest_days=30, is_unavailable=False, is_inactive=False, open_grazing=False,
                 area_ha=Decimal("10"), available_dm_kg_ha=Decimal("2000")),
        ]
        states = [suggest_paddock_state(**p) for p in paddocks]
        self.assertEqual(states[0], PaddockStatus.RESTING)
        self.assertEqual(states[1], PaddockStatus.GRAZING)
        self.assertEqual(states[2], PaddockStatus.NO_MEASUREMENT)


class TestPaddockStateShouldAlert(unittest.TestCase):
    def test_alert_no_measurement(self):
        ps = PaddockState(
            status=PaddockStatus.NO_MEASUREMENT, current_measurement=None,
            last_event=None, open_grazing_event=None,
            days_since_rest=None, days_since_measurement=None,
        )
        self.assertTrue(ps.should_alert())

    def test_alert_stale_measurement(self):
        ps = PaddockState(
            status=PaddockStatus.READY, current_measurement={"a": 1},
            last_event=None, open_grazing_event=None,
            days_since_rest=5, days_since_measurement=15,
        )
        self.assertTrue(ps.should_alert())

    def test_no_alert_fresh_measurement(self):
        ps = PaddockState(
            status=PaddockStatus.READY, current_measurement={"a": 1},
            last_event=None, open_grazing_event=None,
            days_since_rest=5, days_since_measurement=10,
        )
        self.assertFalse(ps.should_alert())

    def test_no_alert_grazing(self):
        ps = PaddockState(
            status=PaddockStatus.GRAZING, current_measurement={"a": 1},
            last_event=None, open_grazing_event={"a": 1},
            days_since_rest=None, days_since_measurement=3,
        )
        self.assertFalse(ps.should_alert())


class TestFormulaVersion(unittest.TestCase):
    def test_version_string(self):
        self.assertEqual(FORMULA_VERSION, "pasture_live.v1")

    def test_version_constant_type(self):
        self.assertIsInstance(FORMULA_VERSION, str)


class TestForageSpeciesValidation(unittest.TestCase):
    def test_all_valid_species_accepted(self):
        valid = {"brachiaria_brizantha", "brachiaria_decumbens", "panicum_maximum",
                 "mombaca", "tanzania", "zuri", "tifton", "coast_cross",
                 "capim_elefante", "other"}
        self.assertEqual(_FORAGE_SPECIES, valid)

    def test_invalid_species_not_in_set(self):
        self.assertNotIn("invalid_grass", _FORAGE_SPECIES)

    def test_species_count(self):
        self.assertEqual(len(_FORAGE_SPECIES), 10)


class TestMeasurementMethodValidation(unittest.TestCase):
    def test_all_methods_valid(self):
        methods = {"visual", "ruler", "rising_plate", "field_sampling", "external", "other"}
        for m in MeasurementMethod:
            self.assertIn(m.value, methods)

    def test_invalid_method_not_in_enum(self):
        values = {m.value for m in MeasurementMethod}
        self.assertNotIn("satellite", values)


class TestEventTypeValidation(unittest.TestCase):
    def test_all_event_types_valid(self):
        types = {"grazing_started", "grazing_finished", "rest_started",
                 "released", "marked_unavailable", "reactivated", "status_adjusted"}
        for e in EventType:
            self.assertIn(e.value, types)

    def test_invalid_event_type_not_in_enum(self):
        values = {e.value for e in EventType}
        self.assertNotIn("invalid_event", values)


class TestUtilizationPctBoundaries(unittest.TestCase):
    def test_boundary_0(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("0"), forage_species="mixed",
        )
        self.assertEqual(mr.utilization_pct, Decimal("0"))

    def test_boundary_100(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("100"), forage_species="mixed",
        )
        self.assertEqual(mr.utilization_pct, Decimal("100"))

    def test_boundary_101_rejected(self):
        with self.assertRaises(ValueError):
            MeasurementResult(
                formula_version=FORMULA_VERSION, method="visual",
                measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
                utilization_pct=Decimal("101"), forage_species="mixed",
            )


class TestAreaValidPositive(unittest.TestCase):
    def test_max_area_accepted(self):
        self.assertEqual(MAX_AREA_HA, Decimal("100000"))

    def test_max_dm_ha(self):
        self.assertEqual(MAX_DM_KG_HA, Decimal("50000"))

    def test_max_utilization(self):
        self.assertEqual(MAX_UTILIZATION_PCT, Decimal("100"))

    def test_max_rest_days(self):
        self.assertEqual(MAX_REST_DAYS, 365)


class TestRestDaysNonNegative(unittest.TestCase):
    def test_rest_days_zero(self):
        result = calculate_next_release_date(date(2026, 7, 1), 0)
        self.assertEqual(result, date(2026, 7, 1))

    def test_rest_days_1(self):
        result = calculate_next_release_date(date(2026, 7, 1), 1)
        self.assertEqual(result, date(2026, 7, 2))


class TestEdgeCases(unittest.TestCase):
    def test_very_small_area(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("50"), forage_species="mixed",
        )
        result = mr.calculate_total_dm(Decimal("0.01"), Decimal("2000"))
        self.assertEqual(result, Decimal("20.00"))

    def test_very_large_area(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("50"), forage_species="mixed",
        )
        result = mr.calculate_total_dm(Decimal("99999"), Decimal("2000"))
        self.assertEqual(result, Decimal("199998000.00"))

    def test_100pct_utilization_full_dm(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("100"), forage_species="mixed",
        )
        total = mr.calculate_total_dm(Decimal("10"), Decimal("2000"))
        usable = mr.calculate_usable_dm(Decimal("10"), Decimal("2000"), Decimal("100"))
        self.assertEqual(total, usable)

    def test_0pct_utilization_zero_dm(self):
        mr = MeasurementResult(
            formula_version=FORMULA_VERSION, method="visual",
            measured_at="2026-07-01", available_dm_kg_ha=Decimal("2000"),
            utilization_pct=Decimal("0"), forage_species="mixed",
        )
        usable = mr.calculate_usable_dm(Decimal("10"), Decimal("2000"), Decimal("0"))
        self.assertEqual(usable, Decimal("0.00"))

    def test_measurement_freshness_boundary_14_days(self):
        today = date.today()
        boundary = today - timedelta(days=14)
        self.assertTrue(is_measurement_fresh(boundary, freshness_days=14))
        expired = today - timedelta(days=15)
        self.assertFalse(is_measurement_fresh(expired, freshness_days=14))


class TestQ2Function(unittest.TestCase):
    def test_q2_rounds_to_2_places(self):
        result = _q2(Decimal("1.235"))
        self.assertEqual(result, Decimal("1.24"))

    def test_q2_already_2_places(self):
        result = _q2(Decimal("1.23"))
        self.assertEqual(result, Decimal("1.23"))

    def test_q2_integer(self):
        result = _q2(Decimal("5"))
        self.assertEqual(result, Decimal("5.00"))

    def test_q2_returns_decimal(self):
        result = _q2(Decimal("3.14159"))
        self.assertIsInstance(result, Decimal)


class TestPaddockStatusEnum(unittest.TestCase):
    def test_all_statuses(self):
        statuses = {s.value for s in PaddockStatus}
        expected = {"ready", "grazing", "resting", "attention",
                    "unavailable", "inactive", "no_measurement"}
        self.assertEqual(statuses, expected)

    def test_status_count(self):
        self.assertEqual(len(PaddockStatus), 7)


if __name__ == "__main__":
    unittest.main()
