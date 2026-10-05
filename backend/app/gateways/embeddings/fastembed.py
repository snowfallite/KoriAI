"""Local embeddings (tech.md §8.6, AD-12): FastEmbed on the CPU, models in FASTEMBED_CACHE_DIR.

The models load (and download) on the first call; the work runs in a thread.
"""

import asyncio
import threading
from collections.abc import Callable

from fastembed import SparseTextEmbedding, TextEmbedding
from fastembed.common.model_description import ModelSource, PoolingType

from app.config import Settings
from app.contracts.vectors import SparseVec
from app.core.errors import TransientGatewayError

# multilingual-e5-small of §8.6; a collection made for it keeps this size.
DENSE_DIM = 384
type Work[T] = Callable[[list[str]], list[T]]
_register_lock = threading.Lock()


def _register(model: str) -> None:
    """FastEmbed does not list multilingual-e5-small: §8.6 adds it as a custom model."""
    with _register_lock:
        known = {m["model"].lower() for m in TextEmbedding.list_supported_models()}
        if model.lower() not in known:
            TextEmbedding.add_custom_model(
                model=model,
                pooling=PoolingType.MEAN,
                normalization=True,
                sources=ModelSource(hf=model),
                dim=DENSE_DIM,
            )


class FastEmbedEmbeddings:
    def __init__(self, settings: Settings) -> None:
        self._dense_name = settings.EMBEDDINGS_DENSE_MODEL
        self._sparse_name = settings.EMBEDDINGS_SPARSE_MODEL
        self._cache_dir = str(settings.FASTEMBED_CACHE_DIR)
        self._lock = threading.Lock()
        self._models: tuple[TextEmbedding, SparseTextEmbedding] | None = None

    def dense_dim(self) -> int:
        return DENSE_DIM

    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return await self._run(self._dense, [f"passage: {text}" for text in texts])

    async def embed_query(self, text: str) -> list[float]:
        [vector] = await self._run(self._dense, [f"query: {text}"])
        return vector

    async def sparse_passages(self, texts: list[str]) -> list[SparseVec]:
        return await self._run(self._sparse, texts)

    async def sparse_query(self, text: str) -> SparseVec:
        [vector] = await self._run(self._sparse_query, [text])
        return vector

    async def _run[T](self, work: Work[T], texts: list[str]) -> list[T]:
        try:
            return await asyncio.to_thread(work, texts)
        except OSError as error:  # the model could not download or load: try again later
            raise TransientGatewayError("internal") from error

    def _loaded(self) -> tuple[TextEmbedding, SparseTextEmbedding]:
        with self._lock:
            if self._models is None:
                _register(self._dense_name)
                self._models = (
                    TextEmbedding(self._dense_name, cache_dir=self._cache_dir),
                    SparseTextEmbedding(
                        self._sparse_name, cache_dir=self._cache_dir, language="russian"
                    ),
                )
            return self._models

    def _dense(self, texts: list[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._loaded()[0].embed(texts)]

    def _sparse(self, texts: list[str]) -> list[SparseVec]:
        return [
            SparseVec(indices=e.indices.tolist(), values=e.values.tolist())
            for e in self._loaded()[1].embed(texts)
        ]

    def _sparse_query(self, texts: list[str]) -> list[SparseVec]:
        return [
            SparseVec(indices=e.indices.tolist(), values=e.values.tolist())
            for e in self._loaded()[1].query_embed(texts)
        ]
