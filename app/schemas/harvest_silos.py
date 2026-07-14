"""Schemas Pydantic para a API de Colheita e Silos."""
from datetime import date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field

# ------------------------------------------------------------------ #
# Areas                                                              #
# ------------------------------------------------------------------ #

class AreaCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    crop: str = Field(..., min_length=1, max_length=100)
    cultivar: str = Field(default="", max_length=100)
    area_ha: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    expected_yield_t_ha: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    expected_dm_pct: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    expected_harvest_date: Optional[date] = None
    notes: str = Field(default="", max_length=1000)

class AreaResponse(BaseModel):
    public_id: str
    name: str
    crop: str
    cultivar: str
    area_ha: str
    expected_yield_t_ha: str
    expected_dm_pct: str
    expected_harvest_date: Optional[date] = None
    calculated_gross_natural_kg: str
    calculated_net_natural_kg: str
    calculated_dm_kg: str
    notes: str

# ------------------------------------------------------------------ #
# Allocations                                                        #
# ------------------------------------------------------------------ #

class AllocationCreateRequest(BaseModel):
    facility_uuid: UUID
    expected_natural_kg: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    percentage: str = Field(..., pattern=r"^\d+(\.\d+)?$")

class AllocationResponse(BaseModel):
    public_id: str
    facility_uuid: str
    facility_name: str
    expected_quantity_natural_kg: str
    actual_quantity_natural_kg: Optional[str] = None
    expected_percentage: str
    capacity_snapshot_kg: Optional[str] = None
    current_stock_snapshot_kg: Optional[str] = None
    projected_occupancy_kg: Optional[str] = None
    projected_occupancy_pct: Optional[str] = None
    capacity_status: str
    created_feed_lot_uuid: Optional[str] = None

# ------------------------------------------------------------------ #
# Plans                                                              #
# ------------------------------------------------------------------ #

class PlanCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    main_crop: str = Field(..., min_length=1, max_length=100)
    purpose: str = Field(..., min_length=1, max_length=100)
    expected_start_date: date
    expected_end_date: date
    expected_field_loss_pct: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    expected_ensiling_loss_pct: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    notes: str = Field(default="", max_length=2000)
    areas: list[AreaCreateRequest] = Field(default=[])
    allocations: list[AllocationCreateRequest] = Field(default=[])

class PlanUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    main_crop: str = Field(..., min_length=1, max_length=100)
    purpose: str = Field(..., min_length=1, max_length=100)
    expected_start_date: date
    expected_end_date: date
    expected_field_loss_pct: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    expected_ensiling_loss_pct: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    notes: str = Field(default="", max_length=2000)
    areas: list[AreaCreateRequest] = Field(default=[])
    allocations: list[AllocationCreateRequest] = Field(default=[])

class PlanResponse(BaseModel):
    public_id: str
    name: str
    main_crop: str
    purpose: str
    expected_start_date: date
    expected_end_date: date
    expected_field_loss_pct: str
    expected_ensiling_loss_pct: str
    expected_gross_natural_kg: str
    expected_net_natural_kg: str
    expected_dm_kg: str
    actual_start_date: Optional[date] = None
    actual_end_date: Optional[date] = None
    actual_natural_kg: Optional[str] = None
    actual_dm_pct: Optional[str] = None
    actual_loss_pct: Optional[str] = None
    status: str
    notes: str
    rule_version: str
    completed_at: Optional[str] = None
    created_at: str
    updated_at: str
    areas: list[AreaResponse] = Field(default=[])
    allocations: list[AllocationResponse] = Field(default=[])

class PlanListResponse(BaseModel):
    items: list[PlanResponse]
    total: int

# ------------------------------------------------------------------ #
# Simulation and Operations                                          #
# ------------------------------------------------------------------ #

class SimulationResponse(BaseModel):
    expected_gross_natural_kg: str
    expected_net_natural_kg: str
    expected_dm_kg: str
    allocations: list[AllocationResponse]

class StartRequest(BaseModel):
    actual_start_date: date

class AllocationCompleteRequest(BaseModel):
    facility_uuid: UUID
    actual_natural_kg: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    lot_name: str = Field(..., min_length=1, max_length=200)
    feed_type: str = Field(..., min_length=1, max_length=100)
    utilization_pct: str = Field(default="100", pattern=r"^\d+(\.\d+)?$")
    cost: Optional[str] = Field(default=None, pattern=r"^\d+(\.\d+)?$")
    notes: str = Field(default="", max_length=2000)

class CompleteRequest(BaseModel):
    actual_start_date: date
    actual_end_date: date
    actual_natural_kg: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    actual_dm_pct: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    actual_loss_pct: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    allocations: list[AllocationCompleteRequest] = Field(default=[])
    request_id: str = Field(default="", max_length=200)

# ------------------------------------------------------------------ #
# Dashboard                                                          #
# ------------------------------------------------------------------ #

class DashboardResponse(BaseModel):
    active_plans_count: int
    planned_area_ha: str
    expected_gross_natural_kg: str
    expected_net_natural_kg: str
    expected_dm_kg: str
    capacity_needed_kg: str
    capacity_available_kg: str
    over_capacity_plans_count: int
    upcoming_cuts_count: int
