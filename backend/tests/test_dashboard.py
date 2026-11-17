"""Exercise dashboard calculations and authorization against real MongoDB."""

from bson import ObjectId
from app.dashboard.service import DashboardService


async def login(http, email="admin@ketsip.local"):
    """Sign in as a seeded user."""
    response = await http.post("/api/auth/login", json={"email": email, "password": "Test-password-1234"})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["token"]}


async def inventory(db):
    """Insert two populated portfolios and one empty portfolio."""
    ids = [ObjectId(), ObjectId(), ObjectId()]
    await db.portfolios.insert_many([
        {"_id": ids[0], "name": "Alpha", "productArea": "Finance"},
        {"_id": ids[1], "name": "Beta", "productArea": "Technology"},
        {"_id": ids[2], "name": "Empty", "productArea": "Finance"},
    ])
    await db.applications.insert_many([
        {"name": "Alpha One", "portfolioId": str(ids[0]), "qualityScore": 80, "applicationHealthScore": 50, "automationCoverage": 60, "openCriticalDefects": 2, "riskLevel": "High"},
        {"name": "Alpha Two", "portfolioId": str(ids[0]), "qualityScore": 81, "applicationHealthScore": 51, "automationCoverage": 61, "openCriticalDefects": 3, "riskLevel": "Low"},
        {"name": "Beta One", "portfolioId": str(ids[1]), "qualityScore": 100, "applicationHealthScore": 100, "automationCoverage": 90, "openCriticalDefects": 4, "riskLevel": "High"},
    ])
    return ids


async def test_service_and_api_formulas_and_rounding(client):
    """Derive weighted averages, half-up rounding, sums and portfolio metrics."""
    http, db = client
    ids = await inventory(db)
    user = await db.users.find_one({"email": "admin@ketsip.local"})
    service = DashboardService(db)
    result = await service.executive(user)
    assert result["enterpriseQualityScore"] == 87
    assert result["applicationHealthScore"] == 67
    assert result["automationMaturityScore"] == 70
    assert (result["openCriticalDefects"], result["applicationsAtRisk"], result["totalApplications"], result["totalPortfolios"]) == (9, 2, 3, 3)
    assert result["portfolios"][0] == {"id": str(ids[0]), "name": "Alpha", "applicationCount": 2, "qualityScore": 81, "applicationsAtRisk": 1}
    assert result["portfolios"][2]["qualityScore"] is None
    response = await http.get("/api/dashboard/executive", headers=await login(http))
    assert response.status_code == 200 and response.json() == result


async def test_filters_and_empty_portfolio_rules(client):
    """Apply intersecting portfolio, product area, and risk filters."""
    http, db = client
    ids = await inventory(db)
    auth = await login(http)
    response = await http.get("/api/dashboard/executive", headers=auth, params={"productArea": "Finance"})
    assert response.json()["totalPortfolios"] == 2
    assert response.json()["enterpriseQualityScore"] == 81
    result = (await http.get("/api/dashboard/executive", headers=auth, params={"productArea": "Finance", "riskLevel": "High"})).json()
    assert (result["totalPortfolios"], result["totalApplications"], result["enterpriseQualityScore"], result["openCriticalDefects"]) == (1, 1, 80, 2)
    result = (await http.get("/api/dashboard/executive", headers=auth, params={"portfolioId": str(ids[2])})).json()
    assert result["totalPortfolios"] == 1 and result["totalApplications"] == 0
    assert result["enterpriseQualityScore"] is None and result["applicationHealthScore"] is None and result["automationMaturityScore"] is None
    result = (await http.get("/api/dashboard/executive", headers=auth, params={"portfolioId": str(ids[2]), "riskLevel": "Low"})).json()
    assert result["totalPortfolios"] == 0 and result["portfolios"] == []
    assert (await http.get("/api/dashboard/executive", headers=auth, params={"riskLevel": "Extreme"})).status_code == 422
    assert (await http.get("/api/dashboard/executive", headers=auth, params={"portfolioId": "invalid"})).status_code == 422


async def test_live_permissions_leader_scope_and_auth(client):
    """Reject missing sessions and apply live permissions and assigned scope."""
    http, db = client
    ids = await inventory(db)
    assert (await http.get("/api/dashboard/executive")).status_code == 401
    leader = await login(http, "leader@ketsip.local")
    assert (await http.get("/api/dashboard/executive", headers=leader)).json()["totalPortfolios"] == 0
    await db.users.update_one({"email": "leader@ketsip.local"}, {"$set": {"portfolioAccess": [str(ids[0]), str(ids[2])]}})
    result = (await http.get("/api/dashboard/executive", headers=leader)).json()
    assert (result["totalPortfolios"], result["totalApplications"]) == (2, 2)
    result = (await http.get("/api/dashboard/executive", headers=leader, params={"portfolioId": str(ids[1])})).json()
    assert result["totalPortfolios"] == 0 and result["enterpriseQualityScore"] is None
    await db.roles.update_one({"name": "Portfolio Leader"}, {"$set": {"permissions": []}})
    assert (await http.get("/api/dashboard/executive", headers=leader)).status_code == 403
    await db.users.update_one({"email": "leader@ketsip.local"}, {"$set": {"status": "Inactive"}})
    assert (await http.get("/api/dashboard/executive", headers=leader)).status_code == 401
