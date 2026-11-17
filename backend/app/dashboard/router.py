"""Expose the authenticated executive dashboard."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from app.auth.router import current_session
from app.core.database import get_database
from app.dashboard.service import DashboardService

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class PortfolioMetrics(BaseModel):
    """Describe the metrics for one visible portfolio."""
    id: str
    name: str
    applicationCount: int
    qualityScore: int | None
    applicationsAtRisk: int


class ExecutiveMetrics(BaseModel):
    """Describe the complete filtered executive scorecard."""
    enterpriseQualityScore: int | None
    applicationHealthScore: int | None
    automationMaturityScore: int | None
    openCriticalDefects: int
    applicationsAtRisk: int
    totalApplications: int
    totalPortfolios: int
    portfolios: list[PortfolioMetrics]


def service(db=Depends(get_database)) -> DashboardService:
    """Bind the dashboard service to the pooled database."""
    return DashboardService(db)


@router.get("/executive", response_model=ExecutiveMetrics)
async def executive(session: Annotated[tuple[dict, dict], Depends(current_session)],
                    svc: Annotated[DashboardService, Depends(service)],
                    portfolioId: str | None = Query(None, max_length=24),
                    productArea: str | None = Query(None, max_length=200),
                    riskLevel: Literal["Low", "Medium", "High"] | None = None) -> dict:
    """Return metrics for visible portfolios and their matching applications."""
    return await svc.executive(session[0], portfolioId, productArea, riskLevel)
