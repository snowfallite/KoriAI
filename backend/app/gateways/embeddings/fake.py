"""Embeddings fake (tech.md §8.1, §8.6): hashed words instead of a model.

Texts that share words come out close, so search tests rank by meaning of a sort. No seed:
the vectors come from the text itself.
"""

import hashlib
import math
import re
from collections import Counter

from app.contracts.vectors import SparseVec
from app.gateways.fakes import Fake, port_method

DIM = 384  # the size of multilingual-e5-small, so a collection fits both
SPARSE_SPACE = 1 << 20
WORD = re.compile(r"\w+")


def _bucket(word: str, size: int) -> int:
    return int.from_bytes(hashlib.blake2b(word.encode(), digest_size=8).digest()) % size


def _words(text: str) -> list[str]:
    return WORD.findall(text.casefold())


def dense(text: str) -> list[float]:
    vector = [0.0] * DIM
    for word in _words(text):
        vector[_bucket(word, DIM)] += 1.0
    norm = math.sqrt(sum(v * v for v in vector))
    if not norm:
        return [1.0] + [0.0] * (DIM - 1)  # cosine needs a direction even for no words
    return [v / norm for v in vector]


def sparse(text: str, *, counts: bool) -> SparseVec:
    """Term counts of a passage; a query weighs each term once, as bm25 queries do."""
    terms = Counter(_bucket(word, SPARSE_SPACE) for word in _words(text))
    indices = sorted(terms)
    return SparseVec(indices=indices, values=[float(terms[i]) if counts else 1.0 for i in indices])


class FakeEmbeddings(Fake):
    port = "embeddings"
    unavailable = "internal"
    rate_limited = "internal"

    def dense_dim(self) -> int:
        return DIM

    @port_method(empty=lambda a: [[0.0] * DIM for _ in a["texts"]])
    async def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [dense(text) for text in texts]

    @port_method(empty=lambda a: [0.0] * DIM)
    async def embed_query(self, text: str) -> list[float]:
        return dense(text)

    @port_method(empty=lambda a: [SparseVec(indices=[], values=[]) for _ in a["texts"]])
    async def sparse_passages(self, texts: list[str]) -> list[SparseVec]:
        return [sparse(text, counts=True) for text in texts]

    @port_method(empty=lambda a: SparseVec(indices=[], values=[]))
    async def sparse_query(self, text: str) -> SparseVec:
        return sparse(text, counts=False)
