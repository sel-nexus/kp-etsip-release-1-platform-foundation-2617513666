"""Expose scoped application and portfolio reports."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query, Response
from app.auth.router import current_session
from app.core.database import get_database
from app.applications.schemas import ApplicationPage
from app.portfolios.schemas import PortfolioPage
from app.reports.service import ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])


def service(db=Depends(get_database)) -> ReportService:
    """Bind reports to the lifespan-owned database."""
    return ReportService(db)


@router.get("/applications", response_model=ApplicationPage)
async def applications(session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[ReportService, Depends(service)], limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), format: Literal["json", "csv"] = "json") -> ApplicationPage | Response:
    """List or export visible applications."""
    if format == "csv":
        return Response(await svc.export(session[0], "applications"), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=application-report.csv"})
    return ApplicationPage.model_validate(await svc.get(session[0], "applications", limit, offset))


@router.get("/portfolios", response_model=PortfolioPage)
async def portfolios(session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[ReportService, Depends(service)], limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), format: Literal["json", "csv"] = "json") -> PortfolioPage | Response:
    """List or export visible portfolios and derived metrics."""
    if format == "csv":
        return Response(await svc.export(session[0], "portfolios"), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=portfolio-report.csv"})
    return PortfolioPage.model_validate(await svc.get(session[0], "portfolios", limit, offset))
