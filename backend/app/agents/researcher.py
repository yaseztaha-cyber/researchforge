"""Researcher: multi-round retrieval with dedup, ranking, gap-driven follow-ups.

v0.2: parallel query execution, canonical-URL + content-hash dedup with
provenance (which queries discovered each source), per-query audit records,
per-query failure tolerance, diversity-aware selection, hard time budget.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.db_models import ResearchQuery
from app.schemas.research import QuerySpec
from app.services.retrieval.base import SearchHit, canonicalize_url, rank_hits, select_diverse
from app.services.retrieval.factory import get_search_provider


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


@dataclass
class RetrievedSource:
    title: str
    url: str | None
    canonical_url: str | None
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
    usefulness: float
    final: float
    breakdown: dict
    reasons: list[str] = field(default_factory=list)
    discovered_by: list[str] = field(default_factory=list)


async def _run_one(provider, spec: QuerySpec, limit: int) -> tuple[QuerySpec, list[SearchHit] | Exception]:
    try:
        hits = await provider.search(spec.query, limit=limit)
        return spec, hits
    except Exception as e:  # per-query failure must not kill the run
        return spec, e


async def run_retrieval(queries: list[QuerySpec], *, max_sources: int | None = None,
                        max_relevant: int | None = None, max_rounds: int | None = None,
                        db: Session | None = None, run_id: str | None = None,
                        deadline: float | None = None) -> tuple[list[RetrievedSource], dict]:
    s = get_settings()
    max_sources = max_sources or s.MAX_SOURCES
    max_relevant = max_relevant or s.MAX_RELEVANT_SOURCES
    max_rounds = max_rounds or s.MAX_SEARCH_ROUNDS
    per_query = s.MAX_RESULTS_PER_QUERY
    provider = get_search_provider()

    seen: dict[str, RetrievedSource] = {}
    meta = {"rounds": 0, "queries_run": [], "query_types": {}, "duplicates_dropped": 0,
            "queries_failed": [], "provider": provider.name, "selection": "mmr-diverse"}
    t_start = time.time()

    rounds = [queries[i:i + 4] for i in range(0, len(queries[: s.MAX_QUERIES]), 4)][:max_rounds]
    for rnd, batch in enumerate(rounds, start=1):
        if deadline and time.time() > deadline:
            meta["stopped"] = "time budget reached"
            break
        results = await asyncio.gather(*[_run_one(provider, spec, per_query) for spec in batch])
        hits_all: list[tuple[QuerySpec, SearchHit]] = []
        for spec, res in results:
            qlabel = f"[{spec.query_type}] {spec.query}"
            if isinstance(res, Exception):
                meta["queries_failed"].append({"query": spec.query, "error": f"{type(res).__name__}: {res}"[:300]})
                if db is not None and run_id:
                    db.add(ResearchQuery(run_id=run_id, query=spec.query[:300], query_type=spec.query_type,
                                         reason=spec.reason, round_number=rnd, status="failed", hits=0))
                continue
            meta["queries_run"].append(qlabel)
            meta["query_types"][spec.query_type] = meta["query_types"].get(spec.query_type, 0) + 1
            if db is not None and run_id:
                db.add(ResearchQuery(run_id=run_id, query=spec.query[:300], query_type=spec.query_type,
                                     reason=spec.reason, round_number=rnd, status="ok", hits=len(res)))
            for h in res:
                hits_all.append((spec, h))
        if db is not None and run_id:
            db.commit()

        # Rank per query, then merge with canonical+hash dedup (provenance preserved).
        for spec, h in hits_all:
            ranked = rank_hits(spec.query, [h])
            if not ranked:
                continue
            r = ranked[0]
            body = h.content or h.snippet
            ch = content_hash(f"{h.title}|{body[:2000]}")
            canon = canonicalize_url(h.url)
            key = canon or f"hash:{ch}"
            # title-similarity fallback: same normalized title from same domain
            norm_title = " ".join(h.title.lower().split())[:120]
            dupe_key = next((k for k, v in seen.items()
                             if v.content_hash == ch or (v.canonical_url and v.canonical_url == canon and canon)
                             or (" ".join(v.title.lower().split())[:120] == norm_title
                                 and v.domain == h.domain and h.domain)), None)
            if dupe_key:
                if spec.query not in seen[dupe_key].discovered_by:
                    seen[dupe_key].discovered_by.append(spec.query)
                meta["duplicates_dropped"] += 1
                continue
            seen[key] = RetrievedSource(
                title=h.title[:500], url=h.url, canonical_url=canon, author=h.author,
                publisher=h.publisher, published_at=h.published_at, source_type=r.hit.source_type,
                domain=h.domain, description=h.snippet[:800], content=body[:20000],
                content_hash=ch, relevance=r.relevance, quality=r.quality,
                usefulness=r.usefulness, final=r.final, breakdown=r.breakdown,
                reasons=r.reasons, discovered_by=[spec.query])
            if len(seen) >= max_sources * 2:  # gather headroom; final cut is diversity-selected
                break
        meta["rounds"] = rnd
        # Stopping criteria: coverage sufficient AND novelty dropping.
        if len(seen) >= max_relevant and rnd >= 1:
            if meta["duplicates_dropped"] >= len(seen):
                meta["stopped"] = "diminishing returns (mostly duplicates)"
                break
    if db is not None and run_id:
        db.commit()

    # Diversity-aware final selection over the merged pool.
    pool = sorted(seen.values(), key=lambda x: x.final, reverse=True)
    # Re-rank pool entries as RankedSource-compatible for select_diverse
    from app.services.retrieval.base import RankedSource, SearchHit as _SH
    ranked_pool = [RankedSource(hit=_SH(title=v.title, url=v.url, snippet=v.description,
                                        author=v.author, publisher=v.publisher,
                                        published_at=v.published_at, source_type=v.source_type,
                                        domain=v.domain, content=v.content),
                                relevance=v.relevance, quality=v.quality, usefulness=v.usefulness,
                                final=v.final, breakdown=v.breakdown, reasons=v.reasons)
                   for v in pool]
    chosen = select_diverse(ranked_pool, max_sources)
    chosen_keys = {(c.hit.title, c.hit.url) for c in chosen}
    ordered = [v for v in pool if (v.title, v.url) in chosen_keys]
    meta["elapsed_s"] = round(time.time() - t_start, 2)
    return ordered, meta
