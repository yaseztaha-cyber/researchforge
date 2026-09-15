"""Embedding interface + deterministic hash embeddings (offline, no API needed)."""

from __future__ import annotations

import hashlib
import math
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    name: str = "base"
    dim: int = 384

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        raise NotImplementedError

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        """Batch embed. Default: sequential. Subclasses may override with bulk API."""
        return [self.embed(t) for t in texts]

    def normalize(self, text: str) -> str:
        """Light normalization before embedding (subclasses may extend)."""
        return text.strip().replace("\x00", "")[:8000]
