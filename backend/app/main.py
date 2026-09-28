"""App factory: uvicorn app.main:create_app --factory --workers 1 (tech.md AD-02)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import Settings
from app.core.logging import configure_logging
from app.http import errors, health
from app.http.middleware import RequestContextMiddleware


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    configure_logging(config.LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_async_engine(
            config.DATABASE_URL.get_secret_value(),
            pool_size=config.DB_POOL_SIZE,
            pool_pre_ping=True,
        )
        app.state.engine = engine
        yield
        await engine.dispose()

    app = FastAPI(title="Kōri", lifespan=lifespan)
    app.state.settings = config
    errors.install(app)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    return app
