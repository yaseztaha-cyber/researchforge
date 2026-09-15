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
