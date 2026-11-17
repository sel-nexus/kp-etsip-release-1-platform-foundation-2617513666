"""Persist administration changes and audit events atomically in MongoDB."""

from collections.abc import Callable
from datetime import datetime, timezone
from bson import ObjectId
from fastapi import HTTPException
from pymongo.asynchronous.client_session import AsyncClientSession
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.read_concern import ReadConcern


class AdminRepository:
    """Access administrative collections using the application database."""

    def __init__(self, db: AsyncDatabase) -> None:
        """Bind the pooled database."""
        self.db = db

    async def page(self, collection: str, query: dict, limit: int, offset: int) -> dict:
        """Return a bounded page and count."""
        coll = self.db[collection]
        sort = [('timestamp', -1), ('_id', -1)] if collection == 'audit_logs' else [('name', 1), ('_id', 1)]
        items = await coll.find(query, {'passwordHash': 0}).sort(sort).skip(offset).limit(limit).to_list(None)
        return {'items': items, 'total': await coll.count_documents(query), 'limit': limit, 'offset': offset}

    async def audit(self, actor: dict, action: str, kind: str, identity: ObjectId | None, session: AsyncClientSession) -> None:
        """Record actor and target identifiers without storing submitted secrets."""
        now = datetime.now(timezone.utc)
        await self.db.audit_logs.insert_one({'timestamp': now, 'createdAt': now, 'updatedAt': now,
            'userId': actor['_id'], 'userName': actor['name'], 'action': action,
            'entityType': kind, 'entityId': str(identity) if identity is not None else None, 'details': f'{kind.capitalize()} {action}'}, session=session)

    async def mutate_user(self, actor: dict, identity: ObjectId, changes: dict | None, create: bool = False) -> dict | None:
        """Serialize account changes and commit their audit event together."""
        now = datetime.now(timezone.utc)
        async def transaction(session: AsyncClientSession) -> dict | None:
            """Apply one retryable account transaction."""
            # A common write prevents concurrent transactions from removing two final administrators.
            await self.db.admin_locks.update_one({'_id': 'users'}, {'$inc': {'revision': 1}}, upsert=True, session=session)
            old = await self.db.users.find_one({'_id': identity}, session=session)
            if not create and not old:
                raise HTTPException(404, 'User not found')
            if old and old['role'] == 'Administrator' and old['status'] == 'Active' and (changes is None or changes['role'] != 'Administrator' or changes['status'] != 'Active'):
                count = await self.db.users.count_documents({'role': 'Administrator', 'status': 'Active'}, session=session)
                if count <= 1:
                    raise HTTPException(409, 'Cannot remove the last active Administrator')
            normalized = dict(changes) if changes is not None else None
            if normalized is not None:
                ids = normalized.get('portfolioAccess', [])
                if any(not ObjectId.is_valid(value) for value in ids):
                    raise HTTPException(422, 'Invalid portfolio identifier')
                ids = [str(ObjectId(value)) for value in ids]
                if len(set(ids)) != len(ids) or await self.db.portfolios.count_documents({'_id': {'$in': [ObjectId(value) for value in ids]}}, session=session) != len(ids):
                    raise HTTPException(422, 'Portfolio assignments must be unique and exist')
                normalized['portfolioAccess'] = ids
                if not await self.db.roles.find_one({'name': normalized['role']}, session=session):
                    raise HTTPException(422, 'Role does not exist')
            if create:
                doc = {'_id': identity, **normalized, 'createdAt': now, 'updatedAt': now,
                       'lastLogin': None, 'authSource': 'local', 'managerName': None, 'vendorIndicator': False,
                       'defaultLandingPage': 'dashboard' if normalized['role'] in ('Administrator', 'Executive') else 'applications', 'tokenVersion': 0}
                await self.db.users.insert_one(doc, session=session)
            elif normalized is None:
                await self.db.users.delete_one({'_id': identity}, session=session)
            else:
                update = {'$set': {**normalized, 'updatedAt': now}}
                if 'passwordHash' in normalized:
                    update['$inc'] = {'tokenVersion': 1}
                await self.db.users.update_one({'_id': identity}, update, session=session)
            await self.audit(actor, 'create' if create else 'delete' if normalized is None else 'edit', 'user', identity, session)
            if old and normalized is not None and old['role'] != normalized['role']:
                await self.audit(actor, 'roleChange', 'user', identity, session)
            if normalized is not None:
                return await self.db.users.find_one({'_id': identity}, {'passwordHash': 0}, session=session)
            return None

        async with self.db.client.start_session() as session:
            return await session.with_transaction(transaction)

    async def mutate_role(self, actor: dict, identity: ObjectId, changes: dict, create: bool) -> dict:
        """Commit role changes and their audit event together."""
        now = datetime.now(timezone.utc)
        async def transaction(session: AsyncClientSession) -> dict:
            """Apply one retryable role transaction."""
            if changes['name'] == 'Administrator' and 'administer' not in changes['permissions']:
                raise HTTPException(409, 'Administrator must retain administer permission')
            old = None
            if create:
                await self.db.roles.insert_one({'_id': identity, **changes, 'createdAt': now, 'updatedAt': now}, session=session)
            else:
                old = await self.db.roles.find_one({'_id': identity}, session=session)
                if not old:
                    raise HTTPException(404, 'Role not found')
                if old['name'] != changes['name']:
                    raise HTTPException(422, 'Role names cannot be changed')
                await self.db.roles.update_one({'_id': identity}, {'$set': {**changes, 'updatedAt': now}}, session=session)
            await self.audit(actor, 'create' if create else 'edit', 'role', identity, session)
            if old and set(old.get('permissions', [])) != set(changes['permissions']):
                await self.audit(actor, 'permissionChange', 'role', identity, session)
            return await self.db.roles.find_one({'_id': identity}, session=session)

        async with self.db.client.start_session() as session:
            return await session.with_transaction(transaction)

    async def export_audit(self, actor: dict, query: dict, render: Callable[[list[dict]], str]) -> str:
        """Render a bounded snapshot and commit its export event together."""
        async def transaction(session: AsyncClientSession) -> str:
            """Read, render, and audit one retryable export."""
            fields = {field: 1 for field in ('timestamp', 'userId', 'userName', 'action', 'entityType', 'entityId', 'details')}
            rows = await self.db.audit_logs.find(query, fields, session=session).sort([('timestamp', -1), ('_id', -1)]).limit(10001).to_list(10001)
            if len(rows) > 10000:
                raise HTTPException(413, 'Audit export exceeds 10000 records')
            content = render(rows)
            await self.audit(actor, 'export', 'audit', None, session)
            return content

        async with self.db.client.start_session() as session:
            return await session.with_transaction(transaction, read_concern=ReadConcern('snapshot'))
