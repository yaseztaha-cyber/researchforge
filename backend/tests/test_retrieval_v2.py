"""v0.2: typed query generation, canonical dedup, quality components, diversity."""

from app.agents.planner import rule_based_plan
from app.services.llm.providers.mock_provider import MockLLMProvider
from app.agents.planner import plan_research
from app.services.retrieval.base import (SearchHit, canonicalize_url, classify_source,
                                         rank_hits, select_diverse)


async def test_queries_are_typed_and_diverse():
    plan = rule_based_plan("What are the environmental impacts of desalination?")
    types = {q.query_type for q in plan.search_queries}
    assert len(types) >= 4
    assert all(q.reason for q in plan.search_queries)


async def test_mock_plan_has_typed_queries():
    plan = await plan_research("What causes tides?", MockLLMProvider())
    assert all(hasattr(q, "query_type") for q in plan.search_queries)


async def test_legacy_string_queries_coerced():
    class Legacy:
        async def complete_json(self, **kw):
            import json as _json
            from app.services.llm.base import LLMResponse
            return LLMResponse(text=_json.dumps({
                "original_question": "What causes ocean tides on Earth?",
                "sub_questions": ["What causes ocean tides aspect 1?", "What causes ocean tides aspect 2?"],
                "search_queries": ["first query tides", "second query tides"],
                "search_strategy": "strategy text here yes",
                "expected_evidence_types": [], "ambiguities": []}), model="x")
    plan = await plan_research("What causes ocean tides on Earth?", Legacy())
    assert len(plan.search_queries) == 2
    assert all(q.query_type for q in plan.search_queries)


def test_canonical_url_strips_tracking():
    a = canonicalize_url("https://WWW.Example.com/path/?utm_source=x&b=1#frag")
    b = canonicalize_url("https://example.com/path?b=1")
    assert a == b


def test_classify_government_with_reason():
    t, reasons = classify_source("https://www.epa.gov/water", "EPA")
    assert t == "government"
    assert reasons


def test_ranking_has_components_and_reasons():
    hits = [SearchHit(title="EPA desalination brine report", url="https://epa.gov/x",
                      snippet="brine effects", source_type="government",
                      domain="epa.gov", content="desalination brine " * 200)]
    ranked = rank_hits("desalination brine effects", hits)
    b = ranked[0].breakdown
    for key in ("semantic_relevance", "query_coverage", "source_quality",
                "content_usefulness", "formula"):
        assert key in b
    assert ranked[0].reasons
    assert 0.0 <= ranked[0].final <= 1.0


def test_diversity_prefers_type_variety():
    def hit(i, stype, domain):
        return SearchHit(title=f"desalination study {i} {stype}", url=f"https://{domain}/{i}",
                         snippet="desalination", source_type=stype, domain=domain,
                         content="desalination " * 100)
    pool = [hit(i, "blog", "same.example.com") for i in range(6)] + [
        hit(7, "government", "epa.gov"), hit(8, "academic", "uni.edu")]
    ranked = rank_hits("desalination", pool)
    chosen = select_diverse(ranked, 4)
    types = {c.hit.source_type for c in chosen}
    assert len(types) >= 2
