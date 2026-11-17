"""Aggregate visible portfolio inventory for the executive dashboard."""

from bson import ObjectId
from fastapi import HTTPException
from pymongo.asynchronous.database import AsyncDatabase
from app.portfolios.repository import PortfolioRepository
from app.portfolios.service import PortfolioService


class DashboardService:
    """Apply the shared visibility policy and derive dashboard metrics."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Bind the pooled database and existing portfolio policy."""
        self.db = db
        self.policy = PortfolioService(PortfolioRepository(db))

    async def executive(self, user: dict, portfolio_id: str | None = None,
                        product_area: str | None = None, risk_level: str | None = None) -> dict:
        """Summarize filtered inventory without disclosing inaccessible portfolios."""
        await self.policy.authorize(user, "view")
        query = self.policy.scope(user)
        if portfolio_id:
            if not ObjectId.is_valid(portfolio_id):
                raise HTTPException(422, "Invalid portfolio identifier")
            oid = ObjectId(portfolio_id)
            if query and oid not in query["_id"]["$in"]:
                query["_id"] = {"$in": []}
            else:
                query["_id"] = oid
        if product_area:
            query["productArea"] = product_area

        app_match = {"$expr": {"$eq": ["$portfolioId", "$$pid"]}}
        if risk_level:
            app_match["riskLevel"] = risk_level
        pipeline = [
            {"$match": query},
            {"$lookup": {"from": "applications", "let": {"pid": {"$toString": "$_id"}},
                "pipeline": [{"$match": app_match}, {"$group": {
                    "_id": None, "count": {"$sum": 1}, "quality": {"$sum": "$qualityScore"},
                    "health": {"$sum": "$applicationHealthScore"}, "automation": {"$sum": "$automationCoverage"},
                    "defects": {"$sum": "$openCriticalDefects"},
                    "risk": {"$sum": {"$cond": [{"$eq": ["$riskLevel", "High"]}, 1, 0]}}
                }}], "as": "metrics"}},
            {"$set": {"metrics": {"$ifNull": [{"$arrayElemAt": ["$metrics", 0]}, {}]}}},
        ]
        if risk_level:
            pipeline.append({"$match": {"metrics.count": {"$gt": 0}}})
        pipeline.extend([{"$sort": {"name": 1, "_id": 1}}, {"$project": {"name": 1, "metrics": 1}}])
        cursor = await self.db.portfolios.aggregate(pipeline)
        rows = await cursor.to_list(None)
        count = sum(row.get("metrics", {}).get("count", 0) for row in rows)

        def average(total: int, size: int) -> int | None:
            """Round nonnegative score averages to the nearest integer, with halves up."""
            return (2 * total + size) // (2 * size) if size else None

        def total(field: str) -> int:
            """Sum a grouped application field over the visible portfolios."""
            return sum(row.get("metrics", {}).get(field, 0) for row in rows)

        return {
            "enterpriseQualityScore": average(total("quality"), count),
            "applicationHealthScore": average(total("health"), count),
            "automationMaturityScore": average(total("automation"), count),
            "openCriticalDefects": total("defects"), "applicationsAtRisk": total("risk"),
            "totalApplications": count, "totalPortfolios": len(rows),
            "portfolios": [{"id": str(row["_id"]), "name": row["name"],
                "applicationCount": row.get("metrics", {}).get("count", 0),
                "qualityScore": average(row.get("metrics", {}).get("quality", 0), row.get("metrics", {}).get("count", 0)),
                "applicationsAtRisk": row.get("metrics", {}).get("risk", 0)} for row in rows],
        }
