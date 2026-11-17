"""Expose authenticated application inventory endpoints."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query, Response
from app.auth.router import current_session
from app.core.database import get_database
from app.applications.repository import ApplicationRepository
from app.applications.schemas import ApplicationInput, ApplicationPage, ApplicationResponse
from app.applications.service import ApplicationService

router = APIRouter(prefix="/api/applications", tags=["applications"])


def service(db=Depends(get_database)) -> ApplicationService:
    """Build the inventory service using the pooled database."""
    return ApplicationService(ApplicationRepository(db))


@router.get("", response_model=ApplicationPage)
async def list_applications(session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[ApplicationService, Depends(service)], search: str = Query("", max_length=200), portfolioId: str | None = Query(None, max_length=24), criticality: Literal["Low", "Medium", "High", "Critical"] | None = None, riskLevel: Literal["Low", "Medium", "High"] | None = None, lifecycleStatus: Literal["Active", "Deprecated", "Retired"] | None = None, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), format: Literal["json", "csv"] = "json") -> ApplicationPage | Response:
    """List or export the filtered visible inventory."""
    query = svc.query(session[0], search, portfolioId, criticality, riskLevel, lifecycleStatus)
    if format == "csv":
        return Response(await svc.csv(session[0], query), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=applications.csv"})
    return ApplicationPage.model_validate(await svc.list(session[0], query, limit, offset))


@router.post("", response_model=ApplicationResponse, status_code=201)
async def create_application(payload: ApplicationInput, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[ApplicationService, Depends(service)]) -> dict:
    """Create an audited application."""
    return await svc.save(session[0], payload)


@router.get("/{identity}", response_model=ApplicationResponse)
async def application(identity: str, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[ApplicationService, Depends(service)]) -> dict:
    """Read a visible application."""
    return await svc.detail(session[0], identity)


@router.put("/{identity}", response_model=ApplicationResponse)
async def update_application(identity: str, payload: ApplicationInput, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[ApplicationService, Depends(service)]) -> dict:
    """Update an authorized application."""
    return await svc.save(session[0], payload, identity)


@router.delete("/{identity}", status_code=204)
async def delete_application(identity: str, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[ApplicationService, Depends(service)]) -> Response:
    """Delete an application and record the event."""
    await svc.delete(session[0], identity)
    return Response(status_code=204)
