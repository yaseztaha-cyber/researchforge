from app.core.config import get_settings
from app.services.retrieval.base import SearchProvider
from app.services.retrieval.providers.mock_provider import MockSearchProvider
from app.services.retrieval.providers.web_provider import WebSearchProvider


def get_search_provider() -> SearchProvider:
    s = get_settings()
    if s.SEARCH_PROVIDER == "web" and s.SEARCH_API_KEY:
        return WebSearchProvider()
    return MockSearchProvider()


def is_mock_search() -> bool:
    return isinstance(get_search_provider(), MockSearchProvider)
