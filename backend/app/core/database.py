"""Supply the lifespan-owned Mongo database to request handlers."""

from fastapi import Request
from pymongo.asynchronous.database import AsyncDatabase


def get_database(request: Request) -> AsyncDatabase:
    """Return the database owned by the application lifespan."""
    return request.app.state.db


async def create_indexes(db: AsyncDatabase) -> None:
    """Enforce natural keys and support identity audit lookup."""
    await db.users.create_index("email", unique=True)
    await db.roles.create_index("name", unique=True)
    await db.audit_logs.create_index("timestamp")
    await db.audit_logs.create_index([("userId", 1), ("timestamp", -1)])
    await db.audit_logs.create_index([("action", 1), ("timestamp", -1)])
    await db.revoked_tokens.create_index("expiresAt", expireAfterSeconds=0)
    await db.portfolios.create_index("name", unique=True)
    await db.portfolios.create_index([("status", 1), ("productArea", 1)])
    await db.applications.create_index("portfolioId")
    await db.applications.create_index("name", unique=True)
    await db.applications.create_index([("criticality", 1), ("riskLevel", 1), ("lifecycleStatus", 1)])
