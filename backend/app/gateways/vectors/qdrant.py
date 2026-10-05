"""Qdrant behind VectorStorePort (tech.md §8.6): named vectors dense and bm25, hybrid search
of the Query API with reciprocal rank fusion."""

from uuid import UUID

import httpx
from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from app.config import Settings
from app.contracts.vectors import ChunkHit, ChunkPayload, ChunkPoint, ChunkQuery
from app.core.errors import GatewayError, PermanentGatewayError, TransientGatewayError
from app.gateways.retry import with_retries

PAYLOAD_INDEXES = {
    "issuer_id": models.PayloadSchemaType.KEYWORD,
    "document_id": models.PayloadSchemaType.KEYWORD,
    "kind": models.PayloadSchemaType.KEYWORD,
    "period_year": models.PayloadSchemaType.INTEGER,
}
PREFETCH = 4  # candidates per list for each place of the answer


def _error(exc: Exception) -> GatewayError:
    if isinstance(exc, UnexpectedResponse) and (exc.status_code or 500) < 500:
        return PermanentGatewayError("internal")
    return TransientGatewayError("internal")


def _filter(q: ChunkQuery) -> models.Filter | None:
    must: list[models.Condition] = []
    if q.issuer_id is not None:
        must.append(
            models.FieldCondition(key="issuer_id", match=models.MatchValue(value=str(q.issuer_id)))
        )
    if q.kinds is not None:
        must.append(models.FieldCondition(key="kind", match=models.MatchAny(any=list(q.kinds))))
    if q.years is not None:
        must.append(models.FieldCondition(key="period_year", match=models.MatchAny(any=q.years)))
    return models.Filter(must=must) if must else None


class QdrantVectorStore:
    def __init__(self, settings: Settings, dim: int) -> None:
        # No version probe on start: it blocks, and /api/health/ready watches Qdrant anyway.
        self._client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY.get_secret_value() or None,
            check_compatibility=False,
        )
        self._name = settings.QDRANT_COLLECTION
        self._dim = dim

    async def aclose(self) -> None:
        await self._client.close()

    async def ensure_collection(self) -> None:
        try:
            if not await self._client.collection_exists(self._name):
                await self._client.create_collection(
                    self._name,
                    vectors_config={
                        "dense": models.VectorParams(
                            size=self._dim, distance=models.Distance.COSINE
                        )
                    },
                    sparse_vectors_config={
                        "bm25": models.SparseVectorParams(modifier=models.Modifier.IDF)
                    },
                )
            for field, schema in PAYLOAD_INDEXES.items():  # an existing index stays as is
                await self._client.create_payload_index(self._name, field, field_schema=schema)
        except (UnexpectedResponse, ResponseHandlingException, httpx.TransportError) as exc:
            raise _error(exc) from exc

    async def upsert(self, points: list[ChunkPoint]) -> None:
        structs = [
            models.PointStruct(
                id=str(point.id),
                vector={
                    "dense": point.dense,
                    "bm25": models.SparseVector(
                        indices=point.sparse.indices, values=point.sparse.values
                    ),
                },
                payload=point.payload.model_dump(mode="json"),
            )
            for point in points
        ]
        try:
            await self._client.upsert(self._name, points=structs, wait=True)
        except (UnexpectedResponse, ResponseHandlingException, httpx.TransportError) as exc:
            raise _error(exc) from exc

    async def delete_document(self, document_id: UUID) -> None:
        selector = models.FilterSelector(
            filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="document_id", match=models.MatchValue(value=str(document_id))
                    )
                ]
            )
        )
        try:
            await self._client.delete(self._name, points_selector=selector, wait=True)
        except (UnexpectedResponse, ResponseHandlingException, httpx.TransportError) as exc:
            raise _error(exc) from exc

    async def search(self, q: ChunkQuery) -> list[ChunkHit]:
        where, limit = _filter(q), q.top_k * PREFETCH
        sparse = models.SparseVector(indices=q.sparse.indices, values=q.sparse.values)

        async def query() -> list[ChunkHit]:
            try:
                answer = await self._client.query_points(
                    self._name,
                    prefetch=[
                        models.Prefetch(query=q.dense, using="dense", filter=where, limit=limit),
                        models.Prefetch(query=sparse, using="bm25", filter=where, limit=limit),
                    ],
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    limit=q.top_k,
                    with_payload=True,
                )
            except (UnexpectedResponse, ResponseHandlingException, httpx.TransportError) as exc:
                raise _error(exc) from exc
            return [
                ChunkHit(payload=ChunkPayload.model_validate(point.payload), score=point.score)
                for point in answer.points
            ]

        return await with_retries(query)
