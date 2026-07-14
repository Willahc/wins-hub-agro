from __future__ import annotations

"""Schemas Pydantic para a API de Estoque de Ração."""
from typing import Optional
from pydantic import BaseModel, Field


class PaginationResponse(BaseModel):
    limit: int
    offset: int
    returned: int
    total: int
    has_more: bool


class FacilityCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    code: str = Field(default="", max_length=50)
    facility_type: str = "storage"
    capacity_natural_kg: str = Field(default="0", pattern=r"^\d+(\.\d+)?$")
    preferred_display_unit: str = Field(default="kg")
    location_description: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)


class FacilityUpdateRequest(BaseModel):
    name: str = Field(default="", min_length=0, max_length=200)
    code: str = Field(default="", max_length=50)
    facility_type: str = Field(default="")
    capacity_natural_kg: str = Field(default="", pattern=r"^\d+(\.\d+)?$")
    preferred_display_unit: str = Field(default="")
    location_description: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)


class FacilityResponse(BaseModel):
    public_id: str
    name: str
    code: str
    facility_type: str
    capacity_natural_kg: str
    preferred_display_unit: str
    location_description: str
    active: bool
    notes: str
    created_at: str
    updated_at: str


class FacilityListResponse(BaseModel):
    items: list[FacilityResponse]
    pagination: PaginationResponse


class LotCreateRequest(BaseModel):
    facility_uuid: str
    name: str = Field(..., min_length=1, max_length=200)
    feed_type: str = ""
    custom_feed_type: str = Field(default="", max_length=200)
    production_date: str = Field(default="")
    ensiling_date: str = Field(default="")
    source_description: str = Field(default="", max_length=500)
    initial_quantity_natural_kg: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    dry_matter_pct: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    utilization_pct: str = Field(default="100", pattern=r"^\d+(\.\d+)?$")
    initial_total_cost: str = Field(default="", pattern=r"^\d+(\.\d+)?$")
    planned_daily_use_dm_kg: str = Field(default="", pattern=r"^\d+(\.\d+)?$")
    notes: str = Field(default="", max_length=2000)


class LotUpdateRequest(BaseModel):
    name: str = Field(default="", min_length=0, max_length=200)
    notes: str = Field(default="", max_length=2000)
    planned_daily_use_dm_kg: str = Field(default="", pattern=r"^\d+(\.\d+)?$")


class LotResponse(BaseModel):
    public_id: str
    facility_uuid: str = ""
    facility_name: str = ""
    name: str
    feed_type: str
    custom_feed_type: str = ""
    production_date: str = ""
    ensiling_date: str = ""
    source_description: str = ""
    initial_quantity_natural_kg: str
    current_quantity_natural_kg: str = "0"
    dry_matter_pct: str = "0"
    utilization_pct: str = "100"
    current_physical_dm_kg: str = "0"
    current_usable_dm_kg: str = "0"
    initial_total_cost: Optional[str] = None
    average_cost_per_natural_kg: Optional[str] = None
    current_inventory_value: str = "0"
    cost_per_usable_dm_kg: Optional[str] = None
    planned_daily_use_dm_kg: Optional[str] = None
    days_remaining: Optional[str] = None
    estimated_end_date: Optional[str] = None
    status: str
    rule_version: str = ""
    notes: str = ""
    created_at: str
    updated_at: str


class LotListResponse(BaseModel):
    items: list[LotResponse]
    pagination: PaginationResponse


class MovementCreateRequest(BaseModel):
    movement_type: str
    quantity_natural_kg: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    movement_at: str = Field(default="")
    dry_matter_pct: Optional[str] = None
    utilization_pct: Optional[str] = None
    unit_cost: Optional[str] = None
    total_cost: Optional[str] = None
    reason: str = Field(default="", max_length=500)
    loss_reason: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=2000)
    request_id: str = Field(default="", max_length=200)


class MovementResponse(BaseModel):
    public_id: str
    lot_uuid: str
    movement_type: str
    quantity_natural_kg: str
    dry_matter_pct_snapshot: Optional[str] = None
    utilization_pct_snapshot: Optional[str] = None
    physical_dm_kg: Optional[str] = None
    usable_dm_kg: Optional[str] = None
    unit_cost_snapshot: Optional[str] = None
    total_cost: Optional[str] = None
    balance_after_natural_kg: Optional[str] = None
    loss_reason: str
    reason: str
    notes: str
    movement_at: str
    created_at: str


class MovementListResponse(BaseModel):
    items: list[MovementResponse]
    pagination: PaginationResponse


class WithdrawRequest(BaseModel):
    quantity_natural_kg: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    reason: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)


class RecordLossRequest(BaseModel):
    quantity_natural_kg: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    loss_reason: str = Field(..., min_length=1, max_length=200)
    reason: str = Field(default="", max_length=500)
    notes: str = Field(default="", max_length=2000)


class AdjustRequest(BaseModel):
    quantity_natural_kg: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    movement_type: str = Field(default="adjustment_positive")
    reason: str = Field(..., min_length=1, max_length=500)
    notes: str = Field(default="", max_length=2000)


class DashboardResponse(BaseModel):
    total_natural_kg: str
    total_physical_dm_kg: str
    total_usable_dm_kg: str
    total_value: str
    period_losses_kg: str
    period_losses_value: str
    open_lots: int
    lots_near_end: int
    quarantined_lots: int
    depleted_lots: int
    total_facilities: int
    active_facilities: int
    lots_by_feed_type: list[dict]
    lots_by_facility: list[dict]


class ReconciliationResponse(BaseModel):
    persisted_balance: str
    ledger_balance: str
    difference: str
    is_reconciled: bool
    movement_count: int


class AutonomySourceItem(BaseModel):
    source_public_id: str
    source_type: str
    feed_type: str
    name: str
    quantity_natural_kg: str
    dry_matter_pct: str
    utilization_pct: str
    usable_dm_kg: str
    facility_name: str
    production_date: str
    opened_at: str
    status: str
    warnings: list[str]
