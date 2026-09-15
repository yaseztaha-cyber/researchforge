"""Research planner: decomposes a question into sub-questions + categorized search queries.

Uses the LLM when available but ALWAYS validates with the ResearchPlan schema,
with a deterministic rule-based fallback so the pipeline never breaks on
malformed model output. Every query carries a type + reason for auditability.
"""

from __future__ import annotations

import json
import re

from app.schemas.research import QuerySpec, ResearchPlan

PLANNER_SYSTEM = (
    "You are the ResearchForge planner. Decompose research questions into sub-questions "
    "and DIVERSE search queries. Reply with STRICT JSON matching: original_question, "
    "sub_questions (2-5), search_queries (4-7 items, each {query, query_type, reason}), "
    "search_strategy, expected_evidence_types, ambiguities. "
    "query_type must be one of: broad, scientific, mechanism, consequence, recent, "
    "mitigation, controversy. Cover complementary angles — do NOT paraphrase one query. "
    "No prose outside JSON."
)

_CATEGORIES: list[tuple[str, str, str]] = [
    ("broad", "{}", "Broad overview of the question"),
    ("scientific", "{} peer-reviewed evidence", "Scientific / peer-reviewed evidence"),
    ("mechanism", "{} causes mechanisms", "Underlying causes and mechanisms"),
    ("consequence", "{} effects impacts", "Effects and consequences"),
    ("recent", "{} recent findings 2023 2024 2025", "Recent evidence"),
    ("mitigation", "{} mitigation solutions", "Mitigations and solutions"),
    ("controversy", "{} disagreement debate evidence", "Disagreement / controversy"),
]


def rule_based_plan(question: str, *, max_queries: int = 7) -> ResearchPlan:
    q = question.strip()
    parts = [p.strip(" .") for p in re.split(r"[?;]|\sand\s", q) if len(p.strip()) > 4]
    subs = [f"{p}?" if not p.endswith("?") else p for p in parts[:4]]
    while len(subs) < 3:
        subs.append(f"{q} — aspect {len(subs) + 1}: evidence and mechanisms?")
    core = re.sub(r"\?$", "", q).strip()
    queries = [QuerySpec(query=pat.format(core)[:200], query_type=qt, reason=reason)
               for qt, pat, reason in _CATEGORIES[: max(1, min(max_queries, len(_CATEGORIES)))]]
    return ResearchPlan(
        original_question=q[:500],
        sub_questions=subs[:5],
        search_queries=queries,
        search_strategy=("Decompose into sub-questions; run complementary typed queries preferring "
                         "government/academic/institutional sources; follow up on gaps; stop on "
                         "coverage, redundancy, or configured limits."),
        expected_evidence_types=["government reports", "peer-reviewed studies", "institutional reports"],
        ambiguities=[] if len(q) > 20 else ["Question is short; scope may need clarification."],
    )


def _coerce_queries(raw: object, question: str) -> list[QuerySpec]:
    """Accept new [{query, query_type, reason}] or legacy [str] LLM output."""
    if isinstance(raw, list) and raw and isinstance(raw[0], str):
        base = rule_based_plan(question)
        types = [c[0] for c in _CATEGORIES]
        return [QuerySpec(query=s[:200], query_type=types[i % len(types)],
                          reason="Legacy string query; typed heuristically.")
                for i, s in enumerate(raw[:7]) if s and s.strip()]
    return [QuerySpec.model_validate(q) for q in (raw or [])]


async def plan_research(question: str, llm, *, max_queries: int = 7) -> ResearchPlan:
    try:
        resp = await llm.complete_json(system=PLANNER_SYSTEM, user=f"Question: {question}")
        data = json.loads(resp.text.strip().removeprefix("```json").removesuffix("```").strip())
        data["search_queries"] = _coerce_queries(data.get("search_queries"), question)[:max_queries]
        return ResearchPlan.model_validate(data)
    except Exception:
        return rule_based_plan(question, max_queries=max_queries)
