"""DTOs of the embeddings and vector store ports (tech.md §8.6)."""

from uuid import UUID

from pydantic import Field

from app.contracts.common import Contract, DocKind, Standard


class SparseVec(Contract):
    indices: list[int]
    values: list[float]


class ChunkPayload(Contract):
    document_id: UUID
    issuer_id: UUID
    kind: DocKind
    standard: Standard
    period_year: int | None
    period_label: str
    page: int
    chunk_idx: int
    text: str


class ChunkPoint(Contract):
    id: UUID  # uuid5(document_id, chunk_idx)
    dense: list[float]
    sparse: SparseVec
    payload: ChunkPayload


class ChunkQuery(Contract):
    text: str
    dense: list[float]
    sparse: SparseVec
    issuer_id: UUID | None
    kinds: list[DocKind] | None
    years: list[int] | None
    top_k: int = Field(ge=1, le=20)


class ChunkHit(Contract):
    payload: ChunkPayload
    score: float
