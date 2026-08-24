"""Embedding providers.

The default embedder is deterministic and dependency-free (hashed
bag-of-words, L2-normalized) so the whole context plane runs offline and
reproducibly. Real embedding services implement the same protocol.
"""

import hashlib
import math
import re
from typing import Protocol

TOKEN = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dimension: int

    def embed(self, text: str) -> list[float]: ...


class DeterministicHashEmbedder:
    """Portable fallback embedder: hashed token counts, L2-normalized."""

    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        for token in TOKEN.findall(text.lower()):
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(v * v for v in vector))
        if norm == 0:
            return vector
        return [v / norm for v in vector]


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
