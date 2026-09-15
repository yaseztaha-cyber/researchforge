"""Deterministic mock LLM: offline-safe, used for dev/tests and clearly labeled in UI."""

from __future__ import annotations

import json
import re

from app.services.llm.base import LLMProvider, LLMResponse


class MockLLMProvider(LLMProvider):
    name = "mock"

    async def complete(self, *, system: str, user: str, max_tokens: int = 1200, temperature: float = 0.2) -> LLMResponse:
        low = (system + "\n" + user).lower()
        if "planner" in low or "sub_question" in low or "sub-question" in low:
            return LLMResponse(text=self._plan_json(user), model="mock-planner")
        if "verif" in low:
            return LLMResponse(text='{"supported": true, "confidence": 0.8, "issues": []}', model="mock-verifier")
        # Generic grounded polish: echo back a constrained summary (never invents citations).
        snippet = user[:800].replace("\n", " ")
        return LLMResponse(
            text=f"Based on the provided evidence, the key points are: {snippet[:400]}.",
            model="mock-generic",
        )

    def _plan_json(self, user: str) -> str:
        m = re.search(r"question\s*[:=]\s*(.+)", user, re.IGNORECASE | re.DOTALL)
        q = (m.group(1).strip().split("\n")[0] if m else user.strip().split("\n")[0][:300]) or "research question"
        topics = ["definitions and scope", "causes and mechanisms", "effects and evidence",
                  "comparisons and alternatives", "mitigations and outlook"]
        subs = [f"{q} — {t}?" for t in topics[:4]]
        plan = {
            "original_question": q[:500],
            "sub_questions": subs,
            "search_queries": [q[:120], f"{q[:80]} evidence review", f"{q[:80]} effects study"],
            "search_strategy": "Decompose into sub-questions; prefer government/academic sources; extract verbatim evidence.",
            "expected_evidence_types": ["government reports", "peer-reviewed studies", "institutional reports"],
            "ambiguities": [],
        }
        return json.dumps(plan)
