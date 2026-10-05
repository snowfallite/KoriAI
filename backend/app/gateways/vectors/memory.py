"""Vector store in memory (tech.md §8.6): the fake of Qdrant, VECTORS_MODE=memory.

Same filters as Qdrant; dense cosine and the overlap of sparse terms each rank the points,
reciprocal rank fusion merges the two lists as the Query API does.
"""

import math
from typing import Any
from uuid import UUID

from pydantic import InstanceOf

from app.contracts.vectors import ChunkHit, ChunkPoint, ChunkQuery
from app.core.errors import ContractViolation
from app.gateways.fakes import Fake, port_method

RRF_K = 60


def _cosine(a: list[float], b: list[float]) -> float:
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return sum(x * y for x, y in zip(a, b, strict=True)) / norm if norm else 0.0


def _matches(point: ChunkPoint, q: ChunkQuery) -> bool:
    payload = point.payload
    return (
        (q.issuer_id is None or payload.issuer_id == q.issuer_id)
        and (q.kinds is None or payload.kind in q.kinds)
        and (q.years is None or payload.period_year in q.years)
    )


def _nothing(arguments: dict[str, Any]) -> None:
    return None


class MemoryVectorStore(Fake):
    port = "vectors"
    unavailable = "internal"
    rate_limited = "internal"

    def __init__(self, dim: int, **options: Any) -> None:
        super().__init__(**options)
        self.dim = dim
        self.points: dict[UUID, ChunkPoint] = {}

    def _check(self, dense: list[float]) -> None:
        if len(dense) != self.dim:
            raise ContractViolation(
                f"a dense vector of {len(dense)} values, the store has {self.dim}"
            )

    @port_method(empty=_nothing)
    async def ensure_collection(self) -> None:
        return None

    @port_method(empty=_nothing)
    async def upsert(self, points: list[InstanceOf[ChunkPoint]]) -> None:
        for point in points:
            self._check(point.dense)
        self.points.update((point.id, point) for point in points)

    @port_method(empty=_nothing)
    async def delete_document(self, document_id: UUID) -> None:
        self.points = {k: p for k, p in self.points.items() if p.payload.document_id != document_id}

    @port_method(empty=lambda a: [])
    async def search(self, q: InstanceOf[ChunkQuery]) -> list[ChunkHit]:
        self._check(q.dense)
        candidates = [p for p in self.points.values() if _matches(p, q)]
        terms = set(q.sparse.indices)
        by_dense = sorted(candidates, key=lambda p: -_cosine(q.dense, p.dense))
        by_terms = sorted(
            (p for p in candidates if terms & set(p.sparse.indices)),
            key=lambda p: -len(terms & set(p.sparse.indices)),
        )
        scores: dict[UUID, float] = {}
        for ranking in (by_dense, by_terms):
            for rank, point in enumerate(ranking, start=1):
                scores[point.id] = scores.get(point.id, 0.0) + 1 / (RRF_K + rank)
        best = sorted(scores, key=lambda point_id: -scores[point_id])[: q.top_k]
        return [ChunkHit(payload=self.points[i].payload, score=scores[i]) for i in best]
