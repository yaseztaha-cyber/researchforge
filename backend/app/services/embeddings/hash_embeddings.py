"""Deterministic hashed-token embeddings: stable across runs, good enough for local RAG."""

from __future__ import annotations

import hashlib
import math
import re

from app.services.embeddings.base import EmbeddingProvider

DIM = 384
_TOKEN = re.compile(r"[a-z0-9]+")


def _idx(token: str) -> int:
    return int(hashlib.sha256(token.encode()).hexdigest(), 16) % DIM


class HashEmbeddingProvider(EmbeddingProvider):
    name = "hash"
    dim = DIM

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for tok in _TOKEN.findall(text.lower()):
            if len(tok) < 3:
                continue
            vec[_idx(tok)] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]


def cosine(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    na = math.sqrt(sum(v * v for v in a[:n])) or 1.0
    nb = math.sqrt(sum(v * v for v in b[:n])) or 1.0
    return dot / (na * nb)
