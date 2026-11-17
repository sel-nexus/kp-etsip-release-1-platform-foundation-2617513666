"""Exercise administrative policies against a real MongoDB replica set."""

import asyncio
import csv
import io
from datetime import datetime, timezone
from bson import ObjectId
import pytest
from fastapi import HTTPException
from pymongo import AsyncMongoClient
from pymongo.errors import DuplicateKeyError
from app.admin.repository import AdminRepository
from app.admin.schemas import UserInput
from app.admin.service import AdminService


async def login(http, email='admin@ketsip.local', password='Test-password-1234'):
    """Authenticate and return a bearer header."""
    response = await http.post('/api/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 200, response.text
    return {'Authorization': 'Bearer ' + response.json()['token']}


def account(**overrides):
    """Construct a valid local account request."""
    return {'name': 'New Leader', 'email': 'new@example.com', 'role': 'Portfolio Leader', 'status': 'Active', 'portfolioAccess': [], 'password': 'New-password-1234', **overrides}


async def test_auth_boundaries_and_live_admin_permission(client):
    """Require an active administrator and current administer permission everywhere."""
    http, db = client
    admin = await login(http)
    auditor = await login(http, 'auditor@ketsip.local')
    for path in ('/api/users', '/api/roles', '/api/audit-logs', '/api/audit-logs?format=csv'):
        assert (await http.get(path)).status_code == 401
        assert (await http.get(path, headers=auditor)).status_code == 403
    assert (await http.post('/api/users', headers=auditor, json=account())).status_code == 403
    await db.roles.update_one({'name': 'Administrator'}, {'$set': {'permissions': ['view']}})
    assert (await http.get('/api/users', headers=admin)).status_code == 403
    assert (await http.get('/api/audit-logs?format=csv', headers=admin)).status_code == 403


async def test_validation_duplicate_and_last_admin(client):
    """Reject invalid credentials, duplicate emails and loss of the last active admin."""
    http, db = client
    admin = await login(http)
    for payload in (account(email='bad'), account(password='short'), account(role='Unknown'), account(portfolioAccess=['bad'])):
        response = await http.post('/api/users', headers=admin, json=payload)
        assert response.status_code == 422
        assert 'New-password-1234' not in response.text and '"input"' not in response.text
    assert (await http.post('/api/users', headers=admin, json=account(email='ADMIN@KETSIP.LOCAL'))).status_code == 409
    user = await db.users.find_one({'email': 'admin@ketsip.local'})
    uid = str(user['_id'])
    assert (await http.delete('/api/users/' + uid, headers=admin)).status_code == 409
    assert (await http.put('/api/users/' + uid, headers=admin, json=account(name='Admin', email=user['email'], role='Administrator', status='Inactive'))).status_code == 409
    assert (await http.get('/api/users?limit=101', headers=admin)).status_code == 422


async def test_user_mutations_scope_sessions_and_history(client):
    """Persist assignments, enforce scope and retain audit history after hard deletion."""
    http, db = client
    admin = await login(http)
    portfolio = (await http.post('/api/portfolios', headers=admin, json={'name': 'Scoped'})).json()['id']
    other = (await http.post('/api/portfolios', headers=admin, json={'name': 'Outside'})).json()['id']
    payload = account(portfolioAccess=[portfolio])
    response = await http.post('/api/users', headers=admin, json=payload)
    assert response.status_code == 201, response.text
    data = response.json(); uid = data['id']
    assert 'password' not in response.text.lower() and data['portfolioAccess'] == [portfolio]
    stored = await db.users.find_one({'_id': ObjectId(uid)})
    assert stored['passwordHash'] != payload['password']
    leader = await login(http, payload['email'], payload['password'])
    assert (await http.get('/api/portfolios', headers=leader)).json()['total'] == 1
    assert (await http.get('/api/portfolios/' + other, headers=leader)).status_code == 404
    changed = {**payload, 'name': 'Changed', 'status': 'Inactive'}
    assert (await http.put('/api/users/' + uid, headers=admin, json=changed)).status_code == 200
    assert (await http.get('/api/auth/me', headers=leader)).status_code == 401
    changed['status'] = 'Active'
    assert (await http.put('/api/users/' + uid, headers=admin, json=changed)).status_code == 200
    leader = await login(http, payload['email'], payload['password'])
    assert (await http.delete('/api/users/' + uid, headers=admin)).status_code == 204
    assert await db.users.find_one({'_id': ObjectId(uid)}) is None
    assert (await http.get('/api/auth/me', headers=leader)).status_code == 401
    assert await db.audit_logs.count_documents({'entityType': 'user', 'entityId': uid}) >= 4
    logs = (await http.get('/api/audit-logs', headers=admin, params={'userId': uid, 'action': 'login'})).json()
    assert logs['total'] >= 1 and logs['items'][0]['userName'] == 'Changed'


async def test_role_edits_hard_restrictions_and_audit_export(client):
    """Role permission grants cannot elevate hard restrictions; CSV neutralizes formulas."""
    http, db = client
    admin = await login(http)
    roles = (await http.get('/api/roles', headers=admin)).json()['items']
    reader = next(role for role in roles if role['name'] == 'Read Only')
    result = await http.put('/api/roles/' + reader['id'], headers=admin, json={'name': 'Read Only', 'description': 'Test', 'permissions': ['view', 'delete', 'administer']})
    assert result.status_code == 200, result.text
    assert await db.audit_logs.count_documents({'entityType': 'role', 'entityId': reader['id'], 'action': 'edit'}) == 1
    readonly = await login(http, 'readonly@ketsip.local')
    assert (await http.get('/api/users', headers=readonly)).status_code == 403
    assert (await http.delete('/api/portfolios/' + str(ObjectId()), headers=readonly)).status_code == 403
    assert (await http.post('/api/roles', headers=admin, json={'name': 'Custom', 'description': '', 'permissions': []})).status_code == 422
    assert (await http.post('/api/roles', headers=admin, json={'name': 'Read Only', 'description': '', 'permissions': []})).status_code == 409
    await db.roles.delete_one({'name': 'Executive'})
    recreated = await http.post('/api/roles', headers=admin, json={'name': 'Executive', 'description': 'Restored', 'permissions': ['view']})
    assert recreated.status_code == 201
    assert await db.audit_logs.count_documents({'entityType': 'role', 'entityId': recreated.json()['id'], 'action': 'create'}) == 1
    now = datetime.now(timezone.utc)
    await db.audit_logs.insert_one({'timestamp': now, 'userId': None, 'userName': '=malicious', 'action': 'test', 'entityType': 'test', 'entityId': None, 'details': ' +formula'})
    response = await http.get('/api/audit-logs', headers=admin, params={'action': 'test', 'startDate': now.date().isoformat(), 'endDate': now.date().isoformat(), 'format': 'csv'})
    assert response.status_code == 200 and "'=malicious" in response.text and "' +formula" in response.text
    assert (await http.get('/api/audit-logs', headers=admin, params={'startDate': '2025-02-02', 'endDate': '2025-01-01'})).status_code == 422


async def test_direct_service_and_audit_transaction_rollback(client):
    """Prove audit failure rolls back the associated account mutation."""
    _, db = client
    actor = await db.users.find_one({'email': 'admin@ketsip.local'})
    svc = AdminService(AdminRepository(db))
    created = await svc.save_user(actor, UserInput(**account()))
    identity = str(created['_id'])
    # Force an audit collision between the existing create and subsequent edit.
    await db.audit_logs.create_index('entityId', unique=True, partialFilterExpression={'entityType': 'user', 'action': {'$in': ['create', 'edit']}})
    with pytest.raises(DuplicateKeyError):
        await svc.repo.mutate_user(actor, ObjectId(identity), UserInput(**account(name='Should roll back')).model_dump(exclude={'password'}))
    assert (await db.users.find_one({'_id': ObjectId(identity)}))['name'] == 'New Leader'
    with pytest.raises(HTTPException) as error:
        await svc.delete_user(actor, str(ObjectId()))
    assert error.value.status_code == 404


async def test_specific_audit_events_and_history(client, mongo_uri):
    """Record actual role and permission changes, without leaking credentials."""
    http, db = client
    admin = await login(http)
    actor = await db.users.find_one({'email': 'admin@ketsip.local'})
    created = await http.post('/api/users', headers=admin, json=account())
    assert created.status_code == 201
    uid = created.json()['id']
    assert await db.audit_logs.count_documents({'entityId': uid, 'action': 'roleChange'}) == 0
    changed = account(role='Engineer', password='Changed-password-1234')
    assert (await http.put('/api/users/' + uid, headers=admin, json=changed)).status_code == 200
    assert (await http.put('/api/users/' + uid, headers=admin, json=changed)).status_code == 200
    events = await db.audit_logs.find({'entityId': uid, 'action': 'roleChange'}).to_list(None)
    assert len(events) == 1 and events[0]['userId'] == actor['_id']
    assert 'password' not in str(events).lower() and 'Changed-password-1234' not in str(events)
    roles = (await http.get('/api/roles', headers=admin)).json()['items']
    role = next(item for item in roles if item['name'] == 'Read Only')
    payload = {'name': role['name'], 'description': 'changed', 'permissions': ['view', 'export']}
    assert (await http.put('/api/roles/' + role['id'], headers=admin, json=payload)).status_code == 200
    payload['permissions'].reverse()
    assert (await http.put('/api/roles/' + role['id'], headers=admin, json=payload)).status_code == 200
    assert await db.audit_logs.count_documents({'entityId': role['id'], 'action': 'permissionChange', 'userId': actor['_id']}) == 1
    assert (await http.delete('/api/users/' + uid, headers=admin)).status_code == 204
    history = await http.get('/api/audit-logs', headers=admin, params={'action': 'roleChange'})
    assert history.status_code == 200 and any(item['entityId'] == uid for item in history.json()['items'])
    fresh_client = AsyncMongoClient(mongo_uri)
    try:
        persisted = await fresh_client[db.name].audit_logs.find_one({'action': 'roleChange', 'entityId': uid})
        assert persisted is not None and persisted['userId'] == actor['_id']
    finally:
        await fresh_client.close()


async def test_administrator_permission_cannot_be_removed(client):
    """Prevent an administrative lockout without writing an audit event."""
    http, db = client
    admin = await login(http)
    role = await db.roles.find_one({'name': 'Administrator'})
    before = await db.audit_logs.count_documents({'entityId': str(role['_id'])})
    response = await http.put('/api/roles/' + str(role['_id']), headers=admin,
                              json={'name': 'Administrator', 'description': '', 'permissions': ['view']})
    assert response.status_code in (409, 422)
    assert 'administer' in (await db.roles.find_one({'_id': role['_id']}))['permissions']
    assert await db.audit_logs.count_documents({'entityId': str(role['_id'])}) == before
    assert (await http.get('/api/users', headers=admin)).status_code == 200


async def test_audit_export_filter_snapshot_and_event(client):
    """Filter by inclusive UTC dates and log exports outside their own snapshot."""
    http, db = client
    admin = await login(http)
    actor = await db.users.find_one({'email': 'admin@ketsip.local'})
    docs = []
    for day, value in [(1, 'before'), (2, '=formula'), (3, 'after')]:
        docs.append({'timestamp': datetime(2024, 2, day, 12, tzinfo=timezone.utc), 'userId': actor['_id'],
                     'userName': value, 'action': 'filter-test', 'entityType': 'test', 'entityId': None,
                     'details': '\t=bad'})
    await db.audit_logs.insert_many(docs)
    params = {'from': '2024-02-02', 'to': '2024-02-02', 'action': 'filter-test'}
    page = await http.get('/api/audit-logs', headers=admin, params=params)
    assert page.status_code == 200 and page.json()['total'] == 1
    assert page.json()['items'][0]['userName'] == '=formula'
    response = await http.get('/api/audit-logs', headers=admin, params={**params, 'format': 'csv'})
    assert response.status_code == 200
    rows = list(csv.DictReader(io.StringIO(response.text)))
    assert len(rows) == 1 and rows[0]['userName'] == "'=formula" and rows[0]['details'] == "'\t=bad"
    event = await db.audit_logs.find_one({'action': 'export', 'userId': actor['_id']})
    assert event and event['entityType'] == 'audit' and 'password' not in str(event).lower()
    all_export = await http.get('/api/audit-logs', headers=admin, params={'action': 'export', 'format': 'csv'})
    assert len(list(csv.DictReader(io.StringIO(all_export.text)))) == 1
    assert await db.audit_logs.count_documents({'action': 'export'}) == 2
    assert (await http.get('/api/audit-logs', headers=admin, params={'from': '2024-02-03', 'to': '2024-02-02'})).status_code == 422
    assert (await http.get('/api/audit-logs', headers=admin, params={'from': '2024-02-02', 'startDate': '2024-02-01'})).status_code == 422


async def test_export_limit_and_audit_failure_are_atomic(client):
    """Reject oversized exports and do not return data if the audit insert fails."""
    http, db = client
    admin = await login(http)
    actor = await db.users.find_one({'email': 'admin@ketsip.local'})
    now = datetime.now(timezone.utc)
    await db.audit_logs.insert_many([{'timestamp': now, 'userId': actor['_id'], 'userName': 'Admin',
                                      'action': 'bulk', 'entityType': 'test', 'entityId': None, 'details': ''}
                                     for _ in range(10001)])
    response = await http.get('/api/audit-logs', headers=admin, params={'action': 'bulk', 'format': 'csv'})
    assert response.status_code == 413
    assert await db.audit_logs.count_documents({'action': 'export'}) == 0
    await db.audit_logs.delete_one({'action': 'bulk'})
    response = await http.get('/api/audit-logs', headers=admin, params={'action': 'bulk', 'format': 'csv'})
    assert response.status_code == 200 and len(list(csv.DictReader(io.StringIO(response.text)))) == 10000
    await db.audit_logs.create_index('action', unique=True, partialFilterExpression={'action': 'export'})
    with pytest.raises(DuplicateKeyError):
        await AdminService(AdminRepository(db)).csv(actor, {'action': 'bulk'})
    assert await db.audit_logs.count_documents({'action': 'export'}) == 1


async def test_specific_audit_failure_rolls_back_mutations(client):
    """A failed specialized event aborts both the change and generic edit event."""
    _, db = client
    actor = await db.users.find_one({'email': 'admin@ketsip.local'})
    svc = AdminService(AdminRepository(db))
    user = await svc.save_user(actor, UserInput(**account()))
    uid = str(user['_id'])
    await db.audit_logs.insert_one({'action': 'roleChange'})
    await db.audit_logs.create_index('action', unique=True, partialFilterExpression={'action': 'roleChange'})
    with pytest.raises(DuplicateKeyError):
        await svc.save_user(actor, UserInput(**account(role='Engineer')), uid)
    assert (await db.users.find_one({'_id': user['_id']}))['role'] == 'Portfolio Leader'
    assert await db.audit_logs.count_documents({'entityId': uid, 'action': 'edit'}) == 0
    role = await db.roles.find_one({'name': 'Read Only'})
    await db.audit_logs.insert_one({'action': 'permissionChange'})
    await db.audit_logs.create_index('action', name='permission_change_unique', unique=True, partialFilterExpression={'action': 'permissionChange'})
    from app.admin.schemas import RoleInput
    with pytest.raises(DuplicateKeyError):
        await svc.repo.mutate_role(actor, role['_id'], RoleInput(name='Read Only', permissions=['export']).model_dump(), False)
    assert (await db.roles.find_one({'_id': role['_id']}))['permissions'] == role['permissions']
    assert await db.audit_logs.count_documents({'entityId': str(role['_id']), 'action': 'edit'}) == 0


async def test_concurrent_administrator_demotions_keep_one_active(client):
    """Concurrent requests retry conflicts and cannot remove both administrators."""
    http, db = client
    admin = await login(http)
    second = await http.post('/api/users', headers=admin, json=account(email='second@example.com', role='Administrator'))
    assert second.status_code == 201
    first = await db.users.find_one({'email': 'admin@ketsip.local'})
    first_payload = UserInput(**account(name=first['name'], email=first['email'], role='Engineer', password=None))
    second_payload = UserInput(**account(email='second@example.com', role='Engineer', password=None))
    service = AdminService(AdminRepository(db))
    results = await asyncio.gather(service.save_user(first, first_payload, str(first['_id'])),
                                   service.save_user(first, second_payload, second.json()['id']), return_exceptions=True)
    assert sum(isinstance(result, dict) for result in results) == 1
    errors = [result for result in results if isinstance(result, HTTPException)]
    assert len(errors) == 1 and errors[0].status_code == 409
    assert await db.users.count_documents({'role': 'Administrator', 'status': 'Active'}) == 1


async def test_user_transaction_retries_real_write_conflict(client):
    """A concurrent MongoDB lock conflict is retried after its owner commits."""
    _, db = client
    actor = await db.users.find_one({'email': 'admin@ketsip.local'})
    service = AdminService(AdminRepository(db))
    user = await service.save_user(actor, UserInput(**account()))
    async with db.client.start_session() as session:
        await session.start_transaction()
        await db.admin_locks.update_one({'_id': 'users'}, {'$inc': {'revision': 1}}, session=session)
        task = asyncio.create_task(service.save_user(actor, UserInput(**account(name='Retried')), str(user['_id'])))
        await asyncio.sleep(0.1)
        assert not task.done()
        await session.commit_transaction()
        result = await asyncio.wait_for(task, 10)
    assert result['name'] == 'Retried'
    assert await db.audit_logs.count_documents({'entityId': str(user['_id']), 'action': 'edit'}) == 1
