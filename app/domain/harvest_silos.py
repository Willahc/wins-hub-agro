"""Domínio do módulo de Colheita e Silos — cálculos puros e regras de negócio."""
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

RULE_VERSION = "harvest_silos.v1"

class MainCrop(str, Enum):
    MILHO = "milho"
    SORGO = "sorgo"
    CAPIM = "capim"
    CANA = "cana-de-açúcar"
    AVEIA = "aveia"
    AZEVEM = "azevém"
    OUTRA = "outra"

class PlanPurpose(str, Enum):
    SILAGEM = "silagem"
    FENO = "feno"
    PRE_SECADO = "pré-secado"
    OUTRO = "outro"

class PlanStatus(str, Enum):
    DRAFT = "draft"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELED = "canceled"
    ARCHIVED = "archived"

class CapacityStatus(str, Enum):
    AVAILABLE = "available"
    NEAR_CAPACITY = "near_capacity"
    OVER_CAPACITY = "over_capacity"
    UNKNOWN_CAPACITY = "unknown_capacity"

VALID_CROPS = frozenset({c.value for c in MainCrop})
VALID_PURPOSES = frozenset({p.value for p in PlanPurpose})
VALID_STATUSES = frozenset({s.value for s in PlanStatus})
VALID_CAPACITIES = frozenset({c.value for c in CapacityStatus})
MAX_QUANTITY_KG = Decimal("9999999999.99")

def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def calculate_gross_natural(area_ha: Decimal, yield_t_ha: Decimal) -> Decimal:
    if area_ha <= 0 or yield_t_ha <= 0:
        raise ValueError("area_and_yield_must_be_positive")
    return _q2(area_ha * yield_t_ha * Decimal("1000"))

def calculate_net_natural(gross_natural: Decimal, field_loss_pct: Decimal, ensiling_loss_pct: Decimal) -> Decimal:
    if gross_natural < 0 or not (0 <= field_loss_pct <= 100) or not (0 <= ensiling_loss_pct <= 100):
        raise ValueError("invalid_harvest_values")
    field_loss = gross_natural * (field_loss_pct / Decimal("100"))
    after_field = gross_natural - field_loss
    ensiling_loss = after_field * (ensiling_loss_pct / Decimal("100"))
    return _q2(after_field - ensiling_loss)

def calculate_dm_kg(net_natural: Decimal, dm_pct: Decimal) -> Decimal:
    if net_natural < 0 or not (0 <= dm_pct <= 100):
        raise ValueError("invalid_dry_matter_values")
    return _q2(net_natural * (dm_pct / Decimal("100")))

def calculate_projected_occupancy(stock: Decimal, allocated: Decimal) -> Decimal:
    if stock < 0 or allocated < 0:
        raise ValueError("invalid_capacity_values")
    return _q2(stock + allocated)

def calculate_occupancy_pct(projected: Decimal, capacity: Decimal | None) -> Decimal | None:
    if capacity is None or capacity <= 0:
        return None
    return _q2((projected / capacity) * Decimal("100"))

def determine_capacity_status(occupancy_pct: Decimal | None) -> str:
    if occupancy_pct is None:
        return CapacityStatus.UNKNOWN_CAPACITY.value
    if occupancy_pct < Decimal("85"):
        return CapacityStatus.AVAILABLE.value
    elif occupancy_pct <= Decimal("100"):
        return CapacityStatus.NEAR_CAPACITY.value
    else:
        return CapacityStatus.OVER_CAPACITY.value

def calculate_variation(predicted: Decimal, actual: Decimal) -> tuple[Decimal, Decimal | None]:
    diff = actual - predicted
    if predicted == 0:
        return _q2(diff), None
    pct = _q2((diff / predicted) * Decimal("100"))
    return _q2(diff), pct
