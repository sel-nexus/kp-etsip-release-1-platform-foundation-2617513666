"""Implement identity policies independently of HTTP handlers."""

from datetime import datetime, timezone
from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool
from app.auth.repository import AuthRepository
from app.core.config import Settings
from app.core.security import create_token, hash_password, verify_password


class AuthService:
    """Apply credential and profile rules using a Mongo repository."""

    def __init__(self, repo: AuthRepository, settings: Settings) -> None:
        """Bind the persistence and configuration dependencies."""
        self.repo, self.settings = repo, settings

    async def login(self, email: str, password: str) -> dict:
        """Authenticate, audit the attempt, and return a signed token."""
        user = await self.repo.by_email(email)
        valid = user is not None and await run_in_threadpool(verify_password, password, user["passwordHash"])
        if not valid or user["status"] != "Active":
            await self.repo.audit(user, "login", "Login failed")
            raise HTTPException(401, "Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
        if not await self.repo.login_success(user):
            await self.repo.audit(user, "login", "Login failed")
            raise HTTPException(401, "Invalid email or password")
        return {"token": create_token(user, self.settings), "user": await self.repo.public_user(user)}

    async def update_profile(self, user: dict, landing: str) -> dict:
        """Persist a landing preference together with an audit event."""
        if not await self.repo.update_and_audit(user, {"defaultLandingPage": landing}, "Landing preference updated"):
            raise HTTPException(401, "Account is unavailable")
        return await self.repo.public_user(await self.repo.by_id(str(user["_id"])))

    async def change_password(self, user: dict, current: str, new: str) -> None:
        """Change a password and invalidate previously issued tokens."""
        if not await run_in_threadpool(verify_password, current, user["passwordHash"]):
            raise HTTPException(400, "Current password is incorrect")
        if current == new:
            raise HTTPException(400, "New password must be different")
        hashed = await run_in_threadpool(hash_password, new)
        if not await self.repo.update_and_audit(user, {"passwordHash": hashed, "tokenVersion": user.get("tokenVersion", 0) + 1},
                                                "Password changed", {"passwordHash": user["passwordHash"]}):
            raise HTTPException(409, "Account changed; try again")

    async def logout(self, claims: dict) -> None:
        """Persist revocation of the current token until it expires."""
        await self.repo.revoke(claims["jti"], datetime.fromtimestamp(claims["exp"], timezone.utc))
