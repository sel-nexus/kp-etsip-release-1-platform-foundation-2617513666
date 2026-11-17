"""Expose administrator-only user, role, and audit endpoints."""

from datetime import date
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from app.admin.repository import AdminRepository
from app.admin.schemas import AuditPage, RoleInput, RolePage, RoleResponse, UserInput, UserPage, UserResponse
from app.admin.service import AdminService
from app.auth.router import current_session
from app.core.database import get_database

router = APIRouter(prefix='/api', tags=['administration'])


def service(db=Depends(get_database)) -> AdminService:
    """Build the administrative service."""
    return AdminService(AdminRepository(db))


@router.get('/users', response_model=UserPage)
async def users(session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AdminService, Depends(service)], limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    """List accounts without credential material."""
    return await svc.page(session[0], 'users', {}, limit, offset)


@router.get('/admin/portfolios')
async def assignment_portfolios(session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AdminService, Depends(service)], limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    """List portfolio identifiers and names for access assignments."""
    page = await svc.page(session[0], 'portfolios', {}, limit, offset)
    page['items'] = [{'id': str(item['_id']), 'name': item['name']} for item in page['items']]
    return page


@router.post('/users', response_model=UserResponse, status_code=201)
async def create_user(payload: UserInput, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AdminService, Depends(service)]) -> dict:
    """Create a local account."""
    return await svc.save_user(session[0], payload)


@router.get('/users/{identity}', response_model=UserResponse)
async def get_user(identity: str, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AdminService, Depends(service)]) -> dict:
    """Read a single account."""
    page = await svc.page(session[0], 'users', {'_id': svc.identifier(identity)}, 1, 0)
    if not page['items']:
        from fastapi import HTTPException
        raise HTTPException(404, 'User not found')
    return page['items'][0]


@router.put('/users/{identity}', response_model=UserResponse)
async def update_user(identity: str, payload: UserInput, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AdminService, Depends(service)]) -> dict:
    """Update account details and assignments."""
    return await svc.save_user(session[0], payload, identity)


@router.delete('/users/{identity}', status_code=204)
async def delete_user(identity: str, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AdminService, Depends(service)]) -> Response:
    """Delete an account without deleting its history."""
    await svc.delete_user(session[0], identity)
    return Response(status_code=204)


@router.get('/roles', response_model=RolePage)
async def roles(session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AdminService, Depends(service)], limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    """List configured roles."""
    return await svc.page(session[0], 'roles', {}, limit, offset)


@router.post('/roles', response_model=RoleResponse, status_code=201)
async def create_role(payload: RoleInput, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AdminService, Depends(service)]) -> dict:
    """Create a missing supported role."""
    return await svc.save_role(session[0], payload)


@router.put('/roles/{identity}', response_model=RoleResponse)
async def update_role(identity: str, payload: RoleInput, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AdminService, Depends(service)]) -> dict:
    """Edit a role's permissions and description."""
    return await svc.save_role(session[0], payload, identity)


@router.get('/audit-logs', response_model=None)
async def audit_logs(session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AdminService, Depends(service)], userId: str | None = Query(None, max_length=24), action: str | None = Query(None, max_length=100), startDate: date | None = None, endDate: date | None = None, from_date: date | None = Query(None, alias='from'), to_date: date | None = Query(None, alias='to'), limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), format: Literal['json', 'csv'] = 'json') -> AuditPage | Response:
    """Search or export audit history, restricted to administrators."""
    await svc.authorize(session[0])
    if (startDate and from_date and startDate != from_date) or (endDate and to_date and endDate != to_date):
        raise HTTPException(422, 'Conflicting date filters')
    query = svc.audit_query(userId, action, from_date or startDate, to_date or endDate)
    if format == 'csv':
        return Response(await svc.csv(session[0], query), media_type='text/csv', headers={'Content-Disposition': 'attachment; filename=audit-logs.csv'})
    return AuditPage.model_validate(await svc.page(session[0], 'audit_logs', query, limit, offset))
