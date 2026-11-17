"""Assemble the API and manage its pooled MongoDB connection."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pymongo import AsyncMongoClient
from app.auth.router import router
from app.portfolios.router import router as portfolios_router
from app.applications.router import router as applications_router
from app.dashboard.router import router as dashboard_router
from app.core.config import Settings
from app.core.database import create_indexes
from app.core.seed import seed_database


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application, deferring configuration and I/O until startup."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Connect, index, seed when enabled, and close the database."""
        config = settings or Settings()
        client = AsyncMongoClient(config.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=5000)
        app.state.settings = config
        app.state.db = client[config.mongodb_db]
        try:
            await create_indexes(app.state.db)
            if config.seed_on_startup:
                await seed_database(app.state.db, config)
            yield
        finally:
            await client.close()

    app = FastAPI(title="KP ETSIP API", version="1.0", lifespan=lifespan)
    # Resolve origins at request time through configuration, but allow importing without secrets.
    config = settings
    if config is None:
        import os
        from dotenv import dotenv_values
        origins = os.environ.get("CORS_ORIGINS") or dotenv_values(".env").get("CORS_ORIGINS") or "http://localhost:5173"
    else:
        origins = config.cors_origins
    app.add_middleware(CORSMiddleware, allow_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
                       allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Authorization", "Content-Type"])
    app.include_router(router)
    app.include_router(portfolios_router)
    app.include_router(applications_router)
    app.include_router(dashboard_router)

    @app.get("/api/health", tags=["health"])
    async def health() -> dict[str, str]:
        """Report process liveness without querying external dependencies."""
        return {"status": "ok"}

    return app


app = create_app()
