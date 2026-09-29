"""Payloads of queue tasks (tech.md §10)."""

from datetime import date
from uuid import UUID

from app.contracts.common import Contract, FileSection


class Payload(Contract):
    """defer(payload) takes the procrastinate locks from these methods (tech.md §10.1)."""

    def queueing_lock(self) -> str | None:
        return None

    def lock(self) -> str | None:
        return None


class DemoEchoPayload(Payload):
    key: str
    value: str

    def queueing_lock(self) -> str | None:
        return f"demo:{self.key}"


class ThreadTitlePayload(Payload):
    thread_id: UUID

    def queueing_lock(self) -> str | None:
        return f"title:{self.thread_id}"


class ThreadSummarizePayload(Payload):
    thread_id: UUID
    upto_message_id: UUID

    def queueing_lock(self) -> str | None:
        return f"summ:{self.thread_id}"

    def lock(self) -> str | None:
        return f"thread:{self.thread_id}"


class CandlesPayload(Payload):
    instrument_uid: UUID
    from_day: date
    to_day: date

    def queueing_lock(self) -> str | None:
        return f"candles:{self.instrument_uid}"

    def lock(self) -> str | None:
        return f"candles:{self.instrument_uid}"


class SnapshotPayload(Payload):
    user_id: UUID
    day: date

    def queueing_lock(self) -> str | None:
        return f"snap:{self.user_id}:{self.day}"

    def lock(self) -> str | None:
        return f"user:{self.user_id}"


class SyncIssuerPayload(Payload):
    issuer_id: UUID
    sections: list[FileSection]

    def queueing_lock(self) -> str | None:
        return f"dsync:{self.issuer_id}"

    def lock(self) -> str | None:
        return f"issuer:{self.issuer_id}"


class DocumentPayload(Payload):
    """Tasks of one document wait in the queue together and run one at a time (tech.md §10.1)."""

    document_id: UUID

    def lock(self) -> str | None:
        return f"doc:{self.document_id}"


class FetchDocumentPayload(DocumentPayload):
    def queueing_lock(self) -> str | None:
        return f"dfetch:{self.document_id}"


class ParseRasPayload(DocumentPayload):
    def queueing_lock(self) -> str | None:
        return f"dras:{self.document_id}"


class ExtractIfrsPayload(DocumentPayload):
    def queueing_lock(self) -> str | None:
        return f"difrs:{self.document_id}"


class IndexDocumentPayload(DocumentPayload):
    def queueing_lock(self) -> str | None:
        return f"rag:{self.document_id}"
