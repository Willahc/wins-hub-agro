"""Domínio de Autonomia Alimentar — fórmulas com Decimal, sem eval."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import Mapping


FORMULA_VERSION = "food_autonomy.v1"


class ScenarioStatus(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    ADEQUATE = "adequate"
    INCOMPLETE = "incomplete"


_FEED_TYPES = frozenset({
    "silage", "hay", "pre_dried", "concentrate",
    "protein_supplement", "mineral_supplement", "byproduct", "other",
})

_HERD_CATEGORIES = frozenset({
    "lactating_cows", "dry_cows", "heifers", "steers",
    "calves", "bulls", "other",
})

MAX_HEAD_COUNT = 100000
MAX_WEIGHT_KG = Decimal("3000")
MAX_INTAKE_PCT = Decimal("10")
MAX_AREA_HA = Decimal("100000")
MAX_DM_KG_HA = Decimal("50000")
MAX_QUANTITY_KG = Decimal("10000000")
MAX_TARGET_DAYS = 3650
MAX_SAFETY_PCT = Decimal("100")
MAX_NOTES_LEN = 2000


@dataclass(frozen=True)
class HerdItem:
    category: str
    head_count: int
    average_weight_kg: Decimal
    intake_pct_body_weight: Decimal
    display_order: int = 0
    custom_category_name: str = ""

    def __post_init__(self):
        if self.head_count < 0:
            raise ValueError("head_count não pode ser negativo")
        if self.average_weight_kg <= 0:
            raise ValueError("average_weight_kg deve ser positivo")
        if self.intake_pct_body_weight <= 0 or self.intake_pct_body_weight > MAX_INTAKE_PCT:
            raise ValueError(f"intake_pct_body_weight deve estar entre 0 e {MAX_INTAKE_PCT}")

    def daily_demand_dm_kg(self) -> Decimal:
        peso_total = Decimal(str(self.head_count)) * self.average_weight_kg
        return (peso_total * self.intake_pct_body_weight / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


@dataclass(frozen=True)
class PastureItem:
    name: str
    area_ha: Decimal
    available_dm_kg_ha: Decimal
    utilization_pct: Decimal
    display_order: int = 0
    notes: str = ""

    def __post_init__(self):
        if self.area_ha <= 0:
            raise ValueError("area_ha deve ser positivo")
        if self.available_dm_kg_ha < 0:
            raise ValueError("available_dm_kg_ha não pode ser negativo")
        if self.utilization_pct < 0 or self.utilization_pct > MAX_SAFETY_PCT:
            raise ValueError(f"utilization_pct deve estar entre 0 e {MAX_SAFETY_PCT}")

    def usable_dm_kg(self) -> Decimal:
        return (self.area_ha * self.available_dm_kg_ha * self.utilization_pct / Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )


@dataclass(frozen=True)
class FeedItem:
    feed_type: str
    name: str
    quantity_natural_kg: Decimal
    dry_matter_pct: Decimal
    utilization_pct: Decimal
    display_order: int = 0
    notes: str = ""

    def __post_init__(self):
        if self.feed_type not in _FEED_TYPES:
            raise ValueError(f"feed_type inválido: {self.feed_type}")
        if self.quantity_natural_kg < 0:
            raise ValueError("quantity_natural_kg não pode ser negativo")
        if self.dry_matter_pct < 0 or self.dry_matter_pct > MAX_SAFETY_PCT:
            raise ValueError(f"dry_matter_pct deve estar entre 0 e {MAX_SAFETY_PCT}")
        if self.utilization_pct < 0 or self.utilization_pct > MAX_SAFETY_PCT:
            raise ValueError(f"utilization_pct deve estar entre 0 e {MAX_SAFETY_PCT}")

    def usable_dm_kg(self) -> Decimal:
        return (
            self.quantity_natural_kg
            * self.dry_matter_pct / Decimal("100")
            * self.utilization_pct / Decimal("100")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SimulationInput:
    name: str
    reference_date: date
    target_days: int
    safety_margin_pct: Decimal
    herd: tuple[HerdItem, ...]
    pastures: tuple[PastureItem, ...]
    feeds: tuple[FeedItem, ...]
    notes: str = ""

    def __post_init__(self):
        if self.target_days < 1:
            raise ValueError("target_days deve ser >= 1")
        if self.safety_margin_pct < 0 or self.safety_margin_pct > MAX_SAFETY_PCT:
            raise ValueError(f"safety_margin_pct deve estar entre 0 e {MAX_SAFETY_PCT}")
        if not self.herd:
            raise ValueError("Cenário deve conter ao menos um item de rebanho")
        if not self.pastures and not self.feeds:
            raise ValueError("Cenário deve conter ao menos uma fonte de alimento")
        if len(self.notes) > MAX_NOTES_LEN:
            raise ValueError(f"notes excede {MAX_NOTES_LEN} caracteres")


@dataclass(frozen=True)
class SimulationResult:
    formula_version: str
    daily_demand_dm_kg: Decimal
    pasture_usable_dm_kg: Decimal
    stored_feed_usable_dm_kg: Decimal
    physical_total_dm_kg: Decimal
    reserve_dm_kg: Decimal
    planning_available_dm_kg: Decimal
    autonomy_days: Decimal
    target_days: int
    target_required_dm_kg: Decimal
    balance_dm_kg: Decimal
    balance_days: Decimal
    status: ScenarioStatus
    estimated_end_date: date | None
    warnings: tuple[str, ...]


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_autonomy(inp: SimulationInput) -> SimulationResult:
    """Calcula autonomia alimentar a partir de entradas validadas. Decimal puro."""
    warnings: list[str] = []

    # 1. Demanda diária total
    demanda_total = sum(item.daily_demand_dm_kg() for item in inp.herd)
    if demanda_total <= 0:
        warnings.append("Demanda total zero — verifique os dados do rebanho.")

    # 2. MS utilizável de pastagens
    ms_pasto = sum(item.usable_dm_kg() for item in inp.pastures)

    # 3. MS utilizável de estoques
    ms_estoque = sum(item.usable_dm_kg() for item in inp.feeds)

    # 4. Total físico
    ms_total = _q2(ms_pasto + ms_estoque)

    # 5. Reserva de segurança
    ms_reserva = _q2(ms_total * inp.safety_margin_pct / Decimal("100"))
    ms_planejamento = _q2(ms_total - ms_reserva)

    # 6. Autonomia
    if demanda_total > 0:
        autonomia = _q2(ms_planejamento / demanda_total)
    else:
        autonomia = Decimal("0")
        warnings.append("Sem demanda calculada — autonomia não definida.")

    # 7. Meta
    meta_necessaria = _q2(demanda_total * Decimal(str(inp.target_days)))
    saldo_kg = _q2(ms_planejamento - meta_necessaria)
    saldo_dias = _q2(autonomia - Decimal(str(inp.target_days)))

    # 8. Status
    if demanda_total <= 0:
        status = ScenarioStatus.INCOMPLETE
    elif autonomia < Decimal(str(inp.target_days)) * Decimal("0.5"):
        status = ScenarioStatus.CRITICAL
    elif autonomia < Decimal(str(inp.target_days)):
        status = ScenarioStatus.WARNING
    else:
        status = ScenarioStatus.ADEQUATE

    # 9. Data estimada de término
    if demanda_total > 0 and ms_planejamento > 0:
        dias_int = int(autonomia.to_integral_value(rounding=ROUND_HALF_UP))
        data_termino = inp.reference_date + timedelta(days=dias_int)
    else:
        data_termino = None

    warnings.append("Estimativa baseada nos dados informados e no consumo constante.")
    warnings.append("Resultados dependem da qualidade dos dados informados.")

    return SimulationResult(
        formula_version=FORMULA_VERSION,
        daily_demand_dm_kg=demanda_total,
        pasture_usable_dm_kg=ms_pasto,
        stored_feed_usable_dm_kg=ms_estoque,
        physical_total_dm_kg=ms_total,
        reserve_dm_kg=ms_reserva,
        planning_available_dm_kg=ms_planejamento,
        autonomy_days=autonomia,
        target_days=inp.target_days,
        target_required_dm_kg=meta_necessaria,
        balance_dm_kg=saldo_kg,
        balance_days=saldo_dias,
        status=status,
        estimated_end_date=data_termino,
        warnings=tuple(warnings),
    )
