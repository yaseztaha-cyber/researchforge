"""Live web provider (Tavily-compatible or generic). Graceful errors, SSRF-guarded fetch."""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup
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


class WebSearchProvider(SearchProvider):
    name = "web"

    async def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        s = get_settings()
        if not s.SEARCH_API_KEY:
            raise RuntimeError("SEARCH_API_KEY not set; configure a search provider or use mock mode.")
        # Tavily-compatible `/search` endpoint; adapt SEARCH_API_URL for other vendors.
        endpoint = (s.SEARCH_API_URL or "https://api.tavily.com/search").rstrip("/")
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(endpoint, json={"query": query, "max_results": limit,
                                                  "search_depth": "advanced", "include_answer": False},
                                  headers={"Authorization": f"Bearer {s.SEARCH_API_KEY}"})
            r.raise_for_status()
            data = r.json()
        hits: list[SearchHit] = []
        for item in (data.get("results") or [])[:limit]:
            url = item.get("url")
            domain = _domain(url)
            hits.append(SearchHit(title=item.get("title", url or "Untitled")[:300],
                                  url=url, snippet=(item.get("content") or "")[:800],
                                  publisher=domain, source_type=_guess_type(domain, url),
                                  domain=domain, content=(item.get("content") or "")[:8000],
                                  raw_score=float(item.get("score", 0.5))))
        return hits

    async def fetch(self, url: str) -> str:
        validate_url(url)
        async with httpx.AsyncClient(timeout=30, follow_redirects=True,
                                     headers={"User-Agent": "ResearchForge/0.1 research agent"}) as client:
            r = await client.get(url)
            r.raise_for_status()
            html = r.text[:500_000]
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        text = soup.get_text(separator="\n")
        lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 40]
        return "\n".join(lines)[:20_000]
