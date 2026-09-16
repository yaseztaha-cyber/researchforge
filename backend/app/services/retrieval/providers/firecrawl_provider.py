"""Firecrawl live search provider — OpenAI-compatible research via Firecrawl v2.

Uses POST https://api.firecrawl.dev/v2/search
Sanitized for RECORD_FIXTURES (no key stored).
"""

from __future__ import annotations

import httpx
from urllib.parse import urlparse

from app.core.config import get_settings
from app.core.security import validate_url
from app.services.retrieval.base import SearchHit, SearchProvider


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return None

def _guess_type(domain: str | None, url: str | None) -> str:
    d = (domain or "") + " " + (url or "")
    if ".gov" in d:
        return "government"
    if ".edu" in d or ".ac." in d:
        return "academic"
    if any(k in d for k in ("nature.com", "science.org", "nih.gov", "who.int", "un.org")):
        return "scientific"
    return "unknown"

class FirecrawlSearchProvider(SearchProvider):
    name = "firecrawl"

    async def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        import os
        s = get_settings()
        key = s.FIRECRAWL_API_KEY if hasattr(s, "FIRECRAWL_API_KEY") and s.FIRECRAWL_API_KEY else (s.SEARCH_API_KEY or os.getenv("FIRECRAWL_API_KEY", ""))
        if not key:
            key = os.getenv("FIRECRAWL_API_KEY", "")
        if not key:
            raise RuntimeError("FIRECRAWL_API_KEY not set; cannot use firecrawl provider")
        # Firecrawl v2 search
        url = "https://api.firecrawl.dev/v2/search"
        payload = {"query": query, "limit": limit, "sources": [{"type": "web"}]}
        # Some deployments use sources: ["web"], handle both
        headers = {"Authorization": f"Bearer {key}"}
        timeout = s.REQUEST_TIMEOUT_SECONDS if hasattr(s, "REQUEST_TIMEOUT_SECONDS") else 30
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, json=payload, headers=headers)
            # Fallback to single source param if needed
            if r.status_code in (400, 422):
                # Try alternative payload shape
                payload2 = {"query": query, "limit": limit}
                r = await client.post(url, json=payload2, headers=headers)
            r.raise_for_status()
            data = r.json()
        # Firecrawl returns {success: true, data: [{url, title, description, markdown, ...}]} or {data: {web: [...]}}
        results = []
        if isinstance(data.get("data"), list):
            results = data["data"]
        elif isinstance(data.get("data"), dict):
            # Try web key
            results = data["data"].get("web") or data["data"].get("results") or []
        elif isinstance(data.get("results"), list):
            results = data["results"]
        hits: list[SearchHit] = []
        for item in results[:limit]:
            u = item.get("url") or item.get("link")
            if u:
                try:
                    validate_url(u)
                except Exception:
                    continue
            domain = _domain(u)
            title = (item.get("title") or u or "Untitled")[:300]
            content = (item.get("description") or item.get("markdown") or item.get("content") or "")[:8000]
            snippet = (item.get("description") or content)[:800]
            hits.append(SearchHit(title=title, url=u, snippet=snippet, publisher=domain, source_type=_guess_type(domain, u), domain=domain, content=content, raw_score=float(item.get("score", 0.5) if isinstance(item.get("score"), (int,float)) else 0.5)))
        # Sanitized recording when RECORD_FIXTURES=1 (never store key)
        if os.getenv("RECORD_FIXTURES") == "1":
            try:
                from app.services.retrieval.providers.replay_provider import record_fixture
                record_fixture(query, [{"title": h.title, "url": h.url, "content": h.content, "score": h.raw_score} for h in hits], provider="firecrawl")
            except Exception:
                pass
        return hits

    async def fetch(self, url: str) -> str:
        validate_url(url)
        import os
        key = os.getenv("FIRECRAWL_API_KEY", "")
        if not key:
            return ""
        # Use scrape endpoint
        api_url = "https://api.firecrawl.dev/v2/scrape"
        headers = {"Authorization": f"Bearer {key}"}
        payload = {"url": url, "formats": ["markdown"]}
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                r = await client.post(api_url, json=payload, headers=headers)
                r.raise_for_status()
                data = r.json()
                md = ""
                if isinstance(data.get("data"), dict):
                    md = data["data"].get("markdown") or data["data"].get("content") or ""
                elif isinstance(data.get("markdown"), str):
                    md = data["markdown"]
                return md[:20000]
        except Exception:
            return ""
