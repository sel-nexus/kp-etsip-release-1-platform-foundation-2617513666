"""Persist application inventory and audit events in MongoDB."""

from datetime import datetime, timezone
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase


class ApplicationRepository:
    """Keep reference guards, inventory changes and audits atomic."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Bind the pooled database."""
        self.db = db

    async def page(self, query: dict, limit: int, offset: int, session=None) -> dict:
        """Return a sorted page, including portfolio names."""
        total = await self.db.applications.count_documents(query, session=session)
        cursor = self.db.applications.find(query, session=session).sort([("name", 1), ("_id", 1)]).skip(offset).limit(limit)
        items = await cursor.to_list(None)
        ids = [ObjectId(x["portfolioId"]) for x in items if ObjectId.is_valid(x.get("portfolioId", ""))]
        portfolios = await self.db.portfolios.find({"_id": {"$in": ids}}, {"name": 1}, session=session).to_list(None)
        names = {str(p["_id"]): p["name"] for p in portfolios}
        for item in items:
            item["portfolioName"] = names.get(item["portfolioId"], "")
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def audit(self, user: dict, action: str, identity: str | None, session) -> None:
        """Write a history entry in the caller's transaction."""
        now = datetime.now(timezone.utc)
        await self.db.audit_logs.insert_one({"timestamp": now, "createdAt": now, "updatedAt": now,
            "userId": user["_id"], "userName": user["name"], "action": action,
            "entityType": "application", "entityId": identity, "details": f"Application {action}"}, session=session)

    async def mutate(self, user: dict, action: str, identity: ObjectId, scope: dict, values: dict | None = None) -> dict | None:
        """Mutate and audit together; target portfolio updates serialize against deletion."""
        async def transaction(session):
            now = datetime.now(timezone.utc)
            if action != "create":
                current = await self.db.applications.find_one({"_id": identity, **scope}, session=session)
                if current is None:
                    return None
            if action in ("create", "edit"):
                guard = await self.db.portfolios.update_one({"_id": ObjectId(values["portfolioId"])}, {"$inc": {"applicationRevision": 1}}, session=session)
                if not guard.matched_count:
                    return {"missingPortfolio": True}
            if action == "create":
                result = {"_id": identity, **values, "createdAt": now, "updatedAt": now}
                await self.db.applications.insert_one(result, session=session)
            elif action == "edit":
                updated = await self.db.applications.find_one_and_update({"_id": identity, **scope}, {"$set": {**values, "updatedAt": now}}, return_document=True, session=session)
                if updated is None:
                    return None
                result = updated
            else:
                deleted = await self.db.applications.delete_one({"_id": identity, **scope}, session=session)
                if not deleted.deleted_count:
                    return None
                result = current
            await self.audit(user, action, str(identity), session)
            return result
        async with self.db.client.start_session() as session:
            return await session.with_transaction(transaction)

    async def export(self, user: dict, query: dict) -> list[dict] | None:
        """Read a bounded snapshot and audit only a successful export."""
        async def transaction(session):
            page = await self.page(query, 10001, 0, session)
            if page["total"] > 10000:
                return None
            await self.audit(user, "export", None, session)
            return page["items"]
        async with self.db.client.start_session() as session:
            return await session.with_transaction(transaction)
