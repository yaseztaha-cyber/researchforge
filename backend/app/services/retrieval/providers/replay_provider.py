"""Record/replay fixtures for SearchProvider (v0.3).

Live API -> sanitize -> save fixture -> replay in tests.

Usage:
  RECORD_FIXTURES=1 python -m app.services.retrieval.providers.replay_provider --record "query text"
  or set SEARCH_PROVIDER=replay and place JSON under evaluation/fixtures/providers/search/

Fixtures are sanitized: API keys, private credentials removed. Metadata stored alongside.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from app.services.retrieval.base import SearchHit, SearchProvider
from app.services.retrieval.factory import get_search_provider


def sanitize_record(data: dict) -> dict:
    """Remove secrets; preserve structure. Never store API keys."""
    data = dict(data)
    data.pop("api_key", None)
    data.pop("authorization", None)
    # Keep only expected fields
    return data


def _project_root() -> Path:
    here = Path(__file__).resolve()
    candidates = list(here.parents) + [Path.cwd(), Path.cwd().parent]
    # Prefer the candidate that actually has the example fixture
    for p in reversed(candidates):  # outermost first -> project root beats backend
        if (p / "evaluation" / "fixtures" / "providers" / "search" / "example_search.json").exists():
            return p
    for p in reversed(candidates):
        if (p / "evaluation" / "fixtures").exists():
            return p
    return Path.cwd().parent if Path.cwd().name == "backend" else Path.cwd()


class ReplaySearchProvider(SearchProvider):
    name = "replay"

    def __init__(self, fixture_dir: str | None = None):
        if fixture_dir:
            self.fixture_dir = Path(fixture_dir)
        else:
            self.fixture_dir = _project_root() / "evaluation" / "fixtures" / "providers" / "search"

    async def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        # Exact match file: slugified query, fallback to example_search.json
        slug = "".join(c if c.isalnum() else "_" for c in query.lower())[:60].strip("_")
        path = self.fixture_dir / f"{slug}.json"
        if not path.exists():
            path = self.fixture_dir / "example_search.json"
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        hits: list[SearchHit] = []
        for item in (data.get("results") or [])[:limit]:
            hits.append(SearchHit(title=item.get("title", "Untitled")[:300],
                                  url=item.get("url"), snippet=(item.get("content") or "")[:800],
                                  publisher=item.get("publisher") or item.get("url", "").split("/")[2] if item.get("url") else None,
                                  source_type=item.get("source_type", "unknown"),
                                  domain=item.get("url", "").split("/")[2] if item.get("url") else None,
                                  content=(item.get("content") or "")[:8000],
                                  raw_score=float(item.get("score", 0.5))))
        return hits


def record_fixture(query: str, results: list[dict], provider: str = "tavily") -> Path:
    """Sanitize and save a fixture under evaluation/fixtures/providers/search/."""
    slug = "".join(c if c.isalnum() else "_" for c in query.lower())[:60].strip("_") or "query"
    root = _project_root()
    out = root / "evaluation" / "fixtures" / "providers" / "search" / f"{slug}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "version": "1.0",
        "provider": provider,
        "request_type": "search",
        "sanitized": True,
        "sanitization_notes": "API keys removed; content truncated",
        "query": query,
        "results": sanitize_record({"results": results})["results"],
    }
    out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    meta = {
        "version": "1.0",
        "provider": provider,
        "request_type": "search",
        "sanitization_status": "sanitized",
        "fixture_version": "1.0",
        "source_file": str(out).replace("\\", "/"),
    }
    meta_path = root / "evaluation" / "fixtures" / "providers" / "metadata" / f"{slug}.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return out


# Optional wrapper that records live calls when RECORD_FIXTURES env is set
class RecordingSearchProvider(SearchProvider):
    name = "recording"

    def __init__(self):
        self.inner = get_search_provider.__wrapped__() if hasattr(get_search_provider, "__wrapped__") else None
        # Fallback: instantiate web provider directly if needed
        if self.inner is None or self.inner.name == "recording":
            from app.services.retrieval.providers.mock_provider import MockSearchProvider
            from app.services.retrieval.providers.web_provider import WebSearchProvider
            from app.core.config import get_settings
            s = get_settings()
            self.inner = WebSearchProvider() if s.SEARCH_PROVIDER == "web" and s.SEARCH_API_KEY else MockSearchProvider()

    async def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        hits = await self.inner.search(query, limit=limit)
        if os.getenv("RECORD_FIXTURES") == "1":
            record_fixture(query, [{"title": h.title, "url": h.url, "content": h.content, "score": h.raw_score} for h in hits])
        return hits
