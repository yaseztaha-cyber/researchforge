"""Unit: planner returns validated plans incl. malformed-LLM fallback."""

from app.agents.planner import plan_research, rule_based_plan
from app.services.llm.providers.mock_provider import MockLLMProvider


async def test_rule_based_plan_valid():
    plan = rule_based_plan("What are the environmental impacts of desalination?")
    assert len(plan.sub_questions) >= 3
    assert len(plan.search_queries) >= 2


async def test_planner_with_mock_llm():
    plan = await plan_research("What are the environmental impacts of desalination?", MockLLMProvider())
    assert plan.original_question
    assert 1 <= len(plan.sub_questions) <= 8


async def test_planner_fallback_on_garbage():
    class Garbage:
        async def complete_json(self, **kw):
            from app.services.llm.base import LLMResponse
            return LLMResponse(text="NOT JSON {{{", model="x")

    plan = await plan_research("What causes tides?", Garbage())
    assert plan.original_question
    assert len(plan.sub_questions) >= 1
