"""Expose authentication and self-service profile routes."""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from app.auth.repository import AuthRepository
from app.auth.schemas import LoginRequest, LoginResponse, PasswordUpdate, ProfileUpdate, UserResponse
from app.auth.service import AuthService
from app.core.database import get_database
from app.core.security import decode_token

router = APIRouter(prefix="/api", tags=["identity"])
bearer = HTTPBearer(auto_error=False)


def service(request: Request, db=Depends(get_database)) -> AuthService:
    """Construct the request-scoped identity service."""
    return AuthService(AuthRepository(db), request.app.state.settings)


async def current_session(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)], svc: Annotated[AuthService, Depends(service)]) -> tuple[dict, dict]:
    """Reload the active account for every bearer-authenticated request."""
    denied = HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise denied
    try:
        claims = decode_token(credentials.credentials, request.app.state.settings)
        user = await svc.repo.by_id(claims["sub"])
        if not user or user["status"] != "Active" or user.get("tokenVersion", 0) != claims["ver"] or await svc.repo.revoked(claims["jti"]):
            raise denied
        return user, claims
    except (JWTError, KeyError, TypeError, ValueError):
        raise denied


@router.post("/auth/login", response_model=LoginResponse)
async def login(payload: LoginRequest, svc: Annotated[AuthService, Depends(service)]) -> dict:
    """Authenticate a local account."""
    return await svc.login(payload.email, payload.password)


@router.get("/auth/me", response_model=UserResponse)
async def me(session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AuthService, Depends(service)]) -> dict:
    """Return current identity and live permissions."""
    return await svc.repo.public_user(session[0])


@router.post("/auth/logout", status_code=204)
async def logout(session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AuthService, Depends(service)]) -> Response:
    """Revoke the caller's current bearer token."""
    await svc.logout(session[1])
    return Response(status_code=204)


@router.put("/profile", response_model=UserResponse)
async def profile(payload: ProfileUpdate, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AuthService, Depends(service)]) -> dict:
    """Persist the caller's landing preference."""
    return await svc.update_profile(session[0], payload.defaultLandingPage)


@router.put("/profile/password", status_code=204)
async def password(payload: PasswordUpdate, session: Annotated[tuple[dict, dict], Depends(current_session)], svc: Annotated[AuthService, Depends(service)]) -> Response:
    """Update a password after verifying the old one."""
    await svc.change_password(session[0], payload.currentPassword, payload.newPassword)
    return Response(status_code=204)
