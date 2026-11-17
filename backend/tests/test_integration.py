"""Exercise cross-feature inventory, insight, audit and permission flows."""

from bson import ObjectId


async def authenticate(http, email):
    """Return the bearer header for a seeded account."""
    response = await http.post('/api/auth/login', json={'email': email, 'password': 'Test-password-1234'})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.json()['token']}


async def test_inventory_changes_flow_to_dashboard_reports_audit_and_scope(client):
    """Carry changes across inventory, insight, reporting and access boundaries."""
    http, db = client
    admin = await authenticate(http, 'admin@ketsip.local')
    leader = await authenticate(http, 'leader@ketsip.local')
    first = await http.post('/api/portfolios', headers=admin, json={'name': 'Integration one', 'productArea': 'Finance'})
    second = await http.post('/api/portfolios', headers=admin, json={'name': 'Integration two', 'productArea': 'Other'})
    assert first.status_code == second.status_code == 201
    first_id, second_id = first.json()['id'], second.json()['id']
    await db.users.update_one({'email': 'leader@ketsip.local'}, {'$set': {'portfolioAccess': [first_id]}})
    payload = {'name': 'Integration app', 'portfolioId': first_id, 'qualityScore': 80,
               'applicationHealthScore': 70, 'automationCoverage': 60, 'openCriticalDefects': 2, 'riskLevel': 'High'}
    created = await http.post('/api/applications', headers=admin, json=payload)
    assert created.status_code == 201
    app_id = created.json()['id']
    dashboard = await http.get('/api/dashboard/executive', headers=leader)
    assert dashboard.status_code == 200
    assert dashboard.json()['enterpriseQualityScore'] == 80
    assert dashboard.json()['totalApplications'] == 1 and dashboard.json()['applicationsAtRisk'] == 1
    report = await http.get('/api/reports/applications', headers=leader)
    assert report.status_code == 200 and [row['id'] for row in report.json()['items']] == [app_id]
    updated = await http.put(f'/api/applications/{app_id}', headers=admin, json={**payload, 'qualityScore': 95, 'riskLevel': 'Low'})
    assert updated.status_code == 200
    dashboard = await http.get('/api/dashboard/executive', headers=leader)
    assert dashboard.status_code == 200 and dashboard.json()['enterpriseQualityScore'] == 95
    assert dashboard.json()['applicationsAtRisk'] == 0
    exported = await http.get('/api/reports/applications?format=csv', headers=leader)
    assert exported.status_code == 200 and 'Integration app' in exported.text
    events = await http.get('/api/audit-logs', headers=admin, params={'action': 'export'})
    assert events.status_code == 200 and any(row['entityType'] == 'report' for row in events.json()['items'])
    moved = await http.put(f'/api/applications/{app_id}', headers=admin, json={**payload, 'portfolioId': second_id})
    assert moved.status_code == 200
    assert (await http.get(f'/api/applications/{app_id}', headers=leader)).status_code == 404
    report = await http.get('/api/reports/applications', headers=leader)
    assert report.status_code == 200
    assert report.json()['total'] == 0
    dashboard = await http.get('/api/dashboard/executive', headers=leader)
    assert dashboard.status_code == 200
    assert dashboard.json()['totalApplications'] == 0
    assert (await db.applications.find_one({'_id': ObjectId(app_id)}))['portfolioId'] == second_id
    deleted = await http.delete(f'/api/portfolios/{second_id}', headers=admin)
    assert deleted.status_code == 204
    assert await db.applications.find_one({'_id': ObjectId(app_id)}) is None


async def test_failed_inventory_reference_does_not_leak_into_downstream_views(client):
    """Reject an invalid reference without creating inventory or misleading insights."""
    http, db = client
    admin = await authenticate(http, 'admin@ketsip.local')
    portfolio = await http.post('/api/portfolios', headers=admin, json={'name': 'Available'})
    assert portfolio.status_code == 201
    missing = str(ObjectId())
    failed = await http.post('/api/applications', headers=admin,
                             json={'name': 'Must not exist', 'portfolioId': missing, 'qualityScore': 90})
    assert failed.status_code == 404
    report = await http.get('/api/reports/applications', headers=admin)
    assert report.status_code == 200 and report.json()['total'] == 0
    dashboard = await http.get('/api/dashboard/executive', headers=admin)
    assert dashboard.status_code == 200 and dashboard.json()['totalApplications'] == 0
    assert await db.applications.count_documents({'name': 'Must not exist'}) == 0
    assert await db.audit_logs.count_documents({'entityType': 'application', 'action': 'create'}) == 0
