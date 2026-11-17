"""Build scoped report pages and audited CSV snapshots."""

import csv
import io
from datetime import datetime, timezone

from fastapi import HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from app.applications.repository import ApplicationRepository
from app.applications.schemas import ApplicationResponse
from app.applications.service import ApplicationService
from app.portfolios.repository import PortfolioRepository
from app.portfolios.schemas import PortfolioResponse
from app.portfolios.service import PortfolioService


class ReportService:
    """Reuse inventory access rules for report reads and exports."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Bind the database and existing inventory policies."""
        self.db = db
        self.applications = ApplicationService(ApplicationRepository(db))
        self.portfolios = PortfolioService(PortfolioRepository(db))

    async def page(self, user: dict, kind: str, limit: int, offset: int, session=None) -> dict:
        """Return a sorted, scoped page with live portfolio metrics."""
        if kind == "applications":
            return await self.applications.repo.page(self.applications.scope(user), limit, offset, session)
        query = self.portfolios.scope(user)
        total = await self.db.portfolios.count_documents(query, session=session)
        pipeline = [
            {"$match": query}, {"$sort": {"name": 1, "_id": 1}}, {"$skip": offset}, {"$limit": limit},
            {"$lookup": {"from": "applications", "let": {"pid": {"$toString": "$_id"}}, "pipeline": [
                {"$match": {"$expr": {"$eq": ["$portfolioId", "$$pid"]}}},
                {"$group": {"_id": None, "count": {"$sum": 1}, "average": {"$avg": "$qualityScore"}}}
            ], "as": "metrics"}},
            {"$set": {"applicationCount": {"$ifNull": [{"$arrayElemAt": ["$metrics.count", 0]}, 0]},
                      "qualityScore": {"$cond": [{"$gt": [{"$size": "$metrics"}, 0]},
                          {"$floor": {"$add": [{"$arrayElemAt": ["$metrics.average", 0]}, 0.5]}}, None]}}},
            {"$unset": "metrics"},
        ]
        cursor = await self.db.portfolios.aggregate(pipeline, session=session)
        return {"items": await cursor.to_list(None), "total": total, "limit": limit, "offset": offset}

    async def get(self, user: dict, kind: str, limit: int, offset: int) -> dict:
        """Authorize and read a report page."""
        await self.applications.authorize(user, "view")
        return await self.page(user, kind, limit, offset)

    async def export(self, user: dict, kind: str) -> str:
        """Return a bounded CSV only if its audit entry commits."""
        await self.applications.authorize(user, "view")
        await self.applications.authorize(user, "export")
        columns = (["name", "portfolioName", "portfolioId", "description", "productArea", "businessOwner", "technologyOwner", "etsOwner", "criticality", "tier", "lifecycleStatus", "technologyStack", "repositoryLink", "pipelineLink", "applicationHealthScore", "qualityScore", "automationCoverage", "unitTestCoverage", "openDefects", "openCriticalDefects", "riskLevel"] if kind == "applications" else
                   ["name", "owner", "description", "productArea", "status", "applicationCount", "qualityScore"])

        async def transaction(session):
            """Read and serialize a snapshot before recording the export."""
            collection = self.db.applications if kind == "applications" else self.db.portfolios
            query = self.applications.scope(user) if kind == "applications" else self.portfolios.scope(user)
            if await collection.count_documents(query, limit=10001, session=session) > 10000:
                raise HTTPException(413, "Export exceeds 10000 records")
            page = await self.page(user, kind, 10000, 0, session)
            model = ApplicationResponse if kind == "applications" else PortfolioResponse
            output = io.StringIO(newline="")
            writer = csv.writer(output)
            writer.writerow(columns)
            for raw in page["items"]:
                row = model.model_validate(raw).model_dump(mode="json")
                cells = []
                for column in columns:
                    value = str(row.get(column) if row.get(column) is not None else "")
                    if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
                        value = "'" + value
                    cells.append(value)
                writer.writerow(cells)
            now = datetime.now(timezone.utc)
            await self.db.audit_logs.insert_one({"timestamp": now, "createdAt": now, "updatedAt": now,
                "userId": user["_id"], "userName": user["name"], "action": "export",
                "entityType": "report", "entityId": None, "details": f"Exported {kind} report"}, session=session)
            return output.getvalue()

        async with self.db.client.start_session() as session:
            return await session.with_transaction(transaction)
