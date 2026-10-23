"""The end of a run (tech.md §9.1, §9.9): the blocks of the answer, its warnings, the saved
message and run.finished."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from langgraph.runtime import Runtime

from app.contracts.api.chat import (
    ArtifactBlock,
    MarkdownBlock,
    MessageBlock,
    MessageMeta,
    WarningOut,
)
from app.contracts.common import ErrorOut, MessageStatus, RunStatus
from app.domains.agent import repo
from app.domains.agent.state import AgentState, RunContext

log = structlog.get_logger(__name__)

# A line with nothing but an artifact placeholder (§9.9).
PLACEHOLDER = re.compile(r"^\s*\[\[([cti][0-9]+)\]\]\s*$")
MESSAGE_STATUS: dict[RunStatus, MessageStatus] = {
    "done": "complete",
    "cancelled": "partial",
    "failed": "failed",
}
UNKNOWN_PLACEHOLDER = "Ответ ссылался на график или таблицу, которых нет"
# What a failed run tells the reader, by ErrorCode; RunOut repeats it from agent_runs.error_code.
RUN_ERRORS: dict[str, str] = {
    "llm_busy": "Модель не ответила, попробуйте ещё раз",
    "llm_quota_exhausted": "Квота модели исчерпана",
}
RUN_ERROR_FALLBACK = "Ответ не получен, попробуйте ещё раз"


@dataclass(frozen=True, slots=True)
class Split:
    blocks: list[MessageBlock]
    unknown: list[str]  # placeholders without an artifact of the run, each once


def split_blocks(text: str, known: Mapping[str, UUID]) -> Split:
    """The answer as markdown and artifact blocks in the order of the text (§9.9).

    `known` maps the local ids of the artifacts of the run to their ids in creation order. Every
    placeholder line ends a markdown block; an unknown or repeated one shows nothing, and the
    artifacts the text leaves out follow it in creation order.
    """
    blocks: list[MessageBlock] = []
    unknown: list[str] = []
    shown: set[str] = set()
    lines: list[str] = []

    def close_markdown() -> None:
        part = "\n".join(lines).strip()
        lines.clear()
        if part:
            blocks.append(MarkdownBlock(text=part))

    # Only \n: the SPA splits the same way (lib/utils/blocks.ts).
    for line in text.split("\n"):
        match = PLACEHOLDER.match(line)
        if match is None:
            lines.append(line)
            continue
        close_markdown()
        local_id = match.group(1)
        if local_id not in known:
            if local_id not in unknown:
                unknown.append(local_id)
        elif local_id not in shown:
            shown.add(local_id)
            blocks.append(ArtifactBlock(artifact_id=known[local_id]))
    close_markdown()
    rest = [artifact_id for local_id, artifact_id in known.items() if local_id not in shown]
    blocks.extend(ArtifactBlock(artifact_id=artifact_id) for artifact_id in rest)
    return Split(blocks, unknown)


def run_error(code: str, run_id: UUID) -> ErrorOut:
    """The error of a failed run, also from agent_runs.error_code; its request code is the run
    id, which every log line of the run carries."""
    message = RUN_ERRORS.get(code, RUN_ERROR_FALLBACK)
    return ErrorOut.model_validate({"code": code, "message": message, "request_id": str(run_id)})


async def postprocess(state: AgentState, runtime: Runtime[RunContext]) -> dict[str, Any]:
    """Saves the answer with its warnings and ends the stream with run.finished."""
    ctx = runtime.context
    status = state["status"]
    text = state["final_text"] or ""
    # F-03 runs no tools, so the run has no artifacts yet.
    warnings = list(state["warnings"])
    if split_blocks(text, {}).unknown:
        warnings.append(WarningOut(code="unknown_placeholder", message=UNKNOWN_PLACEHOLDER))
    # A run cancelled before its first call asked no model.
    meta = MessageMeta(
        model_family=ctx.family if ctx.started else None,
        model_id=ctx.model_id if ctx.started else None,
        warnings=warnings,
        tokens_billable=state["tokens_billable"] if ctx.started else None,
    )
    error = state["error"]
    async with ctx.uow as session:
        message_id = await repo.save_answer(
            session,
            run_id=ctx.ticket.run_id,
            thread_id=ctx.ticket.thread_id,
            user_id=ctx.ticket.user_id,
            content=text,
            status=MESSAGE_STATUS[status],
            meta=meta.model_dump(mode="json"),
            run_status=status,
            error_code=error.code if error else None,
            steps=state["step"],
            tokens_billable=state["tokens_billable"],
            tokens_precached=state["tokens_precached"],
        )
    log.info(
        "agent_run_finished",
        status=status,
        steps=state["step"],
        answer_length=len(text),
        tokens_billable=state["tokens_billable"],
    )
    ctx.finish(status, message_id, error)
    return {}
