"""Hash credentials and issue and verify signed access tokens."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import Settings


def hash_password(password: str) -> str:
    """Return a bcrypt hash of a password no longer than 72 bytes."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    """Compare credentials without exposing malformed hashes."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, UnicodeError):
        return False


def create_token(user: dict, settings: Settings) -> str:
    """Issue a short-lived bearer token bound to a credential version."""
    identity = str(user["_id"])
    return jwt.encode({"sub": identity, "userId": identity, "role": user["role"],
                       "ver": user.get("tokenVersion", 0), "jti": uuid4().hex,
                       "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_minutes)},
                      settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, settings: Settings) -> dict:
    """Verify a token signature and required claims or raise JWTError."""
    claims = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"], options={"require_exp": True, "require_sub": True, "require_jti": True})
    if (not isinstance(claims.get("ver"), int) or not isinstance(claims.get("sub"), str)
            or not isinstance(claims.get("jti"), str) or claims.get("userId") != claims.get("sub")):
        raise JWTError("Invalid token claims")
    return claims
