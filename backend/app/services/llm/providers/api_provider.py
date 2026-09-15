"""API LLM provider: OpenAI-compatible endpoint via httpx. Never called without a key."""

from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.services.llm.base import LLMProvider, LLMResponse


class ApiLLMProvider(LLMProvider):
    name = "api"

    async def complete(self, *, system: str, user: str, max_tokens: int = 1200, temperature: float = 0.2) -> LLMResponse:
        s = get_settings()
        if not s.LLM_API_KEY:
            raise RuntimeError("LLM_API_KEY is not set; cannot use api provider (use mock instead).")
        url = s.LLM_BASE_URL.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {s.LLM_API_KEY}"}
        payload = {
            "model": s.MODEL_NAME,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            data = r.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        return LLMResponse(
            text=text,
            model=s.MODEL_NAME,
            prompt_tokens=int(usage.get("prompt_tokens", 0)),
            completion_tokens=int(usage.get("completion_tokens", 0)),
        )
