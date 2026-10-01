"""Service tasks of the queue (tech.md §10.2): demo.echo and maintenance.cleanup."""

import asyncio
import time
from pathlib import Path

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from starlette.datastructures import State

from app.contracts.jobs import DemoEchoPayload
from app.db.base import UnitOfWork
from app.db.schema.system import JobMarker, WebCache
from app.db.schema.users import UserSession
from app.jobs.app import periodic, procrastinate_app, task

MEDIA_TTL_S = 30 * 24 * 3600
JOBS_TTL_HOURS = 7 * 24


@task("demo.echo", DemoEchoPayload)
async def demo_echo(payload: DemoEchoPayload, state: State) -> None:
    marker = insert(JobMarker).values(key=payload.key, value=payload.value)
    upsert = marker.on_conflict_do_update(
        index_elements=[JobMarker.key], set_={"value": marker.excluded.value}
    )
    async with UnitOfWork(state.engine) as session:
        await session.execute(upsert)


@periodic("maintenance.cleanup", cron="30 1 * * *", lock="cleanup")
async def cleanup(state: State) -> None:
    async with UnitOfWork(state.engine) as session:
        await session.execute(delete(UserSession).where(UserSession.expires_at < func.now()))
        await session.execute(delete(WebCache).where(WebCache.expires_at < func.now()))
    # FilesPort keeps the media cache under DATA_DIR/media (§8.7).
    await asyncio.to_thread(_drop_files_older, state.settings.DATA_DIR / "media", MEDIA_TTL_S)
    await procrastinate_app.job_manager.delete_old_jobs(
        nb_hours=JOBS_TTL_HOURS, include_failed=True, include_cancelled=True, include_aborted=True
    )


def _drop_files_older(root: Path, age_s: float) -> None:
    oldest = time.time() - age_s
    for path in root.rglob("*"):
        if path.is_file() and path.stat().st_mtime < oldest:
            path.unlink(missing_ok=True)
