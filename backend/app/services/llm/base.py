"""LLM provider interface: business logic depends on this, never on a specific vendor."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    text: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def complete(self, *, system: str, user: str, max_tokens: int = 1200, temperature: float = 0.2) -> LLMResponse:
        raise NotImplementedError

    async def complete_json(self, *, system: str, user: str, max_tokens: int = 1200) -> LLMResponse:
        return await self.complete(system=system, user=user, max_tokens=max_tokens, temperature=0.0)
