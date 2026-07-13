"""Schemas de validação Pydantic para a listagem de fazendas da API v2."""
from pydantic import BaseModel, Field
from uuid import UUID


class OrganizationV2Summary(BaseModel):
    id: UUID
    name: str


class FarmV2Item(BaseModel):
    id: UUID
    name: str
    state: str | None = None
    municipality_code: str | None = None
    area_ha: str | None = None
    status: str
    access_level: str


class PaginationV2(BaseModel):
    limit: int = Field(..., ge=1, le=100)
    offset: int = Field(..., ge=0)
    returned: int = Field(..., ge=0)
    has_more: bool


class FarmV2ListResponse(BaseModel):
    organization: OrganizationV2Summary
    items: list[FarmV2Item]
    pagination: PaginationV2
