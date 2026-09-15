from app.core.config import get_settings
from app.services.llm.base import LLMProvider
from app.services.llm.providers.api_provider import ApiLLMProvider
from app.services.llm.providers.mock_provider import MockLLMProvider


def get_llm_provider() -> LLMProvider:
    s = get_settings()
    if s.LLM_PROVIDER == "api" and s.LLM_API_KEY:
        return ApiLLMProvider()
    return MockLLMProvider()


def is_mock_llm() -> bool:
    return isinstance(get_llm_provider(), MockLLMProvider)
