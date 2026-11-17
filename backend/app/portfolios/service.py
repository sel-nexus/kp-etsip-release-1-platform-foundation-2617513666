"""Enforce portfolio role limits and scope independently of routes."""

import re
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from app.portfolios.repository import PortfolioRepository
from app.portfolios.schemas import PortfolioInput


class PortfolioService:
    """Apply live role permissions and hard portfolio policy."""

    def __init__(self, repo: PortfolioRepository) -> None:
        """Bind a repository for this request."""
        self.repo = repo

    async def authorize(self, user: dict, permission: str) -> None:
        """Deny permissions absent from the current role or beyond its hard limits."""
        role = await self.repo.db.roles.find_one({"name": user["role"]})
        allowed = {"view": {"Administrator", "Executive", "Portfolio Leader", "Engineer", "Auditor", "Read Only"},
                   "create": {"Administrator"}, "edit": {"Administrator", "Portfolio Leader"}, "delete": {"Administrator"}}
        if user["role"] not in allowed[permission] or not role or permission not in role.get("permissions", []):
            raise HTTPException(403, "Insufficient permissions")

    def scope(self, user: dict) -> dict:
        """Limit leaders to valid assigned identifiers; empty scope matches nothing."""
        if user["role"] != "Portfolio Leader":
            return {}
        return {"_id": {"$in": [ObjectId(value) for value in user.get("portfolioAccess", []) if isinstance(value, str) and ObjectId.is_valid(value)]}}

    def identifier(self, value: str) -> ObjectId:
        """Reject malformed resource identifiers."""
        if not ObjectId.is_valid(value):
            raise HTTPException(422, "Invalid portfolio identifier")
        return ObjectId(value)

    async def list(self, user: dict, search: str, status: str | None, product_area: str | None, limit: int, offset: int) -> dict:
        """Filter visible portfolios and return derived metrics."""
        await self.authorize(user, "view")
        query = self.scope(user)
        if search:
            query["name"] = {"$regex": re.escape(search), "$options": "i"}
        if status:
            query["status"] = status
        if product_area:
            query["productArea"] = product_area
        return await self.repo.page(query, limit, offset)

    async def detail(self, user: dict, identity: str, permission: str = "view") -> dict:
        """Find a visible resource without revealing inaccessible portfolios."""
        await self.authorize(user, permission)
        oid = self.identifier(identity)
        query = self.scope(user)
        if query and oid not in query["_id"]["$in"]:
            raise HTTPException(404, "Portfolio not found")
        result = await self.repo.page({"_id": oid}, 1, 0)
        if not result["items"]:
            raise HTTPException(404, "Portfolio not found")
        return result["items"][0]

    async def save(self, user: dict, payload: PortfolioInput, identity: str | None = None) -> dict:
        """Create or update a portfolio, mapping duplicate keys to conflict."""
        action = "edit" if identity else "create"
        if identity:
            await self.detail(user, identity, "edit")
            oid = self.identifier(identity)
        else:
            await self.authorize(user, "create")
            oid = ObjectId()
        try:
            if not await self.repo.mutate(action, user, oid, payload.model_dump()):
                raise HTTPException(404, "Portfolio not found")
        except DuplicateKeyError as exc:
            raise HTTPException(409, "Portfolio name already exists") from exc
        result = await self.repo.page({"_id": oid}, 1, 0)
        return result["items"][0]

    async def delete(self, user: dict, identity: str) -> None:
        """Delete an existing portfolio and its linked applications atomically."""
        await self.authorize(user, "delete")
        if not await self.repo.mutate("delete", user, self.identifier(identity)):
            raise HTTPException(404, "Portfolio not found")

    async def applications(self, user: dict, identity: str, limit: int, offset: int) -> dict:
        """Verify portfolio visibility before exposing linked applications."""
        portfolio = await self.detail(user, identity)
        return await self.repo.applications(str(portfolio["_id"]), limit, offset)
