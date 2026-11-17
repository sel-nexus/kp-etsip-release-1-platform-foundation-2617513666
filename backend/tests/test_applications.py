"""Exercise application inventory against a real MongoDB replica set."""

import asyncio
import csv
import io
from bson import ObjectId
import pytest
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError, OperationFailure
from app.applications.repository import ApplicationRepository
from app.applications.schemas import ApplicationInput
from app.applications.service import ApplicationService


async def headers(http, email="admin@ketsip.local"):
    """Authenticate a seeded account."""
    response = await http.post('/api/auth/login', json={'email': email, 'password': 'Test-password-1234'})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['token']}


async def portfolio(http, auth, name):
    """Create a portfolio and return its identifier."""
    response = await http.post('/api/portfolios', headers=auth, json={'name': name})
    assert response.status_code == 201, response.text
    return response.json()['id']


async def test_crud_filter_pagination_and_audit(client):
    """Persist complete fields, filter, paginate, update and delete with audit."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Payments')
    payload = {'name': 'Ledger', 'portfolioId': pid, 'description': 'Core', 'productArea': 'Finance', 'businessOwner': 'Business', 'technologyOwner': 'Tech', 'etsOwner': 'ETS', 'criticality': 'Critical', 'tier': 2, 'lifecycleStatus': 'Active', 'technologyStack': 'Python', 'repositoryLink': 'https://example.com/repo', 'pipelineLink': 'https://example.com/build', 'applicationHealthScore': 80, 'qualityScore': 85, 'automationCoverage': 70, 'unitTestCoverage': 90, 'openDefects': 4, 'openCriticalDefects': 1, 'riskLevel': 'High'}
    assert (await http.get('/api/applications')).status_code == 401
    response = await http.post('/api/applications', json=payload, headers=admin)
    assert response.status_code == 201, response.text
    identity = response.json()['id']
    assert response.json()['unitTestCoverage'] == 90
    assert (await http.post('/api/applications', headers=admin, json=payload)).status_code == 409
    assert (await http.post('/api/applications', headers=admin, json={**payload, 'name': 'Another', 'riskLevel': 'Low'})).status_code == 201
    page = (await http.get('/api/applications', headers=admin, params={'search': 'led', 'portfolioId': pid, 'criticality': 'Critical', 'riskLevel': 'High', 'lifecycleStatus': 'Active', 'limit': 1})).json()
    assert page['total'] == 1 and page['items'][0]['portfolioName'] == 'Payments'
    assert (await http.get('/api/applications', headers=admin, params={'limit': 1, 'offset': 1})).json()['items'][0]['name'] == 'Ledger'
    detail = await http.get(f'/api/applications/{identity}', headers=admin)
    assert detail.json()['businessOwner'] == 'Business'
    updated = await http.put(f'/api/applications/{identity}', headers=admin, json={**payload, 'qualityScore': 25})
    assert updated.status_code == 200 and updated.json()['qualityScore'] == 25
    assert (await db.applications.find_one({'_id': ObjectId(identity)}))['qualityScore'] == 25
    assert (await http.delete(f'/api/applications/{identity}', headers=admin)).status_code == 204
    assert (await http.get(f'/api/applications/{identity}', headers=admin)).status_code == 404
    assert await db.audit_logs.count_documents({'entityType': 'application', 'entityId': identity}) == 3


async def test_validation_missing_and_conflicts(client):
    """Reject invalid enums, references, numeric boundaries and query limits."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'One')
    payload = {'name': 'A', 'portfolioId': pid}
    for invalid in [{'name': ' '}, {'portfolioId': 'wrong'}, {'criticality': 'Unknown'}, {'tier': 0}, {'tier': True}, {'qualityScore': 101}, {'automationCoverage': -1}, {'openDefects': -1}, {'repositoryLink': 'javascript:alert(1)'}, {'riskLevel': 'Extreme'}, {'unexpected': 'x'}]:
        assert (await http.post('/api/applications', headers=admin, json={**payload, **invalid})).status_code == 422
    assert (await http.post('/api/applications', headers=admin, json={**payload, 'portfolioId': str(ObjectId())})).status_code == 404
    assert (await http.get('/api/applications/not-id', headers=admin)).status_code == 422
    assert (await http.get(f'/api/applications/{ObjectId()}', headers=admin)).status_code == 404
    for query in ['limit=101', 'offset=-1', 'riskLevel=bad', 'portfolioId=bad']:
        assert (await http.get('/api/applications?' + query, headers=admin)).status_code == 422
    assert await db.audit_logs.count_documents({'entityType': 'application'}) == 0


async def test_scope_permissions_and_safe_export(client):
    """Enforce hard limits and live role changes on reads, writes and exports."""
    http, db = client
    admin = await headers(http)
    one = await portfolio(http, admin, 'One')
    two = await portfolio(http, admin, 'Two')
    a = (await http.post('/api/applications', headers=admin, json={'name': '=SUM(1,1)', 'portfolioId': one, 'description': '  +formula'})).json()['id']
    b = (await http.post('/api/applications', headers=admin, json={'name': 'Secret', 'portfolioId': two})).json()['id']
    leader = await headers(http, 'leader@ketsip.local')
    assert (await http.get('/api/applications', headers=leader)).json()['total'] == 0
    await db.users.update_one({'email': 'leader@ketsip.local'}, {'$set': {'portfolioAccess': [one]}})
    assert (await http.get('/api/applications', headers=leader)).json()['total'] == 1
    assert (await http.get('/api/applications', headers=leader, params={'portfolioId': two})).json()['total'] == 0
    assert (await http.get(f'/api/applications/{b}', headers=leader)).status_code == 404
    assert (await http.put(f'/api/applications/{a}', headers=leader, json={'name': 'Moved', 'portfolioId': two})).status_code == 404
    assert (await http.post('/api/applications', headers=leader, json={'name': 'No', 'portfolioId': two})).status_code == 404
    assert (await http.delete(f'/api/applications/{a}', headers=leader)).status_code == 403
    export = await http.get('/api/applications?format=csv', headers=leader)
    assert export.status_code == 200
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert len(rows) == 1 and rows[0]['name'].startswith("'=") and rows[0]['description'].startswith("'+")
    assert 'Secret' not in export.text
    assert await db.audit_logs.count_documents({'entityType': 'application', 'action': 'export'}) == 1
    readonly = await headers(http, 'readonly@ketsip.local')
    await db.roles.update_one({'name': 'Read Only'}, {'$set': {'permissions': ['view', 'create', 'edit', 'delete', 'export']}})
    assert (await http.get('/api/applications?format=csv', headers=readonly)).status_code == 403
    assert (await http.post('/api/applications', headers=readonly, json={'name': 'No', 'portfolioId': one})).status_code == 403
    engineer = await headers(http, 'engineer@ketsip.local')
    assert (await http.put(f'/api/applications/{b}', headers=engineer, json={'name': 'Edited', 'portfolioId': two})).status_code == 200
    await db.roles.update_one({'name': 'Engineer'}, {'$set': {'permissions': ['view']}})
    assert (await http.put(f'/api/applications/{b}', headers=engineer, json={'name': 'Denied', 'portfolioId': two})).status_code == 403
    assert (await http.get('/api/applications?format=csv', headers=engineer)).status_code == 403


async def test_service_audit_failure_rolls_back(client):
    """Keep application state and guard unchanged when audit insertion fails."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'One')
    user = await db.users.find_one({'email': 'admin@ketsip.local'})
    service = ApplicationService(ApplicationRepository(db))
    item = await service.save(user, ApplicationInput(name='Direct', portfolioId=pid))
    before = await db.portfolios.find_one({'_id': ObjectId(pid)})
    await db.audit_logs.create_index('entityId', unique=True, partialFilterExpression={'entityType': 'application'})
    with pytest.raises(DuplicateKeyError):
        await service.save(user, ApplicationInput(name='Changed', portfolioId=pid), str(item['_id']))
    assert (await db.applications.find_one({'_id': item['_id']}))['name'] == 'Direct'
    assert (await db.portfolios.find_one({'_id': ObjectId(pid)}))['applicationRevision'] == before['applicationRevision']
    with pytest.raises(HTTPException) as exc:
        await service.detail(user, str(ObjectId()))
    assert exc.value.status_code == 404


async def test_shared_guard_conflicts_with_delete_and_cascade(client):
    """Demonstrate transactional guard conflicts and verify deletion leaves no orphan."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Guard')
    # Hold the portfolio write in one transaction; another transaction cannot delete it.
    async with db.client.start_session() as first, db.client.start_session() as second:
        async with await first.start_transaction():
            await db.portfolios.update_one({'_id': ObjectId(pid)}, {'$inc': {'applicationRevision': 1}}, session=first)
            with pytest.raises(OperationFailure):
                async with await second.start_transaction():
                    await db.portfolios.delete_one({'_id': ObjectId(pid)}, session=second)
    created = await http.post('/api/applications', headers=admin, json={'name': 'Guarded', 'portfolioId': pid})
    assert created.status_code == 201
    assert (await http.delete(f'/api/portfolios/{pid}', headers=admin)).status_code == 204
    assert await db.applications.count_documents({'portfolioId': pid}) == 0
    assert (await http.post('/api/applications', headers=admin, json={'name': 'Too late', 'portfolioId': pid})).status_code == 404


async def test_concurrent_create_or_move_against_portfolio_deletion(client):
    """Race real application writes with cascades and require no dangling references."""
    http, db = client
    admin = await headers(http)
    source = await portfolio(http, admin, 'Race source')
    for index in range(4):
        target = await portfolio(http, admin, f'Race target {index}')
        if index % 2:
            app = await http.post('/api/applications', headers=admin, json={'name': f'Race {index}', 'portfolioId': source})
            assert app.status_code == 201
            write = http.put(f"/api/applications/{app.json()['id']}", headers=admin, json={'name': f'Race {index}', 'portfolioId': target})
        else:
            write = http.post('/api/applications', headers=admin, json={'name': f'Race {index}', 'portfolioId': target})
        written, deleted = await asyncio.gather(write, http.delete(f'/api/portfolios/{target}', headers=admin))
        assert written.status_code in (200, 201, 404), written.text
        assert deleted.status_code == 204, deleted.text
        assert await db.portfolios.find_one({'_id': ObjectId(target)}) is None
        assert await db.applications.count_documents({'portfolioId': target}) == 0
