"""Research planner: decomposes a question into sub-questions + search queries.

Uses the LLM when available but ALWAYS validates with the ResearchPlan schema,
with a deterministic rule-based fallback so the pipeline never breaks on
malformed model output.
"""

from __future__ import annotations

import json
import re

from app.schemas.research import ResearchPlan
from app.services.llm.base import LLMProvider

PLANNER_SYSTEM = (
    "You are the ResearchForge planner. Decompose research questions into sub-questions "
    "and search queries. Reply with STRICT JSON matching: original_question, sub_questions "
    "(2-5), search_queries (2-6), search_strategy, expected_evidence_types, ambiguities. "
    "No prose outside JSON."
)


def rule_based_plan(question: str) -> ResearchPlan:
    q = question.strip()
    # Split on ? or ; or ' and ' to find dimensions; cap at 5.
    parts = [p.strip(" .") for p in re.split(r"[?;]|\sand\s", q) if len(p.strip()) > 4]
    subs = [f"{p}?" if not p.endswith("?") else p for p in parts[:4]]
    while len(subs) < 3:
        subs.append(f"{q} — aspect {len(subs) + 1}: evidence and mechanisms?")
    keywords = " ".join(re.findall(r"[A-Za-z]{4,}", q))[:120]
    return ResearchPlan(
        original_question=q[:500],
        sub_questions=subs[:5],
        search_queries=[q[:140], f"{keywords} evidence review"[:140], f"{keywords} effects study"[:140]],
        search_strategy=("Decompose into sub-questions; run 1-2 search rounds preferring "
                         "government/academic/institutional sources; stop on coverage or redundancy."),
        expected_evidence_types=["government reports", "peer-reviewed studies", "institutional reports"],
        ambiguities=[] if len(q) > 20 else ["Question is short; scope may need clarification."],
    )


async def plan_research(question: str, llm: LLMProvider) -> ResearchPlan:
    try:
        resp = await llm.complete_json(system=PLANNER_SYSTEM, user=f"Question: {question}")
        data = json.loads(resp.text.strip().removeprefix("```json").removesuffix("```").strip())
        return ResearchPlan.model_validate(data)
    except Exception:
        return rule_based_plan(question)
