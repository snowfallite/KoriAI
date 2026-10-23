"""The agent as the chat sees it (tech.md §9): it answers the question of a run and tells how a
saved answer splits into blocks (§9.9)."""

import asyncio
from typing import Self

import structlog
from starlette.datastructures import State

from app.config import Settings
from app.contracts.api.chat import MessageMeta
from app.db.base import UnitOfWork
from app.domains.agent import repo
from app.domains.agent.graph import GRAPH
from app.domains.agent.postprocess import Split, run_error, split_blocks
from app.domains.agent.state import RunContext, RunTicket, initial_state
from app.domains.broker.service import BrokerService
from app.domains.settings.service import SettingsService
from app.gateways.factory import Gateways
from app.gateways.llm.metering import Metering
from app.gateways.llm.port import LlmPort
from app.http.events import RunEventBus

__all__ = ["AgentService", "RunTicket", "Split", "run_error", "split_blocks"]

log = structlog.get_logger(__name__)


class AgentService:
    def __init__(
        self,
        uow: UnitOfWork,
        settings: Settings,
        events: RunEventBus,
        llm: LlmPort,
        metering: Metering,
        broker: BrokerService,
        preferences: SettingsService,
    ) -> None:
        self._uow = uow
        self._settings = settings
        self._events = events
        self._llm = llm
        self._metering = metering
        self._broker = broker
        self._preferences = preferences

    @classmethod
    def of(cls, state: State) -> Self:
        """The agent over the clients and the database the app state holds now."""
        gateways: Gateways = state.gateways
        return cls(
            UnitOfWork(state.engine),
            state.settings,
            state.events,
            gateways.llm,
            gateways.metering,
            BrokerService(UnitOfWork(state.engine), state.settings),
            SettingsService(UnitOfWork(state.engine)),
        )

    async def run(self, ticket: RunTicket, cancelled: asyncio.Event) -> None:
        """Answers the question of the run; its stream always ends with run.finished.

        A failure the graph does not handle still saves a failed answer. A shutdown cancels
        the task and leaves the run to the restart, which interrupts it (§3.4).
        """
        settings = self._settings
        ctx = RunContext(
            ticket=ticket,
            uow=self._uow,
            settings=settings,
            llm=self._llm,
            metering=self._metering,
            broker=self._broker,
            preferences=self._preferences,
            events=self._events,
            cancelled=cancelled,
            deadline=asyncio.get_running_loop().time() + settings.AGENT_RUN_TIMEOUT_S,
            # F-03 routes every question to lite without tools; F-05 brings the routing.
            family="lite",
            model_id=settings.LLM_MODELS["lite"],
        )
        with structlog.contextvars.bound_contextvars(run_id=str(ticket.run_id)):
            try:
                await GRAPH.ainvoke(initial_state(ticket), context=ctx)
            except Exception:
                log.exception("agent_run_crashed")
                await self._fail(ctx)
            finally:
                ctx.finish("interrupted", None, None)

    async def _fail(self, ctx: RunContext) -> None:
        error = run_error("internal", ctx.ticket.run_id)
        message_id = None
        try:
            async with self._uow as session:
                message_id = await repo.save_answer(
                    session,
                    run_id=ctx.ticket.run_id,
                    thread_id=ctx.ticket.thread_id,
                    user_id=ctx.ticket.user_id,
                    content="",
                    status="failed",
                    meta=MessageMeta().model_dump(mode="json"),
                    run_status="failed",
                    error_code=error.code,
                    steps=0,
                    tokens_billable=0,
                    tokens_precached=0,
                )
        except Exception:  # the next read of the thread interrupts the run instead
            log.exception("agent_run_not_saved")
        ctx.finish("failed", message_id, error)
