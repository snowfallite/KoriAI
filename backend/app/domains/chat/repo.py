"""Queries of threads, messages and runs (tech.md §5.3, §5.5)."""

from collections.abc import Collection, Sequence
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.schema.agent import AgentRun, Artifact, Source
from app.db.schema.chat import Message, Thread

ACTIVE = ("queued", "running")


async def thread(session: AsyncSession, user_id: UUID, thread_id: UUID) -> Thread | None:
    query = select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id)
    return await session.scalar(query)


async def add_thread(session: AsyncSession, user_id: UUID) -> UUID:
    found: UUID = (
        await session.execute(insert(Thread).values(user_id=user_id).returning(Thread.id))
    ).scalar_one()
    return found


async def add_question(session: AsyncSession, thread_id: UUID, user_id: UUID, text: str) -> UUID:
    """The question of the user joins the thread."""
    added = (
        insert(Message)
        .values(thread_id=thread_id, user_id=user_id, role="user", content=text)
        .returning(Message.id, Message.created_at)
    )
    message_id, created_at = (await session.execute(added)).one()
    await session.execute(
        update(Thread)
        .where(Thread.id == thread_id)
        .values(
            message_count=Thread.message_count + 1,
            last_message_at=created_at,
            updated_at=func.now(),
        )
    )
    found: UUID = message_id
    return found


async def add_run(session: AsyncSession, thread_id: UUID, user_id: UUID, message_id: UUID) -> UUID:
    """A queued run; agent_runs_one_active_idx refuses a second active run of the user."""
    added = (
        insert(AgentRun)
        .values(thread_id=thread_id, user_id=user_id, user_message_id=message_id)
        .returning(AgentRun.id)
    )
    found: UUID = (await session.execute(added)).scalar_one()
    return found


async def messages(session: AsyncSession, thread_id: UUID) -> Sequence[Message]:
    query = (
        select(Message)
        .where(Message.thread_id == thread_id)
        .order_by(Message.created_at, Message.id)
    )
    return (await session.scalars(query)).all()


async def artifacts(session: AsyncSession, message_ids: Collection[UUID]) -> Sequence[Artifact]:
    """In creation order: the answer shows the unplaced ones in it (§9.9)."""
    if not message_ids:
        return []
    query = select(Artifact).where(Artifact.message_id.in_(message_ids))
    return (await session.scalars(query.order_by(Artifact.created_at, Artifact.id))).all()


async def sources(session: AsyncSession, message_ids: Collection[UUID]) -> Sequence[Source]:
    if not message_ids:
        return []
    query = select(Source).where(Source.message_id.in_(message_ids))
    return (await session.scalars(query.order_by(Source.created_at, Source.id))).all()


async def active_run(session: AsyncSession, thread_id: UUID) -> AgentRun | None:
    query = select(AgentRun).where(AgentRun.thread_id == thread_id, AgentRun.status.in_(ACTIVE))
    return await session.scalar(query)


async def run(session: AsyncSession, user_id: UUID, run_id: UUID) -> AgentRun | None:
    query = select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id)
    return await session.scalar(query.execution_options(populate_existing=True))


async def request_cancel(session: AsyncSession, run_id: UUID) -> None:
    await session.execute(
        update(AgentRun).where(AgentRun.id == run_id).values(cancel_requested=True)
    )


async def interrupt(
    session: AsyncSession,
    *,
    live: Collection[UUID],
    user_id: UUID | None = None,
    thread_id: UUID | None = None,
    run_id: UUID | None = None,
) -> int:
    """Interrupts the active runs no task of this process owns (§3.4, AD-02); the filters narrow
    them to a user, a thread or one run. Gives the number of runs interrupted."""
    query = update(AgentRun).where(AgentRun.status.in_(ACTIVE))
    if live:
        query = query.where(AgentRun.id.not_in(live))
    if user_id is not None:
        query = query.where(AgentRun.user_id == user_id)
    if thread_id is not None:
        query = query.where(AgentRun.thread_id == thread_id)
    if run_id is not None:
        query = query.where(AgentRun.id == run_id)
    done = await session.execute(
        query.values(status="interrupted", finished_at=func.now())
        .returning(AgentRun.id)
        .execution_options(synchronize_session=False)
    )
    return len(done.all())
