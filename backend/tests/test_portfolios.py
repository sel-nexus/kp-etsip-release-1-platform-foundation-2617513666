"""Exercise portfolio policies and persistence against a real replica set."""

from bson import ObjectId
import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from app.portfolios.repository import PortfolioRepository
from app.portfolios.schemas import PortfolioInput
from app.portfolios.service import PortfolioService


async def headers(http, email="admin@ketsip.local"):
    """Authenticate a seeded user."""
    response = await http.post("/api/auth/login", json={"email": email, "password": "Test-password-1234"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


async def test_http_crud_metrics_pagination_and_cascade(client):
    """Persist records, calculate metrics, paginate, update and cascade with audit."""
    http, db = client
    auth = await headers(http)
    assert (await http.get('/api/portfolios')).status_code == 401
    payload = {"name": "Payments", "owner": "Team", "productArea": "Finance", "description": "Core", "status": "Active"}
    created = await http.post('/api/portfolios', headers=auth, json=payload)
    assert created.status_code == 201, created.text
    portfolio = created.json()
    pid = portfolio['id']
    assert portfolio['applicationCount'] == 0 and portfolio['qualityScore'] is None
    assert (await http.post('/api/portfolios', headers=auth, json=payload)).status_code == 409
    assert (await http.post('/api/portfolios', headers=auth, json={**payload, 'name': 'Other', 'status': 'Archived'})).status_code == 201
    await db.applications.insert_many([{'name': 'A', 'portfolioId': pid, 'qualityScore': 80, 'riskLevel': 'Low'}, {'name': 'B', 'portfolioId': pid, 'qualityScore': 90, 'riskLevel': 'High'}])
    result = (await http.get('/api/portfolios', headers=auth, params={'search': 'pay', 'productArea': 'Finance', 'status': 'Active', 'limit': 1})).json()
    assert result['total'] == 1 and result['items'][0]['applicationCount'] == 2 and result['items'][0]['qualityScore'] == 85
    apps = (await http.get(f'/api/portfolios/{pid}/applications', headers=auth, params={'limit': 1, 'offset': 1})).json()
    assert apps['total'] == 2 and apps['items'][0]['name'] == 'B'
    assert (await http.put(f'/api/portfolios/{pid}', headers=auth, json={**payload, 'name': 'Updated'})).json()['name'] == 'Updated'
    assert (await db.portfolios.find_one({'_id': ObjectId(pid)}))['name'] == 'Updated'
    assert (await http.delete(f'/api/portfolios/{pid}', headers=auth)).status_code == 204
    assert await db.applications.count_documents({'portfolioId': pid}) == 0
    assert await db.audit_logs.count_documents({'entityId': pid, 'entityType': 'portfolio'}) == 3
    assert (await http.get(f'/api/portfolios/{pid}', headers=auth)).status_code == 404


async def test_invalid_input_and_missing(client):
    """Reject malformed inputs, identifiers and invalid pagination."""
    http, _ = client
    auth = await headers(http)
    for body in ({'name': '  '}, {'name': 'A', 'status': 'bad'}, {'name': {'$ne': ''}}, {'name': 'A', 'qualityScore': 90}):
        assert (await http.post('/api/portfolios', headers=auth, json=body)).status_code == 422
    assert (await http.get('/api/portfolios/not-an-id', headers=auth)).status_code == 422
    assert (await http.get(f'/api/portfolios/{ObjectId()}', headers=auth)).status_code == 404
    assert (await http.get('/api/portfolios?limit=101', headers=auth)).status_code == 422
    assert (await http.get('/api/portfolios?offset=-1', headers=auth)).status_code == 422


async def test_scope_and_live_permissions(client):
    """Constrain leaders, deny elevated roles and apply permission changes immediately."""
    http, db = client
    admin = await headers(http)
    one = (await http.post('/api/portfolios', headers=admin, json={'name': 'One'})).json()['id']
    two = (await http.post('/api/portfolios', headers=admin, json={'name': 'Two'})).json()['id']
    leader = await headers(http, 'leader@ketsip.local')
    assert (await http.get('/api/portfolios', headers=leader)).json()['total'] == 0
    await db.users.update_one({'email': 'leader@ketsip.local'}, {'$set': {'portfolioAccess': [one]}})
    assert (await http.get('/api/portfolios', headers=leader)).json()['total'] == 1
    assert (await http.get(f'/api/portfolios/{two}', headers=leader)).status_code == 404
    assert (await http.get(f'/api/portfolios/{two}/applications', headers=leader)).status_code == 404
    assert (await http.put(f'/api/portfolios/{one}', headers=leader, json={'name': 'Changed'})).status_code == 200
    assert (await http.put(f'/api/portfolios/{two}', headers=leader, json={'name': 'Changed'})).status_code == 404
    assert (await http.post('/api/portfolios', headers=leader, json={'name': 'No'})).status_code == 403
    assert (await http.delete(f'/api/portfolios/{one}', headers=leader)).status_code == 403
    await db.roles.update_one({'name': 'Portfolio Leader'}, {'$set': {'permissions': ['view', 'delete']}})
    assert (await http.put(f'/api/portfolios/{one}', headers=leader, json={'name': 'No'})).status_code == 403
    assert (await http.delete(f'/api/portfolios/{one}', headers=leader)).status_code == 403
    engineer = await headers(http, 'engineer@ketsip.local')
    assert (await http.get('/api/portfolios', headers=engineer)).json()['total'] == 2
    assert (await http.put(f'/api/portfolios/{one}', headers=engineer, json={'name': 'No'})).status_code == 403
    await db.roles.update_one({'name': 'Administrator'}, {'$set': {'permissions': []}})
    assert (await http.get('/api/portfolios', headers=admin)).status_code == 403


async def test_direct_service_and_transaction_rollback(client):
    """Exercise service policy and prove audit failure rolls back a cascade."""
    _, db = client
    user = await db.users.find_one({'email': 'admin@ketsip.local'})
    service = PortfolioService(PortfolioRepository(db))
    created = await service.save(user, PortfolioInput(name='Direct'))
    pid = str(created['_id'])
    await db.applications.insert_one({'name': 'Linked', 'portfolioId': pid, 'qualityScore': 50})
    assert (await service.detail(user, pid))['applicationCount'] == 1
    with pytest.raises(HTTPException) as error:
        await service.detail(user, str(ObjectId()))
    assert error.value.status_code == 404
    # A unique index makes the audit insert fail after the deletes inside the transaction.
    await db.audit_logs.create_index('entityId', unique=True, partialFilterExpression={'entityType': 'portfolio'})
    with pytest.raises(DuplicateKeyError):
        await service.delete(user, pid)
    assert await db.portfolios.find_one({'_id': ObjectId(pid)}) is not None
    assert await db.applications.count_documents({'portfolioId': pid}) == 1
