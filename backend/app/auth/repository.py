"""Persist identity records and audit events in MongoDB."""

from datetime import datetime, timezone
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase


class AuthRepository:
    """Keep identity data access and transactional audit writes together."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Bind the request to the pooled database."""
        self.db = db

    async def by_email(self, email: str) -> dict | None:
        """Look up a normalized email address."""
        return await self.db.users.find_one({"email": email.strip().lower()})

    async def by_id(self, identity: str) -> dict | None:
        """Look up a valid account identifier."""
        if not ObjectId.is_valid(identity):
            return None
        return await self.db.users.find_one({"_id": ObjectId(identity)})

    async def public_user(self, user: dict) -> dict:
        """Attach live role permissions to the account response."""
        role = await self.db.roles.find_one({"name": user["role"]})
        return {**user, "permissions": role.get("permissions", []) if role else []}

    async def audit(self, user: dict | None, action: str, detail: str, session=None) -> None:
        """Write denormalized history without saving submitted credentials."""
        now = datetime.now(timezone.utc)
        await self.db.audit_logs.insert_one({"timestamp": now, "createdAt": now, "updatedAt": now,
            "userId": user["_id"] if user else None, "userName": user["name"] if user else "Unknown user",
            "action": action, "entityType": "user", "entityId": str(user["_id"]) if user else None,
            "details": detail}, session=session)

    async def update_and_audit(self, user: dict, changes: dict, detail: str, match: dict | None = None) -> bool:
        """Atomically persist an account change and its audit event."""
        query = {"_id": user["_id"], "status": "Active", **(match or {})}
        async with self.db.client.start_session() as session:
            async with await session.start_transaction():
                result = await self.db.users.update_one(query, {"$set": {**changes, "updatedAt": datetime.now(timezone.utc)}}, session=session)
                if not result.matched_count:
                    return False
                await self.audit(user, "edit", detail, session)
        return True

    async def login_success(self, user: dict) -> bool:
        """Atomically record a successful sign-in and its timestamp."""
        now = datetime.now(timezone.utc)
        async with self.db.client.start_session() as session:
            async with await session.start_transaction():
                result = await self.db.users.update_one({"_id": user["_id"], "status": "Active", "passwordHash": user["passwordHash"]},
                    {"$set": {"lastLogin": now, "updatedAt": now}}, session=session)
                if not result.matched_count:
                    return False
                await self.audit(user, "login", "Login succeeded", session)
        return True

    async def revoked(self, token_id: str) -> bool:
        """Check persistent token revocation."""
        return await self.db.revoked_tokens.find_one({"_id": token_id}) is not None

    async def revoke(self, token_id: str, expires: datetime) -> None:
        """Revoke a token until its expiration."""
        await self.db.revoked_tokens.update_one({"_id": token_id}, {"$setOnInsert": {"expiresAt": expires}}, upsert=True)
