"""Queries of a run (tech.md §5.3, §5.5): the conversation it reads and the answer it leaves."""

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import func, insert, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.agent import RoutingDecision, TaskProfile
from app.contracts.common import ErrorCode, MessageStatus, RunStatus
from app.db.schema.agent import AgentRun, Artifact, Source
from app.db.schema.broker import Instrument
from app.db.schema.chat import Message, Thread


async def start_run(session: AsyncSession, run_id: UUID) -> None:
    await session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id, AgentRun.status == "queued")
        .values(status="running", started_at=func.now())
    )


async def route_run(
    session: AsyncSession,
    run_id: UUID,
    profile: TaskProfile,
    routing: RoutingDecision | None,
) -> None:
    """The profile and the route of the run (§5.5); no route: no family was allowed."""
    await session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id)
        .values(
            profile=profile.model_dump(mode="json"),
            routing=routing.model_dump(mode="json") if routing else None,
            model_family=routing.family if routing else None,
            model_id=routing.model_id if routing else None,
        )
    )


async def instrument_names(session: AsyncSession) -> Sequence[tuple[str, str]]:
    """The (ticker, name) pairs the rules of the classifier check mentions against (§9.3)."""
    rows = await session.execute(select(Instrument.ticker, Instrument.name))
    return [(ticker, name) for ticker, name in rows]


async def summary(session: AsyncSession, thread_id: UUID) -> str | None:
    return await session.scalar(select(Thread.summary).where(Thread.id == thread_id))


async def question(session: AsyncSession, message_id: UUID) -> Message:
    found = await session.get(Message, message_id)
    if found is None:
        raise LookupError(f"message {message_id} is gone")
    return found


async def earlier(session: AsyncSession, asked: Message, limit: int) -> Sequence[Message]:
    """The messages of the thread before the question, oldest first."""
    query = (
        select(Message)
        .where(
            Message.thread_id == asked.thread_id,
            tuple_(Message.created_at, Message.id) < tuple_(asked.created_at, asked.id),
        )
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(limit)
    )
    return list(reversed((await session.scalars(query)).all()))


async def artifacts(session: AsyncSession, message_ids: Sequence[UUID]) -> Sequence[Artifact]:
    if not message_ids:
        return []
    query = select(Artifact).where(Artifact.message_id.in_(message_ids))
    return (await session.scalars(query.order_by(Artifact.created_at, Artifact.id))).all()


async def save_answer(
    session: AsyncSession,
    *,
    run_id: UUID,
    thread_id: UUID,
    user_id: UUID,
    content: str,
    status: MessageStatus,
    meta: dict[str, Any],
    run_status: RunStatus,
    error_code: ErrorCode | None,
    steps: int,
    tokens_billable: int,
    tokens_precached: int,
) -> UUID:
    """The answer joins the thread; the run ends and hands its artifacts and sources to it."""
    message = (
        insert(Message)
        .values(
            thread_id=thread_id,
            user_id=user_id,
            role="assistant",
            content=content,
            status=status,
            run_id=run_id,
            meta=meta,
        )
        .returning(Message.id, Message.created_at)
    )
    message_id, created_at = (await session.execute(message)).one()
    await session.execute(
        update(AgentRun)
        .where(AgentRun.id == run_id)
        .values(
            status=run_status,
            assistant_message_id=message_id,
            error_code=error_code,
            steps=steps,
            tokens_billable=tokens_billable,
            tokens_precached=tokens_precached,
            finished_at=func.now(),
        )
    )
    await session.execute(
        update(Thread)
        .where(Thread.id == thread_id)
        .values(
            message_count=Thread.message_count + 1,
            last_message_at=created_at,
            updated_at=func.now(),
        )
    )
    for model in (Artifact, Source):
        await session.execute(
            update(model).where(model.run_id == run_id).values(message_id=message_id)
        )
    return message_id
