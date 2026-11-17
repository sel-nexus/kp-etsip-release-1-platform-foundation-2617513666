"""Enforce administration policy and prepare audit exports."""

import csv
import io
from datetime import datetime, time, timedelta, timezone, date
from bson import ObjectId
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError
from starlette.concurrency import run_in_threadpool
from app.admin.repository import AdminRepository
from app.admin.schemas import RoleInput, UserInput
from app.core.security import hash_password


class AdminService:
    """Apply current permissions before accessing administrative data."""

    def __init__(self, repo: AdminRepository) -> None:
        """Bind the administrative repository."""
        self.repo = repo

    async def authorize(self, actor: dict) -> None:
        """Require both the Administrator role and its live permission."""
        role = await self.repo.db.roles.find_one({'name': actor['role']})
        if actor['role'] != 'Administrator' or not role or 'administer' not in role.get('permissions', []):
            raise HTTPException(403, 'Insufficient permissions')

    def identifier(self, value: str) -> ObjectId:
        """Validate a MongoDB identifier."""
        if not ObjectId.is_valid(value):
            raise HTTPException(422, 'Invalid identifier')
        return ObjectId(value)

    async def page(self, actor: dict, collection: str, query: dict, limit: int, offset: int) -> dict:
        """List authorized administrative records."""
        await self.authorize(actor)
        return await self.repo.page(collection, query, limit, offset)

    async def save_user(self, actor: dict, payload: UserInput, identity: str | None = None) -> dict:
        """Create or update an account, hashing any replacement credential."""
        await self.authorize(actor)
        if identity is None and not payload.password:
            raise HTTPException(422, 'Password is required for new users')
        changes = payload.model_dump(exclude={'password'})
        if payload.password:
            changes['passwordHash'] = await run_in_threadpool(hash_password, payload.password)
        try:
            return await self.repo.mutate_user(actor, self.identifier(identity) if identity else ObjectId(), changes, create=identity is None)
        except DuplicateKeyError as exc:
            if exc.details and exc.details.get('keyPattern') == {'email': 1}:
                raise HTTPException(409, 'Email already exists') from exc
            raise

    async def delete_user(self, actor: dict, identity: str) -> None:
        """Hard-delete an account while retaining audit history."""
        await self.authorize(actor)
        await self.repo.mutate_user(actor, self.identifier(identity), None)

    async def save_role(self, actor: dict, payload: RoleInput, identity: str | None = None) -> dict:
        """Persist a supported role without weakening hard resource limits."""
        await self.authorize(actor)
        try:
            return await self.repo.mutate_role(actor, self.identifier(identity) if identity else ObjectId(), payload.model_dump(), identity is None)
        except DuplicateKeyError as exc:
            raise HTTPException(409, 'Role already exists') from exc

    def audit_query(self, user_id: str | None, action: str | None, start: date | None, end: date | None) -> dict:
        """Construct a safe inclusive date and exact-match audit filter."""
        query = {}
        if user_id:
            query['userId'] = self.identifier(user_id)
        if action:
            query['action'] = action
        if start and end and start > end:
            raise HTTPException(422, 'Start date must precede end date')
        if start or end:
            bounds = {}
            if start:
                bounds['$gte'] = datetime.combine(start, time.min, timezone.utc)
            if end and end < date.max:
                bounds['$lt'] = datetime.combine(end + timedelta(days=1), time.min, timezone.utc)
            query['timestamp'] = bounds
        return query

    async def csv(self, actor: dict, query: dict) -> str:
        """Export matching audit records with spreadsheet formula protection."""
        await self.authorize(actor)
        return await self.repo.export_audit(actor, query, self.render_csv)

    def render_csv(self, rows: list[dict]) -> str:
        """Render audit rows as spreadsheet-safe CSV."""
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        fields = ['timestamp', 'userId', 'userName', 'action', 'entityType', 'entityId', 'details']
        writer.writerow(fields)
        for row in rows:
            cells = []
            for field in fields:
                text = str(row.get(field) or '')
                if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
                    text = "'" + text
                cells.append(text)
            writer.writerow(cells)
        return output.getvalue()
