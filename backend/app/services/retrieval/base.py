"""Search provider interface + ranking. Business logic never touches a vendor SDK."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SearchHit:
    title: str
    url: str | None
    snippet: str
    author: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    source_type: str = "unknown"
    domain: str | None = None
    content: str = ""
    raw_score: float = 0.0


class SearchProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        raise NotImplementedError

    async def fetch(self, url: str) -> str:
        return ""


# --- Ranking: transparent, stored breakdown (never an unexplained magic score) ---

TRUSTED_TYPES = {"government": 0.95, "academic": 0.93, "scientific": 0.92, "university": 0.90,
                 "institutional": 0.82, "technical_documentation": 0.80, "news": 0.55, "blog": 0.40, "unknown": 0.35}

_TRUSTED_DOMAINS = (".gov", ".edu", ".ac.", "who.int", "un.org", "nature.com", "science.org",
                    "nih.gov", "noaa.gov", "epa.gov", "iea.org", "ipcc.ch")


def token_overlap(a: str, b: str) -> float:
    """Jaccard overlap (symmetric). Kept for keyword-style signals."""
    ta = {t for t in a.lower().split() if len(t) > 2}
    tb = {t for t in b.lower().split() if len(t) > 2}
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def term_coverage(query: str, doc: str) -> float:
    """Fraction of query terms present in doc — recall-oriented retrieval signal."""
    tq = {t for t in query.lower().split() if len(t) > 2}
    td = set(doc.lower().split())
    if not tq:
        return 0.0
    return len(tq & td) / len(tq)


@dataclass
class RankedSource:
    hit: SearchHit
    relevance: float
    quality: float
    breakdown: dict = field(default_factory=dict)


def rank_hits(query: str, hits: list[SearchHit]) -> list[RankedSource]:
    # Local import to avoid a hard embeddings dependency at module load.
    from app.services.embeddings.hash_embeddings import HashEmbeddingProvider, cosine
    embed = HashEmbeddingProvider()
    qv = embed.embed(query)
    ranked: list[RankedSource] = []
    for h in hits:
        text = f"{h.title} {h.snippet} {h.content[:2000]}"
        semantic = cosine(qv, embed.embed(text[:2000]))  # embedding similarity, 0..1
        coverage = term_coverage(query, text)  # query-term recall, 0..1
        title_hit = term_coverage(query, h.title + " " + h.snippet)
        domain_bonus = 0.15 if h.domain and any(d in h.domain for d in _TRUSTED_DOMAINS) else 0.0
        quality = TRUSTED_TYPES.get(h.source_type, 0.35) * 0.8 + domain_bonus
        quality = min(1.0, quality)
        relevance = round(0.55 * semantic + 0.25 * coverage + 0.15 * title_hit + h.raw_score * 0.05, 4)
        relevance = max(0.0, min(1.0, relevance))
        ranked.append(RankedSource(hit=h, relevance=relevance, quality=round(quality, 4),
                                   breakdown={"embedding_cosine": round(semantic, 4),
                                              "query_coverage": round(coverage, 4),
                                              "title_coverage": round(title_hit, 4),
                                              "source_type_weight": TRUSTED_TYPES.get(h.source_type, 0.35),
                                              "domain_bonus": domain_bonus,
                                              "formula": "0.55*cosine + 0.25*coverage + 0.15*title + 0.05*raw"}))
    ranked.sort(key=lambda r: (r.relevance * 0.65 + r.quality * 0.35), reverse=True)
    return ranked
