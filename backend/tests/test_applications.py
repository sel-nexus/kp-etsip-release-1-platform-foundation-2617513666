"""Exercise application inventory against a real MongoDB replica set."""

import asyncio
import csv
import io
from bson import ObjectId
import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
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
    response = await http.get('/api/applications', headers=admin, params={'search': 'led', 'portfolioId': pid, 'criticality': 'Critical', 'riskLevel': 'High', 'lifecycleStatus': 'Active', 'limit': 1})
    assert response.status_code == 200
    page = response.json()
    assert page['total'] == 1 and page['items'][0]['portfolioName'] == 'Payments'
    response = await http.get('/api/applications', headers=admin, params={'limit': 1, 'offset': 1})
    assert response.status_code == 200
    assert response.json()['items'][0]['name'] == 'Ledger'
    detail = await http.get(f'/api/applications/{identity}', headers=admin)
    assert detail.status_code == 200
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


@pytest.mark.parametrize('missing', ['name', 'portfolioId'])
async def test_required_application_fields_are_individually_required(client, missing):
    """Reject each missing required field without creating inventory or audit entries."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Required fields')
    payload = {'name': 'Valid', 'portfolioId': pid}
    del payload[missing]
    response = await http.post('/api/applications', headers=admin, json=payload)
    assert response.status_code == 422
    assert any(error['loc'] == ['body', missing] and error['type'] == 'missing' for error in response.json()['detail'])
    assert await db.applications.count_documents({}) == 0
    assert await db.audit_logs.count_documents({'entityType': 'application'}) == 0


async def test_whitespace_application_name_is_rejected_without_writes(client):
    """Reject whitespace-only names on create and edit without changing MongoDB."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Whitespace validation')
    created = await http.post('/api/applications', headers=admin, json={'name': 'Existing', 'portfolioId': pid})
    assert created.status_code == 201
    apps = await db.applications.find().sort('_id', 1).to_list(None)
    portfolios = await db.portfolios.find().sort('_id', 1).to_list(None)
    audit = await db.audit_logs.find().sort('_id', 1).to_list(None)
    payload = {'name': ' \t\n ', 'portfolioId': pid}
    for response in (await http.post('/api/applications', headers=admin, json=payload),
                     await http.put('/api/applications/' + created.json()['id'], headers=admin, json=payload)):
        assert response.status_code == 422
        assert any(error['loc'] == ['body', 'name'] and error['type'] == 'string_too_short'
                   for error in response.json()['detail'])
    assert await db.applications.find().sort('_id', 1).to_list(None) == apps
    assert await db.portfolios.find().sort('_id', 1).to_list(None) == portfolios
    assert await db.audit_logs.find().sort('_id', 1).to_list(None) == audit


@pytest.mark.parametrize(('field', 'maximum'), [
    ('name', 200), ('productArea', 200), ('businessOwner', 200),
    ('technologyOwner', 200), ('etsOwner', 200), ('description', 4000),
    ('technologyStack', 4000),
])
async def test_application_text_length_boundary(client, field, maximum):
    """Accept the documented maximum and reject one extra character atomically."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Length boundary')
    payload = {'name': 'Valid', 'portfolioId': pid, field: 'x' * maximum}
    created = await http.post('/api/applications', headers=admin, json=payload)
    assert created.status_code == 201, created.text
    identity = created.json()['id']
    assert created.json()[field] == 'x' * maximum
    before = await db.applications.find_one({'_id': ObjectId(identity)})
    response = await http.put(f'/api/applications/{identity}', headers=admin, json={**payload, field: 'x' * (maximum + 1)})
    assert response.status_code == 422
    assert any(error['loc'] == ['body', field] and error['type'] == 'string_too_long' for error in response.json()['detail'])
    assert await db.applications.find_one({'_id': ObjectId(identity)}) == before
    assert await db.audit_logs.count_documents({'entityType': 'application', 'entityId': identity}) == 1


@pytest.mark.parametrize('field', ['name', 'portfolioId', 'description', 'qualityScore'])
async def test_application_rejects_mongo_operator_objects(client, field):
    """Reject operator objects rather than interpreting them as query or update expressions."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Operator boundary')
    payload = {'name': 'Existing', 'portfolioId': pid, 'description': 'Original', 'qualityScore': 50}
    created = await http.post('/api/applications', headers=admin, json=payload)
    assert created.status_code == 201
    identity = created.json()['id']
    before = await db.applications.find_one({'_id': ObjectId(identity)})
    bad = {**payload, field: {'$ne': None}}
    for response in (await http.post('/api/applications', headers=admin, json=bad),
                     await http.put(f'/api/applications/{identity}', headers=admin, json=bad)):
        assert response.status_code == 422
        assert any(error['loc'] == ['body', field] for error in response.json()['detail'])
    assert await db.applications.count_documents({}) == 1
    assert await db.applications.find_one({'_id': ObjectId(identity)}) == before
    assert await db.audit_logs.count_documents({'entityType': 'application', 'entityId': identity}) == 1


async def test_application_search_treats_regex_metacharacters_literally(client):
    """A regex-looking string matches only the name containing those characters."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Search')
    for name in ('Service .* [x]', 'Service anything x', 'Unrelated'):
        response = await http.post('/api/applications', headers=admin, json={'name': name, 'portfolioId': pid})
        assert response.status_code == 201
    for search in ('.* [x]', '.*'):
        response = await http.get('/api/applications', headers=admin, params={'search': search})
        assert response.status_code == 200
        assert response.json()['total'] == 1
        assert [item['name'] for item in response.json()['items']] == ['Service .* [x]']
    assert await db.applications.count_documents({}) == 3


async def test_application_script_text_round_trips_as_json_data(client):
    """Return untrusted text as JSON, not HTML; UI escaping is a separate concern."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Text')
    text = '<script>alert("stored-xss")</script>'
    response = await http.post('/api/applications', headers=admin, json={'name': 'XSS text', 'portfolioId': pid, 'description': text})
    assert response.status_code == 201
    identity = response.json()['id']
    assert response.json()['description'] == text
    assert (await db.applications.find_one({'_id': ObjectId(identity)}))['description'] == text
    detail = await http.get(f'/api/applications/{identity}', headers=admin)
    assert detail.status_code == 200
    assert detail.headers['content-type'].startswith('application/json')
    assert detail.json()['description'] == text
    listing = await http.get('/api/applications', headers=admin, params={'search': 'XSS text'})
    assert listing.status_code == 200
    assert listing.headers['content-type'].startswith('application/json')
    assert listing.json()['total'] == 1 and listing.json()['items'][0]['description'] == text


async def test_application_missing_valid_id_put_delete_are_atomic(client):
    """A valid absent ID produces 404 and no inventory, guard or audit changes."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Missing target')
    missing = str(ObjectId())
    before = await db.portfolios.find_one({'_id': ObjectId(pid)})
    for response in (await http.put(f'/api/applications/{missing}', headers=admin, json={'name': 'Missing', 'portfolioId': pid}),
                     await http.delete(f'/api/applications/{missing}', headers=admin)):
        assert response.status_code == 404
        assert response.json() == {'detail': 'Application not found'}
    assert await db.applications.count_documents({}) == 0
    assert await db.portfolios.find_one({'_id': ObjectId(pid)}) == before
    assert await db.audit_logs.count_documents({'entityType': 'application'}) == 0


async def test_scope_permissions_and_safe_export(client):
    """Enforce hard limits and live role changes on reads, writes and exports."""
    http, db = client
    admin = await headers(http)
    one = await portfolio(http, admin, 'One')
    two = await portfolio(http, admin, 'Two')
    response = await http.post('/api/applications', headers=admin, json={'name': '=SUM(1,1)', 'portfolioId': one, 'description': '  +formula'})
    assert response.status_code == 201
    a = response.json()['id']
    response = await http.post('/api/applications', headers=admin, json={'name': 'Secret', 'portfolioId': two})
    assert response.status_code == 201
    b = response.json()['id']
    leader = await headers(http, 'leader@ketsip.local')
    response = await http.get('/api/applications', headers=leader)
    assert response.status_code == 200 and response.json()['total'] == 0
    await db.users.update_one({'email': 'leader@ketsip.local'}, {'$set': {'portfolioAccess': [one]}})
    response = await http.get('/api/applications', headers=leader)
    assert response.status_code == 200 and response.json()['total'] == 1
    response = await http.get('/api/applications', headers=leader, params={'portfolioId': two})
    assert response.status_code == 200 and response.json()['total'] == 0
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


@pytest.mark.parametrize('operation', ['create', 'edit'])
async def test_save_duplicate_name_returns_conflict_without_writes(client, operation):
    """Both save paths translate the name index violation and roll back the guard."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Duplicate names')
    first = await http.post('/api/applications', headers=admin, json={'name': 'Taken', 'portfolioId': pid})
    second = await http.post('/api/applications', headers=admin, json={'name': 'Other', 'portfolioId': pid})
    assert first.status_code == second.status_code == 201
    apps = await db.applications.find().sort('_id', 1).to_list(None)
    portfolios = await db.portfolios.find().sort('_id', 1).to_list(None)
    audit = await db.audit_logs.find().sort('_id', 1).to_list(None)
    payload = {'name': 'Taken', 'portfolioId': pid}
    if operation == 'create':
        response = await http.post('/api/applications', headers=admin, json=payload)
    else:
        response = await http.put('/api/applications/' + second.json()['id'], headers=admin, json=payload)
    assert response.status_code == 409
    assert response.json() == {'detail': 'Application name already exists'}
    assert await db.applications.find().sort('_id', 1).to_list(None) == apps
    assert await db.portfolios.find().sort('_id', 1).to_list(None) == portfolios
    assert await db.audit_logs.find().sort('_id', 1).to_list(None) == audit


@pytest.mark.parametrize('operation', ['create', 'edit'])
async def test_save_missing_target_portfolio_returns_404_without_writes(client, operation):
    """A valid but absent destination is distinguished from an absent application."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Existing destination')
    created = await http.post('/api/applications', headers=admin, json={'name': 'Existing', 'portfolioId': pid})
    assert created.status_code == 201
    apps = await db.applications.find().sort('_id', 1).to_list(None)
    portfolios = await db.portfolios.find().sort('_id', 1).to_list(None)
    audit = await db.audit_logs.find().sort('_id', 1).to_list(None)
    payload = {'name': 'Changed', 'portfolioId': str(ObjectId())}
    if operation == 'create':
        response = await http.post('/api/applications', headers=admin, json=payload)
    else:
        response = await http.put('/api/applications/' + created.json()['id'], headers=admin, json=payload)
    assert response.status_code == 404
    assert response.json() == {'detail': 'Portfolio not found'}
    assert await db.applications.find().sort('_id', 1).to_list(None) == apps
    assert await db.portfolios.find().sort('_id', 1).to_list(None) == portfolios
    assert await db.audit_logs.find().sort('_id', 1).to_list(None) == audit


@pytest.mark.parametrize('operation', ['create', 'edit'])
async def test_save_propagates_non_name_duplicate_key_and_rolls_back(client, operation):
    """A real unique-index failure on another field is not mislabeled as a name conflict."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'Other unique index')
    actor = await db.users.find_one({'email': 'admin@ketsip.local'})
    service = ApplicationService(ApplicationRepository(db))
    first = await service.save(actor, ApplicationInput(name='First', portfolioId=pid, productArea='Taken'))
    second = await service.save(actor, ApplicationInput(name='Second', portfolioId=pid, productArea='Other'))
    await db.applications.create_index('productArea', unique=True)
    apps = await db.applications.find().sort('_id', 1).to_list(None)
    portfolios = await db.portfolios.find().sort('_id', 1).to_list(None)
    audit = await db.audit_logs.find().sort('_id', 1).to_list(None)
    payload = ApplicationInput(name='Third' if operation == 'create' else 'Second', portfolioId=pid, productArea='Taken')
    with pytest.raises(DuplicateKeyError) as exc:
        await service.save(actor, payload, str(second['_id']) if operation == 'edit' else None)
    assert exc.value.details['keyPattern'] == {'productArea': 1}
    assert first['_id'] != second['_id']
    assert await db.applications.find().sort('_id', 1).to_list(None) == apps
    assert await db.portfolios.find().sort('_id', 1).to_list(None) == portfolios
    assert await db.audit_logs.find().sort('_id', 1).to_list(None) == audit


@pytest.mark.parametrize('operation', ['create', 'edit'])
async def test_non_name_unique_collision_returns_http_500_without_writes(client, operation):
    """An unrelated Mongo index collision is not exposed or translated to a name conflict."""
    http, db = client
    admin = await headers(http)
    pid = await portfolio(http, admin, 'HTTP unique index')
    first = await http.post('/api/applications', headers=admin,
                            json={'name': 'First', 'portfolioId': pid, 'productArea': 'Taken'})
    second = await http.post('/api/applications', headers=admin,
                             json={'name': 'Second', 'portfolioId': pid, 'productArea': 'Other'})
    assert first.status_code == second.status_code == 201
    await db.applications.create_index('productArea', unique=True)
    apps = await db.applications.find().sort('_id', 1).to_list(None)
    portfolios = await db.portfolios.find().sort('_id', 1).to_list(None)
    audit = await db.audit_logs.find().sort('_id', 1).to_list(None)
    payload = {'name': 'Third' if operation == 'create' else 'Second',
               'portfolioId': pid, 'productArea': 'Taken'}
    async with AsyncClient(transport=ASGITransport(app=http._transport.app, raise_app_exceptions=False),
                           base_url='http://test') as boundary:
        if operation == 'create':
            response = await boundary.post('/api/applications', headers=admin, json=payload)
        else:
            response = await boundary.put('/api/applications/' + second.json()['id'], headers=admin, json=payload)
    assert response.status_code == 500
    assert response.text == 'Internal Server Error'
    assert await db.applications.find().sort('_id', 1).to_list(None) == apps
    assert await db.portfolios.find().sort('_id', 1).to_list(None) == portfolios
    assert await db.audit_logs.find().sort('_id', 1).to_list(None) == audit


@pytest.mark.parametrize('case', ['out_of_scope_create', 'out_of_scope_destination', 'out_of_scope_existing',
                                 'edit_permission_denied', 'create_permission_denied'])
async def test_save_authorization_and_scope_fail_closed_without_writes(client, case):
    """Deny unauthorized writes at both the source and destination scope boundaries."""
    http, db = client
    admin = await headers(http)
    one = await portfolio(http, admin, 'Visible')
    two = await portfolio(http, admin, 'Hidden')
    visible = await http.post('/api/applications', headers=admin, json={'name': 'Visible app', 'portfolioId': one})
    hidden = await http.post('/api/applications', headers=admin, json={'name': 'Hidden app', 'portfolioId': two})
    assert visible.status_code == hidden.status_code == 201
    leader = await headers(http, 'leader@ketsip.local')
    await db.users.update_one({'email': 'leader@ketsip.local'}, {'$set': {'portfolioAccess': [one]}})
    if case in ('edit_permission_denied', 'create_permission_denied'):
        await db.roles.update_one({'name': 'Portfolio Leader'}, {'$set': {'permissions': ['view']}})
    apps = await db.applications.find().sort('_id', 1).to_list(None)
    portfolios = await db.portfolios.find().sort('_id', 1).to_list(None)
    audit = await db.audit_logs.find().sort('_id', 1).to_list(None)
    if case == 'out_of_scope_create':
        response = await http.post('/api/applications', headers=leader, json={'name': 'Denied', 'portfolioId': two})
        expected = (404, 'Portfolio not found')
    elif case == 'out_of_scope_destination':
        response = await http.put('/api/applications/' + visible.json()['id'], headers=leader, json={'name': 'Denied', 'portfolioId': two})
        expected = (404, 'Portfolio not found')
    elif case == 'out_of_scope_existing':
        response = await http.put('/api/applications/' + hidden.json()['id'], headers=leader, json={'name': 'Denied', 'portfolioId': one})
        expected = (404, 'Application not found')
    elif case == 'edit_permission_denied':
        response = await http.put('/api/applications/' + visible.json()['id'], headers=leader, json={'name': 'Denied', 'portfolioId': one})
        expected = (403, 'Insufficient permissions')
    else:
        response = await http.post('/api/applications', headers=leader, json={'name': 'Denied', 'portfolioId': one})
        expected = (403, 'Insufficient permissions')
    assert response.status_code == expected[0]
    assert response.json() == {'detail': expected[1]}
    assert await db.applications.find().sort('_id', 1).to_list(None) == apps
    assert await db.portfolios.find().sort('_id', 1).to_list(None) == portfolios
    assert await db.audit_logs.find().sort('_id', 1).to_list(None) == audit
