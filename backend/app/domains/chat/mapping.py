"""Rows of threads, messages and runs as the chat API sends them (tech.md §6.5, §6.6, §9.9)."""

from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from app.contracts.api.chat import (
    MarkdownBlock,
    MessageBlock,
    MessageMeta,
    MessageOut,
    RunOut,
    ThreadDetailOut,
    ThreadOut,
)
from app.contracts.artifacts import ArtifactOut, ChartSpec, ImageSpec, SourceRef, TableSpec
from app.db.schema.agent import AgentRun, Artifact, Source
from app.db.schema.chat import Message, Thread
from app.domains.agent.service import run_error, split_blocks

SPECS: dict[str, type[ChartSpec] | type[TableSpec] | type[ImageSpec]] = {
    "chart": ChartSpec,
    "table": TableSpec,
    "image": ImageSpec,
}


def thread_out(thread: Thread) -> ThreadOut:
    return ThreadOut.model_validate(
        {
            "id": thread.id,
            "title": thread.title,
            "title_source": thread.title_source,
            "message_count": thread.message_count,
            "last_message_at": thread.last_message_at,
            "archived": thread.archived_at is not None,
            "created_at": thread.created_at,
            "snippet": None,  # a search of F-04 fills it
        }
    )


def run_out(run: AgentRun) -> RunOut:
    error = run_error(run.error_code, run.id) if run.error_code else None
    return RunOut.model_validate(
        {
            "id": run.id,
            "thread_id": run.thread_id,
            "status": run.status,
            "model_family": run.model_family,
            "model_id": run.model_id,
            "steps": run.steps,
            "error": error,
            "created_at": run.created_at,
            "finished_at": run.finished_at,
        }
    )


def artifact_out(row: Artifact) -> ArtifactOut:
    # Pictures go through the media proxy (§6.4, AD-09).
    image_url = f"/api/media/artifacts/{row.id}" if row.kind == "image" else None
    return ArtifactOut.model_validate(
        {
            "id": row.id,
            "local_id": row.local_id,
            "kind": row.kind,
            "spec": SPECS[row.kind].model_validate(row.spec),
            "image_url": image_url,
            "created_at": row.created_at,
        }
    )


def source_out(row: Source) -> SourceRef:
    return SourceRef.model_validate(row, from_attributes=True)


def message_out(row: Message, artifacts: list[ArtifactOut], sources: list[SourceRef]) -> MessageOut:
    blocks: list[MessageBlock]
    if row.role == "user":
        # The question is the words of the user: placeholders mean nothing in it.
        blocks = [MarkdownBlock(text=row.content)]
    else:
        known = {artifact.local_id: artifact.id for artifact in artifacts}
        blocks = split_blocks(row.content, known).blocks
    return MessageOut.model_validate(
        {
            "id": row.id,
            "role": row.role,
            "status": row.status,
            "content": row.content,
            "blocks": blocks,
            "artifacts": artifacts,
            "sources": sources,
            "meta": MessageMeta.model_validate(row.meta),
            "created_at": row.created_at,
        }
    )


def thread_detail(
    thread: Thread,
    messages: Sequence[Message],
    artifacts: Sequence[Artifact],
    sources: Sequence[Source],
    active: AgentRun | None,
) -> ThreadDetailOut:
    artifacts_of: defaultdict[UUID | None, list[ArtifactOut]] = defaultdict(list)
    for artifact in artifacts:
        artifacts_of[artifact.message_id].append(artifact_out(artifact))
    sources_of: defaultdict[UUID | None, list[SourceRef]] = defaultdict(list)
    for source in sources:
        sources_of[source.message_id].append(source_out(source))
    return ThreadDetailOut(
        thread=thread_out(thread),
        messages=[message_out(m, artifacts_of[m.id], sources_of[m.id]) for m in messages],
        active_run=run_out(active) if active is not None else None,
    )
