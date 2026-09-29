"""Locks of queue payloads per the table of tech.md §10.2."""

from datetime import date
from uuid import UUID

import pytest

from app.contracts.jobs import (
    CandlesPayload,
    DemoEchoPayload,
    ExtractIfrsPayload,
    FetchDocumentPayload,
    IndexDocumentPayload,
    ParseRasPayload,
    Payload,
    SnapshotPayload,
    SyncIssuerPayload,
    ThreadSummarizePayload,
    ThreadTitlePayload,
)

A = UUID("0199a000-0000-7000-8000-000000000001")
B = UUID("0199a000-0000-7000-8000-000000000002")
DAY = date(2026, 9, 29)


@pytest.mark.parametrize(
    ("payload", "queueing_lock", "lock"),
    [
        (DemoEchoPayload(key="k1", value="v"), "demo:k1", None),
        (ThreadTitlePayload(thread_id=A), f"title:{A}", None),
        (ThreadSummarizePayload(thread_id=A, upto_message_id=B), f"summ:{A}", f"thread:{A}"),
        (
            CandlesPayload(instrument_uid=A, from_day=DAY, to_day=DAY),
            f"candles:{A}",
            f"candles:{A}",
        ),
        (SnapshotPayload(user_id=A, day=DAY), f"snap:{A}:2026-09-29", f"user:{A}"),
        (SyncIssuerPayload(issuer_id=A, sections=["ras"]), f"dsync:{A}", f"issuer:{A}"),
        (FetchDocumentPayload(document_id=A), f"dfetch:{A}", f"doc:{A}"),
        (ParseRasPayload(document_id=A), f"dras:{A}", f"doc:{A}"),
        (ExtractIfrsPayload(document_id=A), f"difrs:{A}", f"doc:{A}"),
        (IndexDocumentPayload(document_id=A), f"rag:{A}", f"doc:{A}"),
    ],
)
def test_payload_locks(payload: Payload, queueing_lock: str, lock: str | None) -> None:
    assert (payload.queueing_lock(), payload.lock()) == (queueing_lock, lock)
