"""Exercise authentication and durable profile behavior against real MongoDB."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from jose import jwt

from app.auth.repository import AuthRepository
from app.auth.service import AuthService
from app.core.security import decode_token, verify_password
from app.core.seed import seed_database


async def login(http, email="admin@ketsip.local", password="Test-password-1234"):
    """Submit test credentials to the real login route."""
    return await http.post("/api/auth/login", json={"email": email, "password": password})


async def test_seed_login_and_failure_audit(client):
    """Seed all roles, issue a valid token, and audit valid and invalid attempts."""
    http, db = client
    assert await db.users.count_documents({}) == 6
    assert await db.roles.count_documents({}) == 6
    from app.core.config import Settings
    settings = Settings(mongodb_uri="mongodb://unused", mongodb_db="unused", jwt_secret="another-test-secret-long-enough-for-testing-1234", bootstrap_password="Test-password-1234")
    await seed_database(db, settings)
    assert await db.users.count_documents({}) == 6
    assert await db.roles.count_documents({}) == 6
    response = await login(http)
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["role"] == "Administrator"
    assert "passwordHash" not in body["user"]
    claims = jwt.get_unverified_claims(body["token"])
    assert claims["userId"] == body["user"]["id"] == claims["sub"]
    assert claims["role"] == "Administrator"
    assert (await login(http, password="wrong")).status_code == 401
    assert (await login(http, email="unknown@ketsip.local")).status_code == 401
    records = await db.audit_logs.find({"action": "login"}).sort([("timestamp", 1), ("_id", 1)]).to_list(None)
    assert [r["details"] for r in records] == ["Login succeeded", "Login failed", "Login failed"]
    assert records[-1]["userId"] is None and records[-1]["userName"] == "Unknown user"
    assert "wrong" not in str(records)
    assert (await db.users.find_one({"email": "admin@ketsip.local"}))["lastLogin"] is not None


async def test_authentication_revocation_and_live_role(client):
    """Reject missing, invalid, logged-out, and deactivated sessions."""
    http, db = client
    assert (await http.get("/api/auth/me")).status_code == 401
    assert (await http.get("/api/auth/me", headers={"Authorization": "Bearer broken"})).status_code == 401
    token = (await login(http)).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert (await http.get("/api/auth/me", headers=headers)).status_code == 200
    await db.roles.update_one({"name": "Administrator"}, {"$set": {"permissions": ["view"]}})
    assert (await http.get("/api/auth/me", headers=headers)).json()["permissions"] == ["view"]
    await db.users.update_one({"email": "admin@ketsip.local"}, {"$set": {"status": "Inactive"}})
    assert (await http.get("/api/auth/me", headers=headers)).status_code == 401
    assert (await login(http)).status_code == 401
    await db.users.update_one({"email": "admin@ketsip.local"}, {"$set": {"status": "Active"}})
    assert (await http.post("/api/auth/logout", headers=headers)).status_code == 204
    assert (await http.get("/api/auth/me", headers=headers)).status_code == 401
    assert (await http.post("/api/auth/logout", headers=headers)).status_code == 401


async def test_profile_and_password_persist_validate_and_revoke(client):
    """Persist preferences and enforce current-password and password rules."""
    http, db = client
    token = (await login(http)).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    assert (await http.put("/api/profile", headers=headers, json={"defaultLandingPage": "bad"})).status_code == 422
    assert (await http.put("/api/profile", headers=headers, json={"defaultLandingPage": "applications"})).json()["defaultLandingPage"] == "applications"
    assert (await db.users.find_one({"email": "admin@ketsip.local"}))["defaultLandingPage"] == "applications"
    path = "/api/profile/password"
    assert (await http.put(path, headers=headers, json={"currentPassword": "wrong", "newPassword": "A-new-password-123"})).status_code == 400
    assert (await http.put(path, headers=headers, json={"currentPassword": "Test-password-1234", "newPassword": "short"})).status_code == 422
    assert (await http.put(path, headers=headers, json={"currentPassword": "Test-password-1234", "newPassword": "Test-password-1234"})).status_code == 400
    assert (await http.put(path, headers=headers, json={"currentPassword": "Test-password-1234", "newPassword": "A-new-password-123"})).status_code == 204
    assert (await http.get("/api/auth/me", headers=headers)).status_code == 401
    assert (await login(http)).status_code == 401
    assert (await login(http, password="A-new-password-123")).status_code == 200
    assert await db.audit_logs.count_documents({"action": "edit"}) == 2


async def test_service_login_persists_timestamp_and_audit(client):
    """Authenticate directly and persist the successful attempt."""
    http, db = client
    service = AuthService(AuthRepository(db), http._transport.app.state.settings)
    result = await service.login(" ADMIN@KETSIP.LOCAL ", "Test-password-1234")
    user = await db.users.find_one({"email": "admin@ketsip.local"})
    claims = decode_token(result["token"], service.settings)
    assert claims["sub"] == str(user["_id"])
    assert result["user"]["permissions"] == (await db.roles.find_one({"name": "Administrator"}))["permissions"]
    assert user["lastLogin"] is not None
    assert await db.audit_logs.count_documents({"userId": user["_id"], "action": "login", "details": "Login succeeded"}) == 1


@pytest.mark.parametrize("email,password,inactive", [
    ("unknown@ketsip.local", "Test-password-1234", False),
    ("admin@ketsip.local", "wrong", False),
    ("admin@ketsip.local", "Test-password-1234", True),
])
async def test_service_login_rejects_invalid_credentials_and_audits(client, email, password, inactive):
    """Reject unknown, incorrect, and inactive accounts without exposing credentials."""
    http, db = client
    service = AuthService(AuthRepository(db), http._transport.app.state.settings)
    if inactive:
        await db.users.update_one({"email": "admin@ketsip.local"}, {"$set": {"status": "Inactive"}})
    with pytest.raises(HTTPException) as error:
        await service.login(email, password)
    assert error.value.status_code == 401
    assert error.value.detail == "Invalid email or password"
    event = await db.audit_logs.find_one({"action": "login"})
    assert event["details"] == "Login failed"
    assert password not in str(event)
    assert (await db.users.find_one({"email": "admin@ketsip.local"}))["lastLogin"] is None


async def test_service_login_rejects_account_changed_after_lookup(client):
    """Reject a login when the account is deactivated before its transactional update."""
    http, db = client

    class DeactivatingRepository(AuthRepository):
        async def by_email(self, email):
            user = await super().by_email(email)
            await self.db.users.update_one({"_id": user["_id"]}, {"$set": {"status": "Inactive"}})
            return user

    service = AuthService(DeactivatingRepository(db), http._transport.app.state.settings)
    with pytest.raises(HTTPException) as error:
        await service.login("admin@ketsip.local", "Test-password-1234")
    assert error.value.status_code == 401
    assert await db.audit_logs.count_documents({"action": "login", "details": "Login failed"}) == 1
    assert await db.audit_logs.count_documents({"action": "login", "details": "Login succeeded"}) == 0
    assert (await db.users.find_one({"email": "admin@ketsip.local"}))["lastLogin"] is None


async def test_service_profile_persists_and_rejects_inactive_account(client):
    """Update a preference with an audit event only for an active account."""
    http, db = client
    service = AuthService(AuthRepository(db), http._transport.app.state.settings)
    user = await service.repo.by_email("admin@ketsip.local")
    result = await service.update_profile(user, "applications")
    assert result["defaultLandingPage"] == "applications"
    assert (await service.repo.by_id(str(user["_id"])))["defaultLandingPage"] == "applications"
    assert await db.audit_logs.count_documents({"action": "edit", "details": "Landing preference updated"}) == 1
    await db.users.update_one({"_id": user["_id"]}, {"$set": {"status": "Inactive"}})
    with pytest.raises(HTTPException) as error:
        await service.update_profile(user, "dashboard")
    assert error.value.status_code == 401
    assert (await service.repo.by_id(str(user["_id"])))["defaultLandingPage"] == "applications"
    assert await db.audit_logs.count_documents({"action": "edit"}) == 1


async def test_service_password_changes_persist_and_revoke_old_tokens(client):
    """Persist a new hash and token version, invalidating an existing session."""
    http, db = client
    service = AuthService(AuthRepository(db), http._transport.app.state.settings)
    token = (await service.login("admin@ketsip.local", "Test-password-1234"))["token"]
    user = await service.repo.by_email("admin@ketsip.local")
    await service.change_password(user, "Test-password-1234", "A-new-password-123")
    saved = await service.repo.by_id(str(user["_id"]))
    assert saved["passwordHash"] != user["passwordHash"]
    assert verify_password("A-new-password-123", saved["passwordHash"])
    assert not verify_password("Test-password-1234", saved["passwordHash"])
    assert saved["tokenVersion"] == user.get("tokenVersion", 0) + 1
    assert await db.audit_logs.count_documents({"action": "edit", "details": "Password changed"}) == 1
    assert (await http.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401


async def test_service_password_rejects_incorrect_same_and_stale_changes(client):
    """Reject invalid passwords and stale writes without changing the hash or audit."""
    http, db = client
    service = AuthService(AuthRepository(db), http._transport.app.state.settings)
    user = await service.repo.by_email("admin@ketsip.local")
    for current, new in [("wrong", "A-new-password-123"), ("Test-password-1234", "Test-password-1234")]:
        with pytest.raises(HTTPException) as error:
            await service.change_password(user, current, new)
        assert error.value.status_code == 400
    await service.change_password(user, "Test-password-1234", "A-new-password-123")
    with pytest.raises(HTTPException) as error:
        await service.change_password(user, "Test-password-1234", "Another-password-123")
    assert error.value.status_code == 409
    saved = await service.repo.by_id(str(user["_id"]))
    assert verify_password("A-new-password-123", saved["passwordHash"])
    assert saved["tokenVersion"] == user.get("tokenVersion", 0) + 1
    assert await db.audit_logs.count_documents({"action": "edit", "details": "Password changed"}) == 1


async def test_service_logout_persists_revocation_until_expiry(client):
    """Store token revocation idempotently and reject the revoked session."""
    http, db = client
    service = AuthService(AuthRepository(db), http._transport.app.state.settings)
    token = (await service.login("admin@ketsip.local", "Test-password-1234"))["token"]
    claims = decode_token(token, service.settings)
    await service.logout(claims)
    await service.logout(claims)
    record = await db.revoked_tokens.find_one({"_id": claims["jti"]})
    assert record is not None
    assert record["expiresAt"].replace(tzinfo=timezone.utc) == datetime.fromtimestamp(claims["exp"], timezone.utc)
    assert await db.revoked_tokens.count_documents({"_id": claims["jti"]}) == 1
    assert (await http.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})).status_code == 401


async def test_auth_rejects_expired_and_malformed_signed_tokens(client):
    """Reject expired, incomplete, incorrectly typed, and incorrectly signed claims."""
    http, db = client
    settings = http._transport.app.state.settings
    user = await db.users.find_one({"email": "admin@ketsip.local"})
    identity = str(user["_id"])
    valid_claims = {"sub": identity, "userId": identity, "ver": user.get("tokenVersion", 0),
                    "jti": "test-token", "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    invalid_claims = [
        {**valid_claims, "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        {key: value for key, value in valid_claims.items() if key != "exp"},
        {key: value for key, value in valid_claims.items() if key != "jti"},
        {**valid_claims, "sub": "not-an-object-id", "userId": "not-an-object-id"},
        {**valid_claims, "userId": "different-user"},
        {**valid_claims, "ver": "0"},
        {**valid_claims, "jti": ["not-a-string"]},
    ]
    tokens = [jwt.encode(claims, settings.jwt_secret, algorithm="HS256") for claims in invalid_claims]
    tokens.append(jwt.encode(valid_claims, "incorrect-signing-key", algorithm="HS256"))
    tokens.append("not.a.valid.token")
    for token in tokens:
        response = await http.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
