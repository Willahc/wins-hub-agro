"""Domínio do módulo de Silagem e Estoques — cálculos puros, sem DB/HTTP."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional

FORMULA_VERSION = "feed_inventory.v1"

MAX_CAPACITY_KG = Decimal("10000000")
MAX_QUANTITY_KG = Decimal("10000000")
MAX_COST = Decimal("10000000")
MAX_NOTES_LEN = 2000
MAX_NAME_LEN = 200
MAX_CODE_LEN = 50


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q4(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


class FacilityType(str, Enum):
    SILO_TRINCHEIRA = "silo_trincheira"
    SILO_SUPERFICIE = "silo_superficie"
    SILO_BOLSA = "silo_bolsa"
    SILO_TORRE = "silo_torre"
    DEPOSITO_FENO = "deposito_feno"
    GALPAO = "galpao"
    DEPOSITO_CONCENTRADO = "deposito_concentrado"
    DEPOSITO_SUBPRODUTO = "deposito_subproduto"
    OUTRO = "outro"


class FeedType(str, Enum):
    SILAGEM_MILHO = "silagem_milho"
    SILAGEM_SORGO = "silagem_sorgo"
    SILAGEM_CAPIM = "silagem_capim"
    SILAGEM_CANA = "silagem_cana"
    FENO = "feno"
    PRE_SECADO = "pre_secado"
    CONCENTRADO = "concentrado"
    SUPLEMENTO_PROTEICO = "suplemento_proteico"
    SUPLEMENTO_MINERAL = "suplemento_mineral"
    SUBPRODUTO = "subproduto"
    POLPA_CITRICA = "polpa_citrica"
    CAROCO_ALGODAO = "caroco_algodao"
    CASQUINHA_SOJA = "casquinha_soja"
    OUTRO = "outro"


class LotStatus(str, Enum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    OPENED = "opened"
    DEPLETED = "depleted"
    QUARANTINED = "quarantined"
    ARCHIVED = "archived"


class MovementType(str, Enum):
    INITIAL_BALANCE = "initial_balance"
    ENTRY = "entry"
    WITHDRAWAL = "withdrawal"
    LOSS = "loss"
    ADJUSTMENT_POSITIVE = "adjustment_positive"
    ADJUSTMENT_NEGATIVE = "adjustment_negative"


class LossReason(str, Enum):
    DETERIORACAO = "deterioracao"
    EXPOSICAO_AR = "exposicao_ar"
    CHUVA = "chuva"
    MANEJO = "manejo"
    TRANSPORTE = "transporte"
    CONTAMINACAO = "contaminacao"
    DESCARTE = "descarte"
    AJUSTE_INVENTARIO = "ajuste_inventario"
    OUTRO = "outro"


FACILITY_TYPES = frozenset({ft.value for ft in FacilityType})
FEED_TYPES = frozenset({ft.value for ft in FeedType})
LOT_STATUSES = frozenset({ls.value for ls in LotStatus})
MOVEMENT_TYPES = frozenset({mt.value for mt in MovementType})
LOSS_REASONS = frozenset({lr.value for lr in LossReason})

ACTIVE_LOT_STATUSES = frozenset({
    LotStatus.AVAILABLE.value,
    LotStatus.RESERVED.value,
    LotStatus.OPENED.value,
})

NON_QUARANTINED_STATUSES = frozenset({
    LotStatus.AVAILABLE.value,
    LotStatus.RESERVED.value,
    LotStatus.OPENED.value,
    LotStatus.DEPLETED.value,
})

ADDITIVE_MOVEMENTS = frozenset({
    MovementType.INITIAL_BALANCE.value,
    MovementType.ENTRY.value,
    MovementType.ADJUSTMENT_POSITIVE.value,
})

SUBTRACTIVE_MOVEMENTS = frozenset({
    MovementType.WITHDRAWAL.value,
    MovementType.LOSS.value,
    MovementType.ADJUSTMENT_NEGATIVE.value,
})


def calculate_physical_dm(quantity_natural_kg: Decimal,
                         dry_matter_pct: Decimal) -> Decimal:
    """MS física = quantidade_materia_natural × MS% / 100."""
    return _q2(quantity_natural_kg * dry_matter_pct / Decimal("100"))


def calculate_usable_dm(physical_dm_kg: Decimal,
                        utilization_pct: Decimal) -> Decimal:
    """MS utilizável = MS física × aproveitamento% / 100."""
    return _q2(physical_dm_kg * utilization_pct / Decimal("100"))


def calculate_cost_per_natural_kg(initial_total_cost: Decimal | None,
                                  initial_quantity_natural_kg: Decimal) -> Decimal | None:
    """Custo por kg matéria natural = custo_total / quantidade_inicial."""
    if initial_total_cost is None or initial_total_cost <= 0:
        return None
    if initial_quantity_natural_kg <= 0:
        return None
    return _q4(initial_total_cost / initial_quantity_natural_kg)


def calculate_inventory_value(quantity_natural_kg: Decimal,
                              average_cost_per_natural_kg: Decimal | None) -> Decimal:
    """Valor do estoque = saldo × custo médio/kg."""
    if average_cost_per_natural_kg is None or average_cost_per_natural_kg <= 0:
        return Decimal("0")
    return _q2(quantity_natural_kg * average_cost_per_natural_kg)


def calculate_cost_per_usable_dm(inventory_value: Decimal,
                                  usable_dm_kg: Decimal) -> Decimal | None:
    """Custo por kg MS utilizável = valor_estoque / MS_utilizável."""
    if usable_dm_kg <= 0:
        return None
    if inventory_value <= 0:
        return None
    return _q4(inventory_value / usable_dm_kg)


def calculate_loss_value(quantity_lost_kg: Decimal,
                         average_cost_per_natural_kg: Decimal | None) -> Decimal:
    """Valor estimado da perda = quantidade_perdida × custo médio/kg."""
    if average_cost_per_natural_kg is None or average_cost_per_natural_kg <= 0:
        return Decimal("0")
    return _q2(quantity_lost_kg * average_cost_per_natural_kg)


def calculate_days_remaining(usable_dm_kg: Decimal,
                             planned_daily_use_dm_kg: Decimal | None) -> Optional[int]:
    """Dias restantes = MS utilizável / uso diário."""
    if planned_daily_use_dm_kg is None or planned_daily_use_dm_kg <= 0:
        return None
    if usable_dm_kg <= 0:
        return 0
    days = usable_dm_kg / planned_daily_use_dm_kg
    from decimal import ROUND_DOWN
    return int(days.quantize(Decimal("1"), rounding=ROUND_DOWN))


def calculate_estimated_end_date(reference_date: date,
                                 days_remaining: int | None) -> Optional[date]:
    """Data estimada de término = data_referência + dias_restantes."""
    if days_remaining is None:
        return None
    if days_remaining <= 0:
        return reference_date
    return reference_date + timedelta(days=days_remaining)


def reconcile_balance(initial: Decimal, movements: list[dict]) -> Decimal:
    """Reconstrói saldo a partir do ledger de movimentações."""
    balance = initial
    for m in movements:
        mt = m["movement_type"]
        qty = Decimal(str(m["quantity_natural_kg"]))
        if mt in ADDITIVE_MOVEMENTS:
            balance += qty
        elif mt in SUBTRACTIVE_MOVEMENTS:
            balance -= qty
    return balance
