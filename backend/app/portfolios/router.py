"""Expose authenticated portfolio inventory endpoints."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query, Response
from app.auth.router import current_session
from app.core.database import get_database
from app.portfolios.repository import PortfolioRepository
from app.portfolios.schemas import ApplicationPage, PortfolioInput, PortfolioPage, PortfolioResponse
from app.portfolios.service import PortfolioService

router = APIRouter(prefix="/api/portfolios", tags=["portfolios"])


def service(db=Depends(get_database)) -> PortfolioService:
    """Build a service using the lifespan-owned database."""
    return PortfolioService(PortfolioRepository(db))


@router.get("", response_model=PortfolioPage)
async def list_portfolios(session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[PortfolioService, Depends(service)], search: str = Query("", max_length=200), status: Literal["Active", "Archived"] | None = None, productArea: str | None = Query(None, max_length=200), limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    """List filtered visible portfolio summaries."""
    return await svc.list(session[0], search, status, productArea, limit, offset)


@router.post("", response_model=PortfolioResponse, status_code=201)
async def create_portfolio(payload: PortfolioInput, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[PortfolioService, Depends(service)]) -> dict:
    """Create an audited portfolio."""
    return await svc.save(session[0], payload)


@router.get("/{identity}", response_model=PortfolioResponse)
async def portfolio(identity: str, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[PortfolioService, Depends(service)]) -> dict:
    """Read a visible portfolio."""
    return await svc.detail(session[0], identity)


@router.put("/{identity}", response_model=PortfolioResponse)
async def update_portfolio(identity: str, payload: PortfolioInput, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[PortfolioService, Depends(service)]) -> dict:
    """Update an authorized portfolio."""
    return await svc.save(session[0], payload, identity)


@router.delete("/{identity}", status_code=204)
async def delete_portfolio(identity: str, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[PortfolioService, Depends(service)]) -> Response:
    """Delete a portfolio and its applications."""
    await svc.delete(session[0], identity)
    return Response(status_code=204)


@router.get("/{identity}/applications", response_model=ApplicationPage)
async def linked_applications(identity: str, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[PortfolioService, Depends(service)], limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    """List applications in a visible portfolio."""
    return await svc.applications(session[0], identity, limit, offset)
