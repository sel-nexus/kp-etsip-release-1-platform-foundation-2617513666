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
