"""Provide an isolated real MongoDB replica set for identity tests."""

import os
import shutil
import socket
import subprocess
import tempfile
import time
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from app.core.config import Settings
from app.main import create_app


@pytest.fixture(scope="session")
def mongo_uri():
    """Use a supplied test replica set or launch a temporary local one."""
    configured = os.getenv("TEST_MONGODB_URI")
    if configured:
        yield configured
        return
    executable = shutil.which("mongod")
    if not executable:
        pytest.fail("mongod is required, or set TEST_MONGODB_URI to a test replica set")
    with tempfile.TemporaryDirectory(prefix="ketsip-test-mongo-") as directory:
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen([executable, "--dbpath", directory, "--port", str(port), "--bind_ip", "127.0.0.1", "--replSet", "identityTest", "--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        uri = f"mongodb://127.0.0.1:{port}/?replicaSet=identityTest"
        client = MongoClient(f"mongodb://127.0.0.1:{port}/?directConnection=true", serverSelectionTimeoutMS=300)
        try:
            for _ in range(100):
                try:
                    client.admin.command("ping")
                    break
                except PyMongoError:
                    if process.poll() is not None:
                        pytest.fail("mongod exited while starting")
                    time.sleep(0.1)
            client.admin.command("replSetInitiate", {"_id": "identityTest", "members": [{"_id": 0, "host": f"127.0.0.1:{port}"}]})
            for _ in range(100):
                if client.admin.command("hello").get("isWritablePrimary"):
                    break
                time.sleep(0.1)
            else:
                pytest.fail("test replica set did not elect a primary")
            yield uri
        finally:
            client.close()
            process.terminate()
            process.wait(timeout=10)


@pytest_asyncio.fixture
async def client(mongo_uri):
    """Create a unique seeded database and discard only that test database."""
    config = Settings(mongodb_uri=mongo_uri, mongodb_db="identity_test_" + uuid4().hex,
                      jwt_secret="test-secret-unique-value-not-for-production-123456789",
                      bootstrap_password="Test-password-1234", seed_on_startup=True)
    app = create_app(config)
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
            yield test_client, app.state.db
        await app.state.db.client.drop_database(config.mongodb_db)
