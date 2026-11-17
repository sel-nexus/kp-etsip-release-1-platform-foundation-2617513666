"""Create local demonstration roles and accounts without replacing existing data."""

from datetime import datetime, timezone
from starlette.concurrency import run_in_threadpool
from pymongo.asynchronous.database import AsyncDatabase
from app.core.config import Settings
from app.core.security import hash_password

ROLES = {
    "Administrator": ["view", "create", "edit", "delete", "export", "administer"],
    "Executive": ["view", "export"],
    "Portfolio Leader": ["view", "create", "edit", "export"],
    "Engineer": ["view", "create", "edit", "export"],
    "Auditor": ["view", "export"],
    "Read Only": ["view"],
}
DEMO_USERS = {
    "Administrator": "admin@ketsip.local", "Executive": "executive@ketsip.local",
    "Portfolio Leader": "leader@ketsip.local", "Engineer": "engineer@ketsip.local",
    "Auditor": "auditor@ketsip.local", "Read Only": "readonly@ketsip.local",
}


async def seed_database(db: AsyncDatabase, settings: Settings) -> None:
    """Upsert roles and demo users, retaining any existing changes."""
    if len(settings.bootstrap_password) < 12 or len(settings.bootstrap_password.encode("utf-8")) > 72:
        raise ValueError("BOOTSTRAP_PASSWORD must contain at least 12 characters and at most 72 bytes")
    now = datetime.now(timezone.utc)
    password_hash = await run_in_threadpool(hash_password, settings.bootstrap_password)
    for role, permissions in ROLES.items():
        await db.roles.update_one({"name": role}, {"$setOnInsert": {"name": role, "description": role,
            "permissions": permissions, "createdAt": now, "updatedAt": now}}, upsert=True)
        email = DEMO_USERS[role]
        await db.users.update_one({"email": email}, {"$setOnInsert": {"email": email, "name": f"Demo {role}",
            "passwordHash": password_hash, "role": role, "portfolioAccess": [], "status": "Active",
            "lastLogin": None, "authSource": "local", "managerName": None, "vendorIndicator": False,
            "defaultLandingPage": "dashboard" if role in ("Administrator", "Executive") else "applications",
            "tokenVersion": 0, "createdAt": now, "updatedAt": now}}, upsert=True)
    await seed_inventory(db, now)


async def seed_inventory(db: AsyncDatabase, now: datetime) -> None:
    """Insert representative inventory without replacing existing records or edits."""
    from app.applications.schemas import ApplicationInput
    from app.portfolios.schemas import PortfolioInput

    portfolios = [
        ("Payments", "Payment services", "Payments"),
        ("Customer Platform", "Customer experience services", "Customer"),
        ("Data & Analytics", "Enterprise data products", "Data"),
    ]
    ids = []
    for name, description, area in portfolios:
        key = f"demo-portfolio:{name}"
        existing = await db.portfolios.find_one({"$or": [{"seedKey": key}, {"name": name}]})
        if not existing:
            values = PortfolioInput(name=name, owner="Platform team", description=description, productArea=area).model_dump()
            await db.portfolios.update_one({"name": name}, {"$setOnInsert": {**values, "seedKey": key, "createdAt": now, "updatedAt": now}}, upsert=True)
            existing = await db.portfolios.find_one({"name": name})
        ids.append(str(existing["_id"]))

    applications = [
        ("Payment Gateway", 0, 92, 88, 2, 0, "Low"), ("Settlement Engine", 0, 81, 76, 7, 1, "Medium"),
        ("Fraud Monitor", 0, 69, 65, 12, 3, "High"), ("Billing Service", 0, 86, 80, 5, 0, "Low"),
        ("Customer Portal", 1, 90, 85, 3, 0, "Low"), ("Identity Service", 1, 78, 72, 8, 1, "Medium"),
        ("Case Management", 1, 73, 68, 11, 2, "High"), ("Analytics Warehouse", 2, 84, 77, 6, 0, "Medium"),
        ("Reporting Pipeline", 2, 88, 83, 4, 0, "Low"), ("Data Catalog", 2, 76, 71, 9, 1, "Medium"),
    ]
    for name, index, quality, coverage, defects, critical, risk in applications:
        key = f"demo-application:{name}"
        existing = await db.applications.find_one({"$or": [{"seedKey": key}, {"name": name}]})
        if existing:
            continue
        values = ApplicationInput(name=name, portfolioId=ids[index], description=f"Demonstration {name.lower()} application",
            productArea=portfolios[index][2], businessOwner="Business team", technologyOwner="Engineering team",
            etsOwner="Quality team", criticality="High", tier=2, technologyStack="Cloud services",
            applicationHealthScore=quality, qualityScore=quality, automationCoverage=coverage,
            unitTestCoverage=min(100, coverage + 5), openDefects=defects, openCriticalDefects=critical,
            riskLevel=risk).model_dump(mode="json")
        await db.applications.update_one({"name": name}, {"$setOnInsert": {**values, "seedKey": key, "createdAt": now, "updatedAt": now}}, upsert=True)
