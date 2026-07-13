"""Schemas Pydantic para a API de Autonomia Alimentar."""
from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


class HerdItemSchema(BaseModel):
    category: str
    custom_category_name: str = ""
    head_count: int = Field(..., ge=0, le=100000)
    average_weight_kg: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    intake_pct_body_weight: str = Field(..., pattern=r"^\d+(\.\d+)?$")


class PastureItemSchema(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    area_ha: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    available_dm_kg_ha: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    utilization_pct: str = Field(default="50", pattern=r"^\d+(\.\d+)?$")
    notes: str = ""


class FeedItemSchema(BaseModel):
    feed_type: str
    name: str = Field(..., min_length=1, max_length=200)
    quantity_natural_kg: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    dry_matter_pct: str = Field(..., pattern=r"^\d+(\.\d+)?$")
    utilization_pct: str = Field(default="100", pattern=r"^\d+(\.\d+)?$")
    notes: str = ""


class SimulationRequest(BaseModel):
    name: str = Field(default="Cenário", max_length=200)
    reference_date: date
    target_days: int = Field(default=90, ge=1, le=3650)
    safety_margin_pct: str = Field(default="0", pattern=r"^\d+(\.\d+)?$")
    herd: list[HerdItemSchema] = Field(..., min_length=1)
    pastures: list[PastureItemSchema] = Field(default=[])
    feeds: list[FeedItemSchema] = Field(default=[])
    notes: str = Field(default="", max_length=2000)

    def model_post_init(self, __context):
        if not self.pastures and not self.feeds:
            raise ValueError("Informe ao menos uma pastagem ou estoque")


class ScenarioCreateRequest(BaseModel):
    name: str = Field(default="Cenário", max_length=200)
    reference_date: date
    target_days: int = Field(default=90, ge=1, le=3650)
    safety_margin_pct: str = Field(default="0", pattern=r"^\d+(\.\d+)?$")
    herd: list[HerdItemSchema] = Field(..., min_length=1)
    pastures: list[PastureItemSchema] = Field(default=[])
    feeds: list[FeedItemSchema] = Field(default=[])
    notes: str = Field(default="", max_length=2000)


class ScenarioUpdateRequest(BaseModel):
    name: str = Field(default="Cenário", max_length=200)
    reference_date: date
    target_days: int = Field(default=90, ge=1, le=3650)
    safety_margin_pct: str = Field(default="0", pattern=r"^\d+(\.\d+)?$")
    herd: list[HerdItemSchema] = Field(..., min_length=1)
    pastures: list[PastureItemSchema] = Field(default=[])
    feeds: list[FeedItemSchema] = Field(default=[])
    notes: str = Field(default="", max_length=2000)


class SimulationResponse(BaseModel):
    formula_version: str
    daily_demand_dm_kg: str
    pasture_usable_dm_kg: str
    stored_feed_usable_dm_kg: str
    physical_total_dm_kg: str
    reserve_dm_kg: str
    planning_available_dm_kg: str
    autonomy_days: str
    target_days: int
    target_required_dm_kg: str
    balance_dm_kg: str
    balance_days: str
    status: str
    estimated_end_date: str | None
    warnings: list[str]


class ScenarioSummary(BaseModel):
    public_id: str
    name: str
    reference_date: str
    target_days: int
    status: str
    autonomy_days: str
    formula_version: str
    created_at: str


class PaginationResponse(BaseModel):
    limit: int
    offset: int
    returned: int
    total: int
    has_more: bool


class ScenarioListResponse(BaseModel):
    items: list[ScenarioSummary]
    pagination: PaginationResponse
