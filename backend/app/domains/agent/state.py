"""The state of a run and what its nodes share (tech.md §9.1, §9.2).

F-03 runs the minimal graph load_context → agent → postprocess: lite without tools. The slices
that add classify, route and tools add their fields here.
"""

import asyncio
from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import UUID

from langchain_core.messages import BaseMessage

from app.config import Settings
from app.contracts.api.chat import WarningOut
from app.contracts.common import ErrorOut, RunStatus
from app.contracts.llm import ModelFamily
from app.contracts.stream import RunFinishedEvent, RunStartedEvent, StreamEvent
from app.db.base import UnitOfWork
from app.domains.agent import repo
from app.domains.broker.service import BrokerService
from app.domains.settings.service import SettingsService
from app.gateways.llm.metering import Metering
from app.gateways.llm.port import LlmPort
from app.http.events import RunEventBus


@dataclass(frozen=True, slots=True)
class RunTicket:
    """The run the chat accepted: the question is the user message `message_id`."""

    run_id: UUID
    user_id: UUID
    thread_id: UUID
    message_id: UUID


class AgentState(TypedDict):
    run_id: UUID
    user_id: UUID
    thread_id: UUID
    messages: list[BaseMessage]  # the LLM context of this run
    step: int  # calls of the model so far
    warnings: list[WarningOut]
    final_text: str | None
    status: RunStatus
    error: ErrorOut | None
    tokens_billable: int
    tokens_precached: int


def initial_state(ticket: RunTicket) -> AgentState:
    return AgentState(
        run_id=ticket.run_id,
        user_id=ticket.user_id,
        thread_id=ticket.thread_id,
        messages=[],
        step=0,
        warnings=[],
        final_text=None,
        status="running",
        error=None,
        tokens_billable=0,
        tokens_precached=0,
    )


@dataclass(eq=False)
class RunContext:
    """The services of a run and the two facts its stream depends on: whether run.started and
    run.finished went out (§7: run.started once, run.finished always and last)."""

    ticket: RunTicket
    uow: UnitOfWork
    settings: Settings
    llm: LlmPort
    metering: Metering
    broker: BrokerService
    preferences: SettingsService
    events: RunEventBus
    cancelled: asyncio.Event  # POST .../cancel sets it
    deadline: float  # loop time when the model step gives up (AGENT_RUN_TIMEOUT_S)
    family: ModelFamily
    model_id: str
    started: bool = False
    finished: bool = False

    def emit(self, kind: type[StreamEvent], **fields: Any) -> None:
        self.events.publish(self.ticket.run_id, kind, **fields)

    async def start(self) -> None:
        """The first model call holds its slot: the run is running (§3.3, §7)."""
        async with self.uow as session:
            await repo.start_run(session, self.ticket.run_id, self.family, self.model_id)
        self.started = True
        self.emit(RunStartedEvent)

    def finish(self, status: RunStatus, message_id: UUID | None, error: ErrorOut | None) -> None:
        if not self.finished:
            self.finished = True
            self.emit(RunFinishedEvent, status=status, message_id=message_id, error=error)
