"""What the model reads (tech.md §9.1 load_context, §9.6, §9.12): the static prompt and the
summary of the thread, its last turns, then the context of the service and the question."""

import functools
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.runtime import Runtime

from app.contracts.api.broker import BrokerConnectionOut
from app.contracts.api.settings import AnswerStyle
from app.core import time
from app.db.schema.agent import Artifact
from app.domains.agent import repo
from app.domains.agent.postprocess import PLACEHOLDER
from app.domains.agent.state import AgentState, RunContext

PROMPTS = Path(__file__).parent / "prompts"
HEADER = re.compile(r"\A<!--.*?-->\s*", re.DOTALL)
MSK = "МСК"  # noqa: RUF001 - Moscow time in Russian
WEEKDAYS = ("понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье")
STYLES: dict[AnswerStyle, str] = {"concise": "кратко", "detailed": "подробно"}
KINDS = {"chart": "график", "table": "таблица", "image": "изображение"}
SUMMARY = "Сводка прошлой части разговора:"
# Questions without an answer drop out of the history: read more to fill its window.
READ_AHEAD = 3


@functools.cache
def prompt(name: str) -> str:
    """A prompt of prompts/ without the comment at its head (§9.6)."""
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    return HEADER.sub("", text).strip()


def system_prompt() -> str:
    return prompt("system")


@dataclass(frozen=True, slots=True)
class Said:
    """A message of the thread as the history takes it: the placeholders already named."""

    role: str
    status: str
    text: str


def history_text(content: str, labels: Mapping[str, str]) -> str:
    """An answer as the history tells it (§9.12): a placeholder line gives way to the name of
    its artifact, a placeholder without one drops out."""
    lines = []
    for line in content.split("\n"):
        match = PLACEHOLDER.match(line)
        if match is None:
            lines.append(line)
        elif found := labels.get(match.group(1)):
            lines.append(found)
    return "\n".join(lines).strip()


def label(artifact: Artifact) -> str:
    name = artifact.spec.get("alt" if artifact.kind == "image" else "title")
    return f"[{KINDS[artifact.kind]} «{name}»]"


def history_messages(said: Sequence[Said], limit: int) -> list[BaseMessage]:
    """The last turns of the thread, at most `limit` messages, a question first.

    A question left without an answer (failed, interrupted) drops out: the user and the model
    keep taking turns, the way chat models are trained to read them.
    """
    turns: list[BaseMessage] = []
    question: Said | None = None
    for message in said:
        if message.role == "user":
            question = message
            continue
        if question is not None and message.status != "failed" and message.text:
            turns += [HumanMessage(question.text), AIMessage(message.text)]
        question = None
    window = turns[-limit:] if limit > 0 else []
    return window[1:] if window and isinstance(window[0], AIMessage) else window


def context_block(now: datetime, broker: BrokerConnectionOut, answer_style: AnswerStyle) -> str:
    """The context of the service for this question (§9.12): Moscow time, the broker with the
    accounts by alias and name, the answer style."""
    moment = now.astimezone(time.MSK)
    return "\n".join(
        [
            "Служебный контекст:",
            f"- сейчас {moment:%d.%m.%Y, %H:%M} {MSK}, {WEEKDAYS[moment.weekday()]};",
            f"- {_broker(broker)};",
            f"- стиль ответа: {STYLES[answer_style]}.",
        ]
    )


# §9.4: without the broker the portfolio tools drop out and the model offers to connect it.
NO_BROKER = (
    "брокер не подключён: данных портфеля и счетов нет; на вопрос про портфель предложи "
    "подключить токен в Настройках"
)
INVALID_BROKER = (
    "токен брокера не действует: данных портфеля и счетов нет; на вопрос про портфель предложи "
    "подключить токен заново в Настройках"
)


def broker_ready(broker: BrokerConnectionOut) -> bool:
    """The broker gives data: connected, and its token works."""
    return broker.connected and broker.status == "active"


def _broker(broker: BrokerConnectionOut) -> str:
    if not broker.connected:
        return NO_BROKER
    if broker.status == "invalid":
        return INVALID_BROKER
    # The T-Invest id of an account never reaches the model (§3.5).
    accounts = [
        f"{account.alias} «{' '.join(account.name.split())}»"
        for account in broker.accounts
        if not account.is_hidden
    ]
    if not accounts:
        return "брокер подключён, все счета скрыты пользователем"
    return f"брокер подключён, счета: {', '.join(accounts)}"


def llm_messages(
    summary: str | None, history: Sequence[BaseMessage], block: str, question: str
) -> list[BaseMessage]:
    """§9.6: the static prompt, the summary, the history, the context, the question.

    The API documents a single system message at the head of the list: the summary joins it,
    and the context of the service leads the question. The prompt and the history stay a
    stable prefix that GigaChat caches.
    """
    parts = [system_prompt()]
    if summary:
        parts.append(f"{SUMMARY}\n{summary}")
    return [SystemMessage("\n\n".join(parts)), *history, HumanMessage(f"{block}\n\n{question}")]


async def load_context(state: AgentState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    ctx = runtime.context
    ticket = ctx.ticket
    preferences = await ctx.preferences.get(ticket.user_id)
    broker = await ctx.broker.connection(ticket.user_id)
    async with ctx.uow as session:
        asked = await repo.question(session, ticket.message_id)
        earlier = await repo.earlier(
            session, asked, READ_AHEAD * ctx.settings.AGENT_HISTORY_MESSAGES
        )
        artifacts = await repo.artifacts(session, [m.id for m in earlier if m.role == "assistant"])
        summary = await repo.summary(session, ticket.thread_id)
    labels: dict[UUID | None, dict[str, str]] = {}
    for artifact in artifacts:
        labels.setdefault(artifact.message_id, {})[artifact.local_id] = label(artifact)
    said = [
        Said(m.role, m.status, history_text(m.content, labels.get(m.id, {})))
        if m.role == "assistant"
        else Said(m.role, m.status, m.content)
        for m in earlier
    ]
    history = history_messages(said, ctx.settings.AGENT_HISTORY_MESSAGES)
    block = context_block(time.now(), broker, preferences.answer_style)
    previous = next((m.text for m in reversed(history) if isinstance(m, HumanMessage)), None)
    return {
        "messages": llm_messages(summary, history, block, asked.content),
        "question": asked.content,
        "previous": previous,
        "mode": preferences.model_mode,
        "broker_ready": broker_ready(broker),
    }
