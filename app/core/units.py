"""Catálogo de unidades e conversões dimensionais com ``Decimal``."""
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from types import MappingProxyType


class UnitError(ValueError):
    pass


class Dimension(str, Enum):
    MASS = "mass"
    GREEN_MASS = "green_mass"
    DRY_MATTER_MASS = "dry_matter_mass"
    AREA = "area"
    VOLUME = "volume"
    LIQUID_VOLUME = "liquid_volume"
    COUNT_ANIMAL = "count_animal"
    TIME = "time"
    RATIO = "ratio"
    TEMPERATURE = "temperature"
    MONEY = "money"
    DRY_MATTER_PER_ANIMAL_DAY = "dry_matter_per_animal_day"
    DRY_MATTER_PER_AREA = "dry_matter_per_area"
    MASS_PER_AREA = "mass_per_area"
    MONEY_PER_MASS = "money_per_mass"
    MONEY_PER_ANIMAL = "money_per_animal"


@dataclass(frozen=True)
class Unit:
    code: str
    symbol: str
    dimension: Dimension
    description: str
    factor_to_base: Decimal
    precision: int
    active: bool = True


def _unit(code, symbol, dimension, description, factor="1", precision=3):
    return Unit(code, symbol, dimension, description, Decimal(factor), precision)


UNITS = MappingProxyType({unit.code: unit for unit in (
    _unit("kg", "kg", Dimension.MASS, "quilograma"),
    _unit("t", "t", Dimension.MASS, "tonelada", "1000"),
    _unit("kg_green_mass", "kg MV", Dimension.GREEN_MASS, "quilograma de massa verde"),
    _unit("t_green_mass", "t MV", Dimension.GREEN_MASS, "tonelada de massa verde", "1000"),
    _unit("kg_dm", "kg MS", Dimension.DRY_MATTER_MASS, "quilograma de matéria seca"),
    _unit("t_dm", "t MS", Dimension.DRY_MATTER_MASS, "tonelada de matéria seca", "1000"),
    _unit("m2", "m²", Dimension.AREA, "metro quadrado"),
    _unit("ha", "ha", Dimension.AREA, "hectare", "10000", 4),
    _unit("m3", "m³", Dimension.VOLUME, "metro cúbico"),
    _unit("l", "L", Dimension.LIQUID_VOLUME, "litro"),
    _unit("animal", "animal", Dimension.COUNT_ANIMAL, "animal", "1", 0),
    _unit("head", "cab", Dimension.COUNT_ANIMAL, "cabeça", "1", 0),
    _unit("day", "dia", Dimension.TIME, "dia", "1", 2),
    _unit("percent", "%", Dimension.RATIO, "percentual", "0.01", 4),
    _unit("fraction", "fração", Dimension.RATIO, "fração decimal", "1", 6),
    _unit("celsius", "°C", Dimension.TEMPERATURE, "grau Celsius", "1", 2),
    _unit("percent_moisture", "% umid.", Dimension.RATIO, "percentual de umidade", "0.01", 3),
    _unit("brl", "R$", Dimension.MONEY, "real brasileiro", "1", 2),
    _unit("kg_dm_per_animal_day", "kg MS/animal/dia", Dimension.DRY_MATTER_PER_ANIMAL_DAY, "matéria seca por animal por dia"),
    _unit("kg_dm_per_ha", "kg MS/ha", Dimension.DRY_MATTER_PER_AREA, "matéria seca por hectare"),
    _unit("t_per_ha", "t/ha", Dimension.MASS_PER_AREA, "tonelada por hectare", "1000"),
    _unit("brl_per_t", "R$/t", Dimension.MONEY_PER_MASS, "reais por tonelada"),
    _unit("brl_per_animal", "R$/animal", Dimension.MONEY_PER_ANIMAL, "reais por animal"),
)})


def get_unit(code: str) -> Unit:
    try:
        unit = UNITS[code]
    except KeyError as exc:
        raise UnitError(f"Unidade desconhecida: {code}") from exc
    if not unit.active:
        raise UnitError(f"Unidade inativa: {code}")
    return unit


def convert(value: Decimal, from_code: str, to_code: str) -> Decimal:
    source = get_unit(from_code)
    target = get_unit(to_code)
    if source.dimension is not target.dimension:
        raise UnitError(
            f"Conversão incompatível: {source.dimension.value} para {target.dimension.value}"
        )
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    converted = decimal_value * source.factor_to_base / target.factor_to_base
    quantum = Decimal(1).scaleb(-target.precision)
    return converted.quantize(quantum)


def green_mass_to_dry_matter(value: Decimal, dry_matter_fraction: Decimal) -> Decimal:
    """Conversão semântica explícita; não é uma conversão dimensional automática."""
    mass = value if isinstance(value, Decimal) else Decimal(str(value))
    fraction = dry_matter_fraction if isinstance(dry_matter_fraction, Decimal) else Decimal(str(dry_matter_fraction))
    if fraction < 0 or fraction > 1:
        raise UnitError("Teor de matéria seca deve estar entre 0 e 1")
    return mass * fraction
