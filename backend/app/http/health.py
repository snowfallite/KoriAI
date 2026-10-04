"""Liveness and readiness (tech.md §3.6, §6.7)."""

import asyncio

import httpx
import structlog
from fastapi import APIRouter, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config import Settings
from app.contracts.api.health import HealthOut, ReadyOut
from app.gateways.factory import Gateways
from app.jobs.app import procrastinate_app

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/health", tags=["health"])
PROBE_TIMEOUT_S = 2


@router.get("")
async def health() -> HealthOut:
    return HealthOut(status="ok")


@router.get("/ready", responses={503: {"model": ReadyOut}})
async def ready(request: Request, response: Response) -> ReadyOut:
    settings: Settings = request.app.state.settings
    db, qdrant, queue = await asyncio.gather(
        _db_ready(request.app.state.engine), _qdrant_ready(settings), _queue_ready()
    )
    gateways: Gateways = request.app.state.gateways
    out = ReadyOut(db=db, qdrant=qdrant, queue=queue, llm_gate=gateways.gate.stats())
    if not (db and qdrant and queue):
        response.status_code = 503
    return out


async def _db_ready(engine: AsyncEngine) -> bool:
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_S), engine.connect() as conn:
            await conn.execute(text("select 1"))
    except Exception as exc:  # any failure means not ready
        log.warning("db_not_ready", error=repr(exc))
        return False
    return True


async def _queue_ready() -> bool:
    # The workers restart on their own once the queue tables answer (app.jobs.app).
    try:
        async with asyncio.timeout(PROBE_TIMEOUT_S):
            return await procrastinate_app.check_connection_async()
    except Exception as exc:  # any failure means not ready
        log.warning("queue_not_ready", error=repr(exc))
        return False


async def _qdrant_ready(settings: Settings) -> bool:
    if settings.VECTORS_MODE != "qdrant":
        return True  # the in-memory store has nothing to wait for
    api_key = settings.QDRANT_API_KEY.get_secret_value()
    try:
        async with httpx.AsyncClient(timeout=PROBE_TIMEOUT_S) as client:
            reply = await client.get(
                f"{settings.QDRANT_URL.rstrip('/')}/readyz",
                headers={"api-key": api_key} if api_key else None,
            )
    except httpx.HTTPError as exc:
        log.warning("qdrant_not_ready", error=repr(exc))
        return False
    return reply.is_success
