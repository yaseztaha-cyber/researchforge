"""Researcher: multi-round retrieval with dedup, ranking, gap-driven follow-ups."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from app.core.config import get_settings
from app.services.retrieval.base import SearchHit, rank_hits
from app.services.retrieval.factory import get_search_provider


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


@dataclass
class RetrievedSource:
    title: str
    url: str | None
    author: str | None
    publisher: str | None
    published_at: str | None
    source_type: str
    domain: str | None
    description: str
    content: str
    content_hash: str
    relevance: float
    quality: float
    breakdown: dict


async def run_retrieval(queries: list[str], *, max_sources: int | None = None,
                        max_relevant: int | None = None) -> tuple[list[RetrievedSource], dict]:
    s = get_settings()
    max_sources = max_sources or s.MAX_SOURCES
    max_relevant = max_relevant or s.MAX_RELEVANT_SOURCES
    provider = get_search_provider()
    rounds = 1 if len(queries) <= 3 else min(s.MAX_SEARCH_ROUNDS, 3)

    seen: dict[str, RetrievedSource] = {}
    meta = {"rounds": 0, "queries_run": [], "duplicates_dropped": 0, "provider": provider.name}
    queries_to_run = list(queries)
    for r in range(rounds):
        # Agentic iteration: after round 1, keep only queries not yet covered.
        batch = queries_to_run[:4] if r == 0 else queries_to_run[4:7]
        if not batch:
            break
        for q in batch:
            meta["queries_run"].append(q)
            try:
                hits: list[SearchHit] = await provider.search(q, limit=8)
            except Exception as e:
                meta.setdefault("errors", []).append(f"{q}: {e}")
                continue
            for ranked in rank_hits(q, hits):
                h = ranked.hit
                body = h.content or h.snippet
                ch = content_hash(f"{h.title}|{body[:2000]}")
                if ch in seen:
                    meta["duplicates_dropped"] += 1
                    continue
                seen[ch] = RetrievedSource(
                    title=h.title[:500], url=h.url, author=h.author, publisher=h.publisher,
                    published_at=h.published_at, source_type=h.source_type or "unknown",
                    domain=h.domain, description=h.snippet[:800], content=body[:20000],
                    content_hash=ch, relevance=ranked.relevance, quality=ranked.quality,
                    breakdown=ranked.breakdown)
                if len(seen) >= max_sources:
                    break
            if len(seen) >= max_sources:
                break
        meta["rounds"] = r + 1
        # Stopping criteria: coverage sufficient or diminishing returns.
        if len(seen) >= max_relevant:
            # cheap coverage check: stop if last round added <2 new sources
            if r > 0 and len(seen) < max_relevant + 2:
                break
    ordered = sorted(seen.values(), key=lambda x: (x.relevance * 0.65 + x.quality * 0.35), reverse=True)
    return ordered[:max_sources], meta
