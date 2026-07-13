"""Domínio de Pasto Vivo — fórmulas com Decimal, sem eval."""
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from types import MappingProxyType
from typing import Mapping


FORMULA_VERSION = "pasture_live.v1"


class PaddockStatus(str, Enum):
    READY = "ready"
    GRAZING = "grazing"
    RESTING = "resting"
    ATTENTION = "attention"
    UNAVAILABLE = "unavailable"
    INACTIVE = "inactive"
    NO_MEASUREMENT = "no_measurement"


class EventType(str, Enum):
    GRAZING_STARTED = "grazing_started"
    GRAZING_FINISHED = "grazing_finished"
    REST_STARTED = "rest_started"
    RELEASED = "released"
    MARKED_UNAVAILABLE = "marked_unavailable"
    REACTIVATED = "reactivated"
    STATUS_ADJUSTED = "status_adjusted"


class MeasurementMethod(str, Enum):
    VISUAL = "visual"
    RULER = "ruler"
    RISING_PLATE = "rising_plate"
    FIELD_SAMPLING = "field_sampling"
    EXTERNAL = "external"
    OTHER = "other"


_FORAGE_SPECIES = frozenset({
    "brachiaria_brizantha", "brachiaria_decumbens", "panicum_maximum",
    "mombaca", "tanzania", "zuri", "tifton", "coast_cross",
    "capim_elefante", "other",
})

MAX_AREA_HA = Decimal("100000")
MAX_DM_KG_HA = Decimal("50000")
MAX_UTILIZATION_PCT = Decimal("100")
MAX_REST_DAYS = 365
MAX_NOTES_LEN = 2000


def _q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MeasurementResult:
    formula_version: str
    method: str
    measured_at: str
    available_dm_kg_ha: Decimal
    utilization_pct: Decimal
    forage_species: str
    estimated_height_cm: Decimal | None = None
    notes: str = ""

    def __post_init__(self):
        if self.available_dm_kg_ha < 0:
            raise ValueError("available_dm_kg_ha não pode ser negativo")
        if self.utilization_pct < 0 or self.utilization_pct > MAX_UTILIZATION_PCT:
            raise ValueError(f"utilization_pct deve estar entre 0 e {MAX_UTILIZATION_PCT}")

    def calculate_total_dm(self, area_ha: Decimal, available_dm_kg_ha: Decimal) -> Decimal:
        return _q2(area_ha * available_dm_kg_ha)

    def calculate_usable_dm(self, area_ha: Decimal, available_dm_kg_ha: Decimal,
                            utilization_pct: Decimal) -> Decimal:
        return _q2(area_ha * available_dm_kg_ha * utilization_pct / Decimal("100"))


@dataclass(frozen=True)
class PaddockState:
    status: PaddockStatus
    current_measurement: dict | None
    last_event: dict | None
    open_grazing_event: dict | None
    days_since_rest: int | None
    days_since_measurement: int | None

    def should_alert(self) -> bool:
        if self.status == PaddockStatus.NO_MEASUREMENT:
            return True
        if self.days_since_measurement is not None and self.days_since_measurement > 14:
            return True
        return False


def calculate_next_release_date(last_event_at_or_exit: date, planned_rest_days: int) -> date:
    return last_event_at_or_exit + timedelta(days=planned_rest_days)


def suggest_paddock_state(
    *,
    has_measurement: bool,
    days_since_measurement: int | None,
    days_since_rest: int | None,
    rest_days: int | None,
    is_unavailable: bool,
    is_inactive: bool,
    open_grazing: bool,
    area_ha: Decimal | None,
    available_dm_kg_ha: Decimal | None,
) -> PaddockStatus:
    if is_inactive:
        return PaddockStatus.INACTIVE
    if is_unavailable:
        return PaddockStatus.UNAVAILABLE
    if not has_measurement:
        return PaddockStatus.NO_MEASUREMENT
    if open_grazing:
        return PaddockStatus.GRAZING
    if days_since_rest is not None and rest_days is not None:
        if days_since_rest >= rest_days:
            return PaddockStatus.RESTING
    if days_since_measurement is not None and days_since_measurement > 14:
        return PaddockStatus.ATTENTION
    if area_ha is not None and available_dm_kg_ha is not None:
        if available_dm_kg_ha <= Decimal("500"):
            return PaddockStatus.ATTENTION
    return PaddockStatus.READY


def is_measurement_fresh(measured_at: date, freshness_days: int = 14) -> bool:
    from datetime import date as _date
    today = _date.today()
    delta = today - measured_at
    return delta.days <= freshness_days
