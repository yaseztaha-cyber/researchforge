"""Embedding cache: content_hash -> vector, avoids re-embedding identical chunks."""

from __future__ import annotations

import hashlib
from collections import OrderedDict

from app.services.embeddings.base import EmbeddingProvider


class EmbeddingCache:
    def __init__(self, provider: EmbeddingProvider, max_entries: int = 2048):
        self.provider = provider
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self.max_entries = max_entries
        self.hits = 0
        self.misses = 0

    def _key(self, text: str, model: str) -> str:
        return hashlib.sha256(f"{model}|{text}".encode()).hexdigest()

    def embed_cached(self, text: str) -> tuple[list[float], bool]:
        k = self._key(text, self.provider.name)
        if k in self._cache:
            self.hits += 1
            self._cache.move_to_end(k)
            return self._cache[k], True
        vec = self.provider.embed(text)
        self.misses += 1
        self._cache[k] = vec
        if len(self._cache) > self.max_entries:
            self._cache.popitem(last=False)
        return vec, False

    def embed_many_cached(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        to_compute: list[int] = []
        keys: list[str] = []
        for i, t in enumerate(texts):
            k = self._key(t, self.provider.name)
            keys.append(k)
            if k in self._cache:
                out.append(self._cache[k])
                self.hits += 1
                self._cache.move_to_end(k)
            else:
                out.append([])  # placeholder
                to_compute.append(i)
        if to_compute:
            batch = [texts[i] for i in to_compute]
            vecs = self.provider.embed_many(batch)
            for idx, vec in zip(to_compute, vecs):
                out[idx] = vec
                self.misses += 1
                self._cache[keys[idx]] = vec
                if len(self._cache) > self.max_entries:
                    self._cache.popitem(last=False)
        return out
