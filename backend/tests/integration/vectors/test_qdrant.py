"""The Qdrant adapter on a real Qdrant (S1-09; tech.md §8.6): collection, upsert, filters,
hybrid search, delete by document."""

import uuid
from collections.abc import AsyncIterator

import pytest

from app.config import Settings
from app.contracts.vectors import ChunkPayload, ChunkPoint, ChunkQuery
from app.gateways.embeddings.fake import FakeEmbeddings
from app.gateways.vectors.qdrant import QdrantVectorStore

SBER, LKOH = uuid.uuid4(), uuid.uuid4()
SBER_IFRS, SBER_RAS, LKOH_IFRS = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
CHUNKS = [
    (SBER_IFRS, SBER, "ifrs_interim", 2026, "Выручка группы выросла на 12% год к году"),
    (SBER_IFRS, SBER, "ifrs_interim", 2026, "Стоимость риска осталась в пределах прогноза"),
    (SBER_RAS, SBER, "ras_annual", 2025, "Бухгалтерский баланс банка на конец года"),
    (LKOH_IFRS, LKOH, "ifrs_annual", 2025, "Выручка от продажи нефти и нефтепродуктов"),
]
embeddings = FakeEmbeddings()


@pytest.fixture
async def store() -> AsyncIterator[QdrantVectorStore]:
    settings = Settings(
        _env_file=None,
        VECTORS_MODE="qdrant",
        QDRANT_URL="http://127.0.0.1:6333",
        QDRANT_COLLECTION=f"test_{uuid.uuid4().hex[:12]}",
    )
    store = QdrantVectorStore(settings, embeddings.dense_dim())
    await store.ensure_collection()
    try:
        yield store
    finally:
        await store._client.delete_collection(settings.QDRANT_COLLECTION)
        await store.aclose()


async def points() -> list[ChunkPoint]:
    found = []
    for index, (document_id, issuer_id, kind, year, text) in enumerate(CHUNKS):
        [dense] = await embeddings.embed_passages([text])
        [sparse] = await embeddings.sparse_passages([text])
        payload = ChunkPayload(
            document_id=document_id,
            issuer_id=issuer_id,
            kind=kind,
            standard="ras" if kind.startswith("ras") else "ifrs",
            period_year=year,
            period_label=str(year),
            page=index + 1,
            chunk_idx=index,
            text=text,
        )
        point_id = uuid.uuid5(document_id, str(index))  # uuid5(document_id, chunk_idx) of §8.6
        found.append(ChunkPoint(id=point_id, dense=dense, sparse=sparse, payload=payload))
    return found


async def query(text: str, **filters: object) -> ChunkQuery:
    return ChunkQuery.model_validate(
        {
            "text": text,
            "dense": await embeddings.embed_query(text),
            "sparse": await embeddings.sparse_query(text),
            "issuer_id": None,
            "kinds": None,
            "years": None,
            "top_k": 10,
            **filters,
        }
    )


async def texts(store: QdrantVectorStore, q: ChunkQuery) -> list[str]:
    return [hit.payload.text for hit in await store.search(q)]


async def test_ensure_collection_runs_again_without_harm(store: QdrantVectorStore) -> None:
    await store.ensure_collection()


async def test_hybrid_search_finds_the_words_first(store: QdrantVectorStore) -> None:
    await store.upsert(await points())

    found = await texts(store, await query("выручка", issuer_id=SBER))

    assert found[0] == "Выручка группы выросла на 12% год к году"
    assert "Выручка от продажи нефти и нефтепродуктов" not in found  # another issuer


async def test_filters_by_kind_and_year(store: QdrantVectorStore) -> None:
    await store.upsert(await points())

    by_kind = await texts(store, await query("баланс", kinds=["ras_annual"]))
    by_year = await texts(store, await query("выручка", years=[2025]))

    assert by_kind == ["Бухгалтерский баланс банка на конец года"]
    assert set(by_year) == {
        "Бухгалтерский баланс банка на конец года",
        "Выручка от продажи нефти и нефтепродуктов",
    }


async def test_upsert_twice_keeps_one_point_per_id(store: QdrantVectorStore) -> None:
    await store.upsert(await points())
    await store.upsert(await points())

    assert len(await texts(store, await query("год"))) == len(CHUNKS)


async def test_delete_document_drops_only_its_chunks(store: QdrantVectorStore) -> None:
    await store.upsert(await points())

    await store.delete_document(SBER_IFRS)

    left = await texts(store, await query("выручка баланс"))
    assert sorted(left) == sorted(text for doc, *_, text in CHUNKS if doc != SBER_IFRS)
