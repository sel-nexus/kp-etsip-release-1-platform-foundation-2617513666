"""Enforce inventory authorization, scope and export policy."""

import csv
import io
import re
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from app.applications.repository import ApplicationRepository
from app.applications.schemas import ApplicationInput


class ApplicationService:
    """Apply hard role limits in addition to live permissions."""

    def __init__(self, repo: ApplicationRepository) -> None:
        """Bind the application repository."""
        self.repo = repo

    async def authorize(self, user: dict, permission: str) -> None:
        """Reject actions outside the role or its current permissions."""
        allowed = {"view": {"Administrator", "Executive", "Portfolio Leader", "Engineer", "Auditor", "Read Only"},
                   "create": {"Administrator", "Portfolio Leader", "Engineer"},
                   "edit": {"Administrator", "Portfolio Leader", "Engineer"},
                   "delete": {"Administrator"},
                   "export": {"Administrator", "Executive", "Portfolio Leader", "Engineer", "Auditor"}}
        role = await self.repo.db.roles.find_one({"name": user["role"]})
        if user["role"] not in allowed[permission] or not role or permission not in role.get("permissions", []):
            raise HTTPException(403, "Insufficient permissions")

    def scope(self, user: dict) -> dict:
        """Restrict leaders to their explicitly assigned portfolios."""
        if user["role"] == "Portfolio Leader":
            return {"portfolioId": {"$in": [str(ObjectId(v)) for v in user.get("portfolioAccess", []) if isinstance(v, str) and ObjectId.is_valid(v)]}}
        return {}

    def identifier(self, identity: str) -> ObjectId:
        """Validate a resource identifier."""
        if not ObjectId.is_valid(identity):
            raise HTTPException(422, "Invalid application identifier")
        return ObjectId(identity)

    def query(self, user: dict, search: str, portfolio: str | None, criticality: str | None, risk: str | None, lifecycle: str | None) -> dict:
        """Build an injection-safe query without weakening portfolio scope."""
        query = self.scope(user)
        if portfolio:
            if not ObjectId.is_valid(portfolio):
                raise HTTPException(422, "Invalid portfolio identifier")
            portfolio = str(ObjectId(portfolio))
            if query and portfolio not in query["portfolioId"]["$in"]:
                query["portfolioId"] = {"$in": []}
            else:
                query["portfolioId"] = portfolio
        if search:
            query["name"] = {"$regex": re.escape(search), "$options": "i"}
        for key, value in (("criticality", criticality), ("riskLevel", risk), ("lifecycleStatus", lifecycle)):
            if value:
                query[key] = value
        return query

    async def list(self, user: dict, query: dict, limit: int, offset: int) -> dict:
        """List only visible inventory."""
        await self.authorize(user, "view")
        return await self.repo.page(query, limit, offset)

    async def detail(self, user: dict, identity: str, permission: str = "view") -> dict:
        """Return a scoped record without disclosing inaccessible records."""
        await self.authorize(user, permission)
        page = await self.repo.page({"_id": self.identifier(identity), **self.scope(user)}, 1, 0)
        if not page["items"]:
            raise HTTPException(404, "Application not found")
        return page["items"][0]

    async def save(self, user: dict, payload: ApplicationInput, identity: str | None = None) -> dict:
        """Commit a validated create or update and its audit event."""
        action = "edit" if identity else "create"
        await self.authorize(user, action)
        scope = self.scope(user)
        if scope and payload.portfolioId not in scope["portfolioId"]["$in"]:
            raise HTTPException(404, "Portfolio not found")
        oid = self.identifier(identity) if identity else ObjectId()
        try:
            result = await self.repo.mutate(user, action, oid, scope, payload.model_dump(mode="json"))
        except DuplicateKeyError as exc:
            if exc.details and exc.details.get("keyPattern") == {"name": 1}:
                raise HTTPException(409, "Application name already exists") from exc
            raise
        if result is None:
            raise HTTPException(404, "Application not found")
        if result.get("missingPortfolio"):
            raise HTTPException(404, "Portfolio not found")
        return result

    async def delete(self, user: dict, identity: str) -> None:
        """Delete an application and its audit event atomically."""
        await self.authorize(user, "delete")
        if await self.repo.mutate(user, "delete", self.identifier(identity), self.scope(user)) is None:
            raise HTTPException(404, "Application not found")

    async def csv(self, user: dict, query: dict) -> str:
        """Export visible filtered inventory with spreadsheet formula protection."""
        await self.authorize(user, "view")
        await self.authorize(user, "export")
        rows = await self.repo.export(user, query)
        if rows is None:
            raise HTTPException(413, "Export exceeds 10000 applications; narrow the filters")
        columns = ["name", "portfolioName", "portfolioId", "description", "productArea", "businessOwner", "technologyOwner", "etsOwner", "criticality", "tier", "lifecycleStatus", "technologyStack", "repositoryLink", "pipelineLink", "applicationHealthScore", "qualityScore", "automationCoverage", "unitTestCoverage", "openDefects", "openCriticalDefects", "riskLevel"]
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            cells = []
            for column in columns:
                value = str(row.get(column) if row.get(column) is not None else "")
                if value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
                    value = "'" + value
                cells.append(value)
            writer.writerow(cells)
        return output.getvalue()
