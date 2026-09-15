"""Live web provider (Tavily-compatible or generic). Hardened: retries, 429, timeouts, SSRF-guarded fetch."""

from __future__ import annotations

import asyncio
import random

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


async def _with_retries(coro, *, retries: int = 2, base_delay: float = 0.7):
    last: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return await coro()
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError) as e:
            last = e
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < retries:
                retry_after = e.response.headers.get("retry-after")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else base_delay * (2 ** attempt)
                delay += random.uniform(0, 0.3)
                await asyncio.sleep(min(delay, 8))
                last = e
                continue
            if e.response.status_code in (500, 502, 503, 504) and attempt < retries:
                await asyncio.sleep(base_delay * (2 ** attempt) + random.uniform(0, 0.3))
                last = e
                continue
            raise
    raise last  # type: ignore[misc]


class WebSearchProvider(SearchProvider):
    name = "web"

    async def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        s = get_settings()
        if not s.SEARCH_API_KEY:
            raise RuntimeError("SEARCH_API_KEY not set; configure a search provider or use mock mode.")
        endpoint = (s.SEARCH_API_URL or "https://api.tavily.com/search").rstrip("/")

        async def _do():
            async with httpx.AsyncClient(timeout=s.REQUEST_TIMEOUT_SECONDS) as client:
                r = await client.post(endpoint, json={"query": query, "max_results": limit,
                                                      "search_depth": "advanced", "include_answer": False},
                                      headers={"Authorization": f"Bearer {s.SEARCH_API_KEY}"})
                r.raise_for_status()
                return r.json()

        data = await _with_retries(_do, retries=2)
        results = data.get("results") or []
        if not results:
            return []  # empty search results handled gracefully
        hits: list[SearchHit] = []
        for item in results[:limit]:
            url = item.get("url")
            # Validate URL early; skip invalid ones instead of failing whole query
            if url:
                try:
                    validate_url(url)
                except Exception:
                    continue
            domain = _domain(url)
            try:
                raw = float(item.get("score", 0.5))
            except Exception:
                raw = 0.5
            hits.append(SearchHit(title=(item.get("title") or url or "Untitled")[:300],
                                  url=url, snippet=(item.get("content") or "")[:800],
                                  publisher=domain, source_type=_guess_type(domain, url),
                                  domain=domain, content=(item.get("content") or "")[:8000],
                                  raw_score=raw))
        return hits

    async def fetch(self, url: str) -> str:
        validate_url(url)
        s = get_settings()

        async def _do():
            async with httpx.AsyncClient(timeout=s.REQUEST_TIMEOUT_SECONDS, follow_redirects=True,
                                         headers={"User-Agent": "ResearchForge/0.3 research agent"}) as client:
                r = await client.get(url)
                # 429 and 5xx handled by outer retries
                r.raise_for_status()
                return r.text[:500_000]

        try:
            html = await _with_retries(_do, retries=1)
        except httpx.HTTPStatusError as e:
            # Content extraction failure: return empty string gracefully, caller treats as thin content
            if e.response.status_code in (403, 404, 410):
                return ""
            raise
        except Exception:
            return ""
        # Malformed pages: parsing errors return snippet safely
        try:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "nav", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) > 40]
            return "\n".join(lines)[:20_000]
        except Exception:
            # Malformed HTML fallback: strip tags naively
            return html[:20000]
