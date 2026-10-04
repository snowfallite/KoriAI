"""App factory: uvicorn app.main:create_app --factory --workers 1 (tech.md AD-02)."""

import importlib
import importlib.util
import pkgutil
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from app import domains
from app.config import Settings
from app.core.logging import configure_logging
from app.core.security import RateLimiter
from app.http import dev, errors, health, openapi, sse
from app.http.events import RunEventBus
from app.http.middleware import GuardMiddleware, RequestContextMiddleware
from app.jobs.app import run_queue


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
        async with run_queue(app.state):
            yield
        await engine.dispose()

    app = FastAPI(title="Kōri", lifespan=lifespan, responses=openapi.ERROR_RESPONSES)
    app.state.settings = config
    app.state.limiter = RateLimiter()
    app.state.events = RunEventBus(config.RUN_EVENTS_TTL_S)
    errors.install(app)
    openapi.install(app)
    # The last one added runs first: the request id wraps the guard's answers.
    app.add_middleware(GuardMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health.router)
    app.include_router(dev.router)
    app.include_router(sse.router)
    # Every domain with a router.py joins on its own: slices never edit this file (§16.1).
    for module in pkgutil.iter_modules(domains.__path__):
        name = f"{domains.__name__}.{module.name}.router"
        if importlib.util.find_spec(name) is not None:
            app.include_router(importlib.import_module(name).router)
    return app
