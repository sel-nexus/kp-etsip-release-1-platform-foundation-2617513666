"""Read and atomically maintain MongoDB portfolio records."""

from datetime import datetime, timezone
from bson import ObjectId
from pymongo.asynchronous.database import AsyncDatabase


class PortfolioRepository:
    """Implement scoped queries, aggregations and audited mutations."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Bind the pooled database."""
        self.db = db

    async def page(self, query: dict, limit: int, offset: int) -> dict:
        """Derive metrics from referenced applications for a portfolio page."""
        total = await self.db.portfolios.count_documents(query)
        pipeline = [{"$match": query}, {"$sort": {"name": 1, "_id": 1}}, {"$skip": offset}, {"$limit": limit},
            {"$lookup": {"from": "applications", "let": {"pid": {"$toString": "$_id"}}, "pipeline": [
                {"$match": {"$expr": {"$eq": ["$portfolioId", "$$pid"]}}},
                {"$group": {"_id": None, "count": {"$sum": 1}, "average": {"$avg": "$qualityScore"}}}], "as": "metrics"}},
            {"$set": {"applicationCount": {"$ifNull": [{"$arrayElemAt": ["$metrics.count", 0]}, 0]},
                      "qualityScore": {"$round": [{"$arrayElemAt": ["$metrics.average", 0]}, 0]}}},
            {"$unset": "metrics"}]
        cursor = await self.db.portfolios.aggregate(pipeline)
        return {"items": await cursor.to_list(None), "total": total, "limit": limit, "offset": offset}

    async def applications(self, identity: str, limit: int, offset: int) -> dict:
        """List only the selected portfolio's linked applications."""
        query = {"portfolioId": identity}
        total = await self.db.applications.count_documents(query)
        cursor = self.db.applications.find(query, {"name": 1, "portfolioId": 1, "qualityScore": 1, "riskLevel": 1}).sort([("name", 1), ("_id", 1)]).skip(offset).limit(limit)
        return {"items": await cursor.to_list(None), "total": total, "limit": limit, "offset": offset}

    async def mutate(self, action: str, user: dict, identity: ObjectId, values: dict | None = None) -> bool:
        """Commit the portfolio change, cascade and audit together or not at all."""
        now = datetime.now(timezone.utc)
        async with self.db.client.start_session() as session:
            async with await session.start_transaction():
                if action == "create":
                    await self.db.portfolios.insert_one({"_id": identity, **values, "createdAt": now, "updatedAt": now}, session=session)
                elif action == "edit":
                    result = await self.db.portfolios.update_one({"_id": identity}, {"$set": {**values, "updatedAt": now}}, session=session)
                    if not result.matched_count:
                        return False
                else:
                    result = await self.db.portfolios.delete_one({"_id": identity}, session=session)
                    if not result.deleted_count:
                        return False
                    await self.db.applications.delete_many({"portfolioId": str(identity)}, session=session)
                await self.db.audit_logs.insert_one({"timestamp": now, "createdAt": now, "updatedAt": now,
                    "userId": user["_id"], "userName": user["name"], "action": action,
                    "entityType": "portfolio", "entityId": str(identity), "details": {"create": "Portfolio created", "edit": "Portfolio edited", "delete": "Portfolio deleted"}[action]}, session=session)
        return True
