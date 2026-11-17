"""Validate portfolio requests and public responses."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from app.auth.schemas import ObjectIdString


class PortfolioInput(BaseModel):
    """Accept portfolio fields without accepting derived metrics."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    owner: str = Field(default="", max_length=200)
    description: str = Field(default="", max_length=4000)
    productArea: str = Field(default="", max_length=200)
    status: Literal["Active", "Archived"] = "Active"


class PortfolioResponse(PortfolioInput):
    """Expose persisted fields with computed application metrics."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: ObjectIdString = Field(validation_alias="_id", serialization_alias="id")
    applicationCount: int
    qualityScore: int | None


class PortfolioPage(BaseModel):
    """Return a bounded page of portfolio summaries."""
    items: list[PortfolioResponse]
    total: int
    limit: int
    offset: int


class ApplicationSummary(BaseModel):
    """Expose safe application fields for portfolio drill-down."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: ObjectIdString = Field(validation_alias="_id", serialization_alias="id")
    name: str
    portfolioId: str
    riskLevel: str | None = None
    qualityScore: int | None = None


class ApplicationPage(BaseModel):
    """Return a bounded page of linked applications."""
    items: list[ApplicationSummary]
    total: int
    limit: int
    offset: int
