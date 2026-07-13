import sys
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID

APP = Path(__file__).resolve().parents[1]
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from core.units import UnitError, convert, green_mass_to_dry_matter  # noqa: E402
from domain.formulas import FormulaRegistry, FormulaStatus, FormulaVersion, publish_new_version  # noqa: E402
from domain.parameters import ParameterResolver, ParameterScope, TechnicalParameterVersion, VersionStatus  # noqa: E402


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def parameter(scope, value, version=1, **scope_ids):
    return TechnicalParameterVersion(
        UUID(int=version + len(scope.value) * 100), "synthetic.rate", "Taxa sintética",
        "Valor exclusivamente sintético", Decimal(value), "fraction", "decimal",
        "synthetic_test", None, scope, version, VersionStatus.PUBLISHED, NOW,
        **scope_ids,
    )


def formula(version, status, implementation="synthetic.multiply"):
    return FormulaVersion(
        UUID(int=500 + version), "synthetic.multiply", version, implementation,
        {"value": "brl", "factor": "fraction"}, "brl", (),
        "Premissa exclusivamente sintética", None, NOW, status, 1,
    )


class UnitsParametersFormulasTest(unittest.TestCase):
    def test_valid_conversion_and_decimal_money(self):
        result = convert(Decimal("1250.50"), "kg", "t")
        self.assertIsInstance(result, Decimal)
        money = Decimal("10.10") + Decimal("0.20")
        self.assertEqual(money, Decimal("10.30"))

    def test_incompatible_dimensions_are_rejected(self):
        with self.assertRaises(UnitError):
            convert(Decimal("1"), "ha", "kg")

    def test_dry_matter_is_not_automatic_green_mass_conversion(self):
        with self.assertRaises(UnitError):
            convert(Decimal("100"), "kg_green_mass", "kg_dm")
        self.assertEqual(green_mass_to_dry_matter(Decimal("100"), Decimal("0.35")), Decimal("35.00"))

    def test_parameter_scope_validation_and_precedence(self):
        candidates = [
            parameter(ParameterScope.GLOBAL, "0.10"),
            parameter(ParameterScope.REGIONAL, "0.20", region_code="BR-SYN"),
            parameter(ParameterScope.ORGANIZATION, "0.30", organization_id=10),
            parameter(ParameterScope.FARM, "0.40", organization_id=10, farm_id=1000),
        ]
        resolved = ParameterResolver().resolve(
            candidates, organization_id=10, farm_id=1000, region_code="BR-SYN", at=NOW
        )
        self.assertEqual(resolved.value, Decimal("0.40"))
        self.assertIsNone(ParameterResolver().resolve([], organization_id=10, at=NOW))
        with self.assertRaises(ValueError):
            parameter(ParameterScope.FARM, "0.50")

    def test_published_formula_is_immutable_and_new_version_is_required(self):
        published = formula(1, FormulaStatus.PUBLISHED)
        with self.assertRaises(FrozenInstanceError):
            published.version = 2
        next_version = publish_new_version(published, formula(2, FormulaStatus.DRAFT))
        self.assertEqual((next_version.version, next_version.status), (2, FormulaStatus.PUBLISHED))
        self.assertNotEqual(next_version.checksum, published.checksum)

    def test_registry_executes_only_registered_function_without_expression_interpreter(self):
        registry = FormulaRegistry({
            "synthetic.multiply": lambda inputs, parameters: inputs["value"] * inputs["factor"]
        })
        result = registry.execute(formula(1, FormulaStatus.PUBLISHED), {"value": "12.50", "factor": "2"})
        self.assertEqual(result, Decimal("25.00"))
        with self.assertRaises(KeyError):
            registry.execute(formula(1, FormulaStatus.PUBLISHED, "unknown"), {"value": "1", "factor": "1"})


if __name__ == "__main__":
    unittest.main()
