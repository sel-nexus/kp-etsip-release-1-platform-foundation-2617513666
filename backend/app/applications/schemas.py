"""Validate application inventory inputs and outputs."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from bson import ObjectId
from app.auth.schemas import ObjectIdString


class ApplicationInput(BaseModel):
    """Accept editable inventory fields and enforce their boundaries."""
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    portfolioId: str
    productArea: str = Field(default="", max_length=200)
    businessOwner: str = Field(default="", max_length=200)
    technologyOwner: str = Field(default="", max_length=200)
    etsOwner: str = Field(default="", max_length=200)
    criticality: Literal["Low", "Medium", "High", "Critical"] = "Low"
    tier: int = Field(default=1, ge=1, le=4, strict=True)
    lifecycleStatus: Literal["Active", "Deprecated", "Retired"] = "Active"
    technologyStack: str = Field(default="", max_length=4000)
    repositoryLink: HttpUrl | None = None
    pipelineLink: HttpUrl | None = None
    applicationHealthScore: int = Field(default=0, ge=0, le=100, strict=True)
    qualityScore: int = Field(default=0, ge=0, le=100, strict=True)
    automationCoverage: int = Field(default=0, ge=0, le=100, strict=True)
    unitTestCoverage: int = Field(default=0, ge=0, le=100, strict=True)
    openDefects: int = Field(default=0, ge=0, strict=True)
    openCriticalDefects: int = Field(default=0, ge=0, strict=True)
    riskLevel: Literal["Low", "Medium", "High"] = "Low"

    @field_validator("portfolioId")
    @classmethod
    def valid_portfolio(cls, value: str) -> str:
        """Normalize valid portfolio references."""
        if not ObjectId.is_valid(value):
            raise ValueError("Invalid portfolio identifier")
        return str(ObjectId(value))


class ApplicationResponse(ApplicationInput):
    """Expose persisted inventory fields and identifiers."""
    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: ObjectIdString = Field(validation_alias="_id", serialization_alias="id")
    createdAt: datetime
    updatedAt: datetime
    portfolioName: str = ""


class ApplicationPage(BaseModel):
    """Return a bounded page of applications."""
    items: list[ApplicationResponse]
    total: int
    limit: int
    offset: int
