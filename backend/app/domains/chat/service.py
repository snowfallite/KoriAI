"""Threads, questions and runs of the chat (tech.md §3.4, §6.5): a question becomes a run that a
task of this process answers while the client follows its stream."""

import asyncio
import functools
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.contracts.api.chat import MessageAcceptedOut, MessageIn, RunOut, ThreadDetailOut
from app.core.errors import AppError
from app.db.base import UnitOfWork
from app.domains.agent.service import AgentService, RunTicket
from app.domains.chat import mapping, repo
from app.http.events import RunEventBus

log = structlog.get_logger(__name__)

NO_THREAD = "Чат не найден"
NO_RUN = "Ответ не найден"
RUN_ACTIVE = "Ответ на прошлый вопрос ещё готовится: дождитесь или остановите"
RUN_OVER = "Ответ уже готов"
ACTIVE_INDEX = "agent_runs_one_active_idx"
RECOVER_TIMEOUT_S = 10.0
SHUTDOWN_GRACE_S = 5.0

type Work = Callable[[asyncio.Event], Coroutine[Any, Any, None]]


@dataclass(eq=False, slots=True)
class _Live:
    task: asyncio.Task[None]
    cancelled: asyncio.Event


class LiveRuns:
    """The run tasks of this process (AD-02). A run it does not know has no task left: its
    process stopped, or its task died before it could finish the row."""

    def __init__(self) -> None:
        self._live: dict[UUID, _Live] = {}
        # Claimed before their rows commit, so nobody takes them for orphans meanwhile.
        self._claimed: set[UUID] = set()
        self._cancel_first: set[UUID] = set()

    def claim(self, run_id: UUID) -> None:
        self._claimed.add(run_id)

    def unclaim(self, run_id: UUID) -> None:
        self._claimed.discard(run_id)
        self._cancel_first.discard(run_id)

    def ids(self) -> frozenset[UUID]:
        return frozenset(self._live) | self._claimed

    def start(self, run_id: UUID, work: Work) -> None:
        cancelled = asyncio.Event()
        if run_id in self._cancel_first:
            cancelled.set()
        self.unclaim(run_id)
        task = asyncio.create_task(work(cancelled), name=f"run:{run_id}")
        self._live[run_id] = _Live(task, cancelled)
        task.add_done_callback(functools.partial(self._ended, run_id))

    def cancel(self, run_id: UUID) -> None:
        live = self._live.get(run_id)
        if live is not None:
            live.cancelled.set()
        elif run_id in self._claimed:
            self._cancel_first.add(run_id)

    async def join(self) -> None:
        """Waits until no run of the process is going."""
        while tasks := [live.task for live in self._live.values() if not live.task.done()]:
            await asyncio.wait(tasks)

    async def aclose(self) -> None:
        """Stops the runs of a process that shuts down: the restart interrupts them (§3.4)."""
        tasks = [live.task for live in self._live.values()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.wait(tasks, timeout=SHUTDOWN_GRACE_S)

    def _ended(self, run_id: UUID, task: asyncio.Task[None]) -> None:
        self._live.pop(run_id, None)
        if not task.cancelled() and (error := task.exception()) is not None:
            log.error("chat_run_task_failed", run_id=str(run_id), exc_info=error)


class _ActiveRun(Exception):
    """The user has an active run already (agent_runs_one_active_idx)."""


def _active_run_conflict(error: IntegrityError) -> bool:
    diag = getattr(error.orig, "diag", None)
    return getattr(diag, "constraint_name", None) == ACTIVE_INDEX


class ChatService:
    def __init__(
        self, uow: UnitOfWork, events: RunEventBus, runs: LiveRuns, agent: AgentService
    ) -> None:
        self._uow = uow
        self._events = events
        self._runs = runs
        self._agent = agent

    async def send(self, user_id: UUID, role: str, body: MessageIn) -> MessageAcceptedOut:
        """Saves the question with a queued run and starts the task that answers it (§3.4);
        a question over the budget gets no run (§9.5)."""
        text = body.text.strip()
        if not text:
            raise AppError("validation_error", "Напишите вопрос")
        await self._agent.admit(user_id, role)
        try:
            accepted = await self._accept(user_id, body.thread_id, text)
        except _ActiveRun:
            # The active run may have lost its task: then it no longer blocks the user.
            async with self._uow as session:
                freed = await repo.interrupt(session, live=self._runs.ids(), user_id=user_id)
            if not freed:
                raise AppError("run_active", RUN_ACTIVE) from None
            log.warning("chat_orphan_runs_interrupted", runs=freed)
            try:
                accepted = await self._accept(user_id, body.thread_id, text)
            except _ActiveRun:
                raise AppError("run_active", RUN_ACTIVE) from None
        self._events.open(accepted.run_id, user_id)
        ticket = RunTicket(accepted.run_id, user_id, accepted.thread_id, accepted.message_id)
        self._runs.start(accepted.run_id, functools.partial(self._agent.run, ticket))
        log.info("chat_question_accepted", question_length=len(text))
        return accepted

    async def _accept(self, user_id: UUID, thread_id: UUID | None, text: str) -> MessageAcceptedOut:
        claimed: UUID | None = None
        try:
            async with self._uow as session:
                if thread_id is None:
                    thread_id = await repo.add_thread(session, user_id)
                elif await repo.thread(session, user_id, thread_id) is None:
                    raise AppError("not_found", NO_THREAD)
                message_id = await repo.add_question(session, thread_id, user_id, text)
                run_id = await repo.add_run(session, thread_id, user_id, message_id)
                self._runs.claim(run_id)
                claimed = run_id
        except BaseException as error:
            if claimed is not None:
                self._runs.unclaim(claimed)
            if isinstance(error, IntegrityError) and _active_run_conflict(error):
                raise _ActiveRun from None
            raise
        return MessageAcceptedOut(thread_id=thread_id, message_id=message_id, run_id=run_id)

    async def thread(self, user_id: UUID, thread_id: UUID) -> ThreadDetailOut:
        async with self._uow as session:
            found = await repo.thread(session, user_id, thread_id)
            if found is None:
                raise AppError("not_found", NO_THREAD)
            # A run without its task would look active forever.
            await repo.interrupt(session, live=self._runs.ids(), thread_id=thread_id)
            messages = await repo.messages(session, thread_id)
            ids = [message.id for message in messages]
            artifacts = await repo.artifacts(session, ids)
            sources = await repo.sources(session, ids)
            active = await repo.active_run(session, thread_id)
        return mapping.thread_detail(found, messages, artifacts, sources, active)

    async def run(self, user_id: UUID, run_id: UUID) -> RunOut:
        async with self._uow as session:
            found = await repo.run(session, user_id, run_id)
        if found is None:
            raise AppError("not_found", NO_RUN)
        return mapping.run_out(found)

    async def cancel(self, user_id: UUID, run_id: UUID) -> RunOut:
        """Asks the run to stop; it saves what it has written as a partial answer (§3.4)."""
        async with self._uow as session:
            found = await repo.run(session, user_id, run_id)
            if found is None:
                raise AppError("not_found", NO_RUN)
            if found.status not in repo.ACTIVE:
                raise AppError("conflict", RUN_OVER)
            if run_id in self._runs.ids():
                await repo.request_cancel(session, run_id)
            else:  # no task of this process answers it any more
                await repo.interrupt(session, live=(), run_id=run_id)
            changed = await repo.run(session, user_id, run_id)
        self._runs.cancel(run_id)
        return mapping.run_out(changed or found)


async def recover(engine: AsyncEngine) -> None:
    """At the start of the process no run has a task: the ones an earlier process left turn
    interrupted (§3.4). The API also starts without its database (S1-07), so a failure only
    logs: the next read of a thread interrupts its run."""
    try:
        async with asyncio.timeout(RECOVER_TIMEOUT_S), UnitOfWork(engine) as session:
            count = await repo.interrupt(session, live=())
    except Exception:
        log.warning("chat_runs_not_recovered", exc_info=True)
        return
    if count:
        log.info("chat_runs_interrupted", runs=count)
