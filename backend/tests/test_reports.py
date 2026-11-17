"""Exercise report authorization, snapshots and demo seed on real MongoDB."""

import csv
import io
from datetime import datetime, timezone

import pytest
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from app.applications.schemas import ApplicationInput
from app.core.seed import seed_database
from app.core.config import Settings
from app.portfolios.schemas import PortfolioInput
from app.reports.service import ReportService


async def login(http, email="admin@ketsip.local"):
    """Authenticate a demo user."""
    response = await http.post('/api/auth/login', json={'email': email, 'password': 'Test-password-1234'})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['token']}


async def test_reports_json_metrics_pagination_and_csv(client):
    """Derive portfolio scores and export both reports with safe cells and audit."""
    http, db = client
    admin = await login(http)
    response = await http.post('/api/portfolios', headers=admin, json={'name': '=Payments', 'owner': '+owner'})
    assert response.status_code == 201
    p = response.json()
    response = await http.post('/api/portfolios', headers=admin, json={'name': 'Empty'})
    assert response.status_code == 201
    empty = response.json()
    for name, score in [('=Alpha', 80), ('Beta', 81)]:
        response = await http.post('/api/applications', headers=admin, json={'name': name, 'portfolioId': p['id'], 'qualityScore': score})
        assert response.status_code == 201
    result = await http.get('/api/reports/portfolios', headers=admin, params={'limit': 1})
    assert result.status_code == 200
    assert result.json()['total'] == 2
    row = result.json()['items'][0]
    assert row['applicationCount'] == 2 and row['qualityScore'] == 81
    response = await http.get('/api/reports/portfolios', headers=admin, params={'limit': 1, 'offset': 1})
    assert response.status_code == 200
    second = response.json()['items'][0]
    assert second['id'] == empty['id'] and second['qualityScore'] is None
    response = await http.get('/api/reports/applications', headers=admin, params={'limit': 1, 'offset': 1})
    assert response.status_code == 200
    apps = response.json()
    assert apps['total'] == 2 and apps['items'][0]['name'] == 'Beta'
    for kind in ('applications', 'portfolios'):
        response = await http.get(f'/api/reports/{kind}?format=csv', headers=admin)
        assert response.status_code == 200 and response.headers['content-type'].startswith('text/csv')
        rows = list(csv.DictReader(io.StringIO(response.text)))
        assert len(rows) == 2 and rows[0]['name'].startswith("'=")
        assert await db.audit_logs.count_documents({'entityType': 'report', 'action': 'export', 'details': f'Exported {kind} report'}) == 1
    assert (await http.get('/api/reports/applications?limit=101', headers=admin)).status_code == 422
    assert (await http.get('/api/reports/portfolios?format=pdf', headers=admin)).status_code == 422
    assert (await http.get('/api/reports/applications')).status_code == 401


async def test_scope_readonly_and_live_permissions(client):
    """Keep hidden portfolio data out of both representations and enforce hard limits."""
    http, db = client
    admin = await login(http)
    response = await http.post('/api/portfolios', headers=admin, json={'name': 'Visible'})
    assert response.status_code == 201
    one = response.json()['id']
    response = await http.post('/api/portfolios', headers=admin, json={'name': 'Secret'})
    assert response.status_code == 201
    two = response.json()['id']
    for name, pid in [('Visible app', one), ('Secret app', two)]:
        assert (await http.post('/api/applications', headers=admin, json={'name': name, 'portfolioId': pid})).status_code == 201
    leader = await login(http, 'leader@ketsip.local')
    for kind in ('applications', 'portfolios'):
        response = await http.get(f'/api/reports/{kind}', headers=leader)
        assert response.status_code == 200
        assert response.json()['total'] == 0
    await db.users.update_one({'email': 'leader@ketsip.local'}, {'$set': {'portfolioAccess': [one]}})
    for kind in ('applications', 'portfolios'):
        result = await http.get(f'/api/reports/{kind}', headers=leader)
        assert result.status_code == 200
        assert result.json()['total'] == 1 and 'Secret' not in result.text
        exported = await http.get(f'/api/reports/{kind}?format=csv', headers=leader)
        assert exported.status_code == 200 and 'Secret' not in exported.text and 'Visible' in exported.text
    readonly = await login(http, 'readonly@ketsip.local')
    await db.roles.update_one({'name': 'Read Only'}, {'$addToSet': {'permissions': 'export'}})
    for kind in ('applications', 'portfolios'):
        response = await http.get(f'/api/reports/{kind}', headers=readonly)
        assert response.status_code == 200
        assert response.json()['total'] == 2
        assert (await http.get(f'/api/reports/{kind}?format=csv', headers=readonly)).status_code == 403
    await db.roles.update_one({'name': 'Portfolio Leader'}, {'$set': {'permissions': ['view']}})
    assert (await http.get('/api/reports/portfolios?format=csv', headers=leader)).status_code == 403
    await db.roles.update_one({'name': 'Portfolio Leader'}, {'$set': {'permissions': []}})
    assert (await http.get('/api/reports/applications', headers=leader)).status_code == 403


async def test_export_bound_and_audit_failure(client):
    """Reject oversized exports and fail closed if audit cannot be committed."""
    http, db = client
    admin = await login(http)
    user = await db.users.find_one({'email': 'admin@ketsip.local'})
    service = ReportService(db)
    await db.portfolios.insert_many([{'name': f'Bound {i}'} for i in range(10001)])
    response = await http.get('/api/reports/portfolios?format=csv', headers=admin)
    assert response.status_code == 413
    assert await db.audit_logs.count_documents({'entityType': 'report'}) == 0
    await db.portfolios.delete_many({'name': {'$regex': '^Bound '}})
    await db.applications.insert_many([{'name': f'Bound application {i}', 'portfolioId': str(ObjectId())} for i in range(10001)])
    response = await http.get('/api/reports/applications?format=csv', headers=admin)
    assert response.status_code == 413
    assert await db.audit_logs.count_documents({'entityType': 'report'}) == 0
    await db.applications.delete_many({'name': {'$regex': '^Bound application '}})
    await db.audit_logs.create_index('entityType', unique=True, partialFilterExpression={'entityType': 'report'})
    assert await service.export(user, 'portfolios')
    with pytest.raises(DuplicateKeyError):
        await service.export(user, 'portfolios')
    assert await db.audit_logs.count_documents({'entityType': 'report'}) == 1


async def test_actual_seed_counts_validity_and_idempotence(client):
    """Run the actual seeder twice, preserving renames, edits and leader scope."""
    http, db = client
    settings = Settings(jwt_secret='test-secret-unique-value-not-for-production-123456789', bootstrap_password='Test-password-1234')
    await seed_database(db, settings)
    assert await db.portfolios.count_documents({}) == 3
    assert await db.applications.count_documents({}) == 10
    portfolios = await db.portfolios.find({}).to_list(None)
    assert {p['name'] for p in portfolios} == {'Payments', 'Customer Platform', 'Data & Analytics'}
    for p in portfolios:
        PortfolioInput.model_validate({k: p[k] for k in ('name', 'owner', 'description', 'productArea', 'status')})
    applications = await db.applications.find({}).to_list(None)
    for app in applications:
        ApplicationInput.model_validate({k: v for k, v in app.items() if k in ApplicationInput.model_fields})
        assert app['portfolioId'] in {str(p['_id']) for p in portfolios}
    await db.portfolios.update_one({'_id': portfolios[0]['_id']}, {'$set': {'name': 'Edited portfolio'}})
    await db.applications.update_one({'_id': applications[0]['_id']}, {'$set': {'name': 'Edited application', 'qualityScore': 42}})
    await seed_database(db, settings)
    assert await db.portfolios.count_documents({}) == 3
    assert await db.applications.count_documents({}) == 10
    assert (await db.applications.find_one({'_id': applications[0]['_id']}))['qualityScore'] == 42
    assert (await db.portfolios.find_one({'_id': portfolios[0]['_id']}))['name'] == 'Edited portfolio'
    assert (await db.users.find_one({'email': 'leader@ketsip.local'}))['portfolioAccess'] == []
    leader = await login(http, 'leader@ketsip.local')
    response = await http.get('/api/reports/portfolios', headers=leader)
    assert response.status_code == 200
    assert response.json()['total'] == 0
