"""Schemas Pydantic para a API de Pasto Vivo."""
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


class PaddockCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    area_ha: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    forage_species: str = Field(default="mixed")
    rest_days: int = Field(default=30, ge=1, le=365)
    notes: str = Field(default="", max_length=2000)


class PaddockUpdateRequest(BaseModel):
    name: str = Field(default="", min_length=0, max_length=200)
    area_ha: str = Field(default="", pattern=r"^\d+(\.\d+)?$")
    forage_species: str = Field(default="")
    rest_days: int = Field(default=0, ge=0, le=365)
    planned_rest_days: int = Field(default=0, ge=0, le=365)
    notes: str = Field(default="", max_length=2000)


class PaddockResponse(BaseModel):
    public_id: str
    name: str
    area_ha: str
    forage_species: str
    rest_days: int
    planned_rest_days: int | None = None
    status: str
    is_inactive: bool
    is_unavailable: bool
    notes: str
    created_at: str
    updated_at: str


class PaddockSummary(BaseModel):
    public_id: str
    name: str
    area_ha: str
    forage_species: str
    rest_days: int
    status: str
    is_inactive: bool
    is_unavailable: bool
    created_at: str


class MeasurementCreateRequest(BaseModel):
    method: str = Field(default="visual")
    measured_at: str = Field(default="")
    available_dm_kg_ha: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    utilization_pct: str = Field(default="100", pattern=r"^\d+(\.\d+)?$")
    forage_species: str = Field(default="")
    estimated_height_cm: str | None = Field(default=None, pattern=r"^\d+(\.\d+)?$")
    notes: str = Field(default="", max_length=2000)


class MeasurementResponse(BaseModel):
    public_id: str
    paddock_id: int
    method: str
    measured_at: str
    available_dm_kg_ha: str
    utilization_pct: str
    total_dm_kg: str
    usable_dm_kg: str
    forage_species: str
    estimated_height_cm: str | None = None
    notes: str
    formula_version: str
    created_at: str


class MeasurementSummary(BaseModel):
    public_id: str
    method: str
    measured_at: str
    available_dm_kg_ha: str
    utilization_pct: str
    usable_dm_kg: str
    created_at: str


class EventCreateRequest(BaseModel):
    event_type: str
    notes: str = Field(default="", max_length=2000)


class EventResponse(BaseModel):
    public_id: str
    event_type: str
    status_before: str
    status_after: str
    notes: str
    created_at: str


class EventSummary(BaseModel):
    public_id: str
    event_type: str
    status_before: str
    status_after: str
    notes: str
    created_at: str


class StartGrazingRequest(BaseModel):
    notes: str = Field(default="", max_length=2000)


class FinishGrazingRequest(BaseModel):
    notes: str = Field(default="", max_length=2000)


class PaginationResponse(BaseModel):
    limit: int
    offset: int
    returned: int
    total: int
    has_more: bool


class PaddockListResponse(BaseModel):
    items: list[PaddockSummary]
    pagination: PaginationResponse


class MeasurementListResponse(BaseModel):
    items: list[MeasurementSummary]
    pagination: PaginationResponse


class EventListResponse(BaseModel):
    items: list[EventSummary]
    pagination: PaginationResponse


class DashboardResponse(BaseModel):
    total_paddocks: int
    active_paddocks: int
    grazing_count: int
    resting_count: int
    ready_count: int
    attention_count: int
    total_area_ha: str
    total_usable_dm_kg: str
    measurements_total: int


class AutonomySourceMeasurement(BaseModel):
    available_dm_kg_ha: str | None = None
    usable_dm_kg: str | None = None
    utilization_pct: str | None = None
    measured_at: str | None = None


class AutonomySourceItem(BaseModel):
    paddock_public_id: str
    name: str
    area_ha: str
    forage_species: str
    status: str
    latest_measurement: AutonomySourceMeasurement | None = None


class StartGrazingResponse(BaseModel):
    status: str


class FinishGrazingResponse(BaseModel):
    status: str
    next_release_date: str
