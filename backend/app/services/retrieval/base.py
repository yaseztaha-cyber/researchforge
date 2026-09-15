"""Search provider interface + transparent quality model v2.

Every ranked source exposes interpretable components — never one magic number:

  semantic_relevance  embedding cosine(query, title+snippet+content)
  query_coverage      fraction of query terms present (recall-oriented)
  source_quality      type weight + domain signals + recency
  content_usefulness  coverage blended with substantive-length factor

  final = 0.50*relevance + 0.30*quality + 0.20*usefulness
  where relevance = 0.55*semantic + 0.25*coverage + 0.15*title + 0.05*provider_raw

The exact formula is stored per source (score_breakdown) and shown in the UI as
"Why did this source rank here?". Business logic never touches a vendor SDK.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

RANKING_FORMULA = "final = 0.50*relevance + 0.30*quality + 0.20*usefulness; relevance = 0.55*cosine + 0.25*coverage + 0.15*title + 0.05*raw"

TRUSTED_TYPES = {"government": 0.95, "academic": 0.93, "peer_reviewed": 0.94, "scientific": 0.92,
                 "scientific_institution": 0.90, "university": 0.90, "institutional": 0.82,
                 "technical_documentation": 0.80, "news": 0.55, "blog": 0.40, "forum": 0.30,
                 "unknown": 0.35}

_TRUSTED_DOMAINS = (".gov", ".edu", ".ac.", "who.int", "un.org", "nature.com", "science.org",
                    "nih.gov", "noaa.gov", "epa.gov", "iea.org", "ipcc.ch", "unesco.org",
                    "europa.eu", "oecd.org", "worldbank.org")
_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                    "gclid", "fbclid", "msclkid", "ref", "sessionid"}


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


def canonicalize_url(url: str | None) -> str | None:
    """Normalize for dedup: lowercase host, drop tracking params/fragment/index pages."""
    if not url or url.startswith("mock://"):
        return url
    try:
        p = urlparse(url.strip())
        host = (p.hostname or "").lower()
        if host.startswith("m."):
            host = host[2:]
        if host.startswith("www."):
            host = host[4:]
        params = [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in _TRACKING_PARAMS]
        path = p.path.rstrip("/") or "/"
        netloc = host + (f":{p.port}" if p.port not in (None, 80, 443) else "")
        return urlunparse((p.scheme.lower(), netloc, path, "", urlencode(params), ""))
    except Exception:
        return url


def classify_source(url: str | None, publisher: str | None, hint: str = "unknown") -> tuple[str, list[str]]:
    """Source-type classification with recorded reasons. A signal, not a verdict."""
    text = f"{url or ''} {publisher or ''}".lower()
    reasons: list[str] = []
    if ".gov" in text or "government" in text or "environmental protection agency" in text:
        reasons.append("official government domain/publisher")
        return "government", reasons
    if any(k in text for k in ("doi.org", "nature.com", "science.org", "peer-review", "journal")):
        reasons.append("peer-reviewed venue metadata")
        return "peer_reviewed", reasons
    if ".edu" in text or ".ac." in text or "university" in text:
        reasons.append("academic institution domain")
        return "university", reasons
    if any(k in text for k in ("who.int", "un.org", "unesco", "ipcc", "academy", "institute")):
        reasons.append("recognized scientific/institutional publisher")
        return "scientific_institution", reasons
    if hint in TRUSTED_TYPES and hint != "unknown":
        reasons.append(f"provider-reported type: {hint}")
        return hint, reasons
    reasons.append("provenance could not be established")
    return "unknown", reasons


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
    usefulness: float
    final: float
    breakdown: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


def rank_hits(query: str, hits: list[SearchHit]) -> list[RankedSource]:
    # Local import to avoid a hard embeddings dependency at module load.
    from app.services.embeddings.hash_embeddings import HashEmbeddingProvider, cosine
    embed = HashEmbeddingProvider()
    qv = embed.embed(query)
    ranked: list[RankedSource] = []
    for h in hits:
        text = f"{h.title} {h.snippet} {h.content[:2000]}"
        semantic = cosine(qv, embed.embed(text[:2000]))
        coverage = term_coverage(query, text)
        title_hit = term_coverage(query, h.title + " " + h.snippet)
        relevance = round(0.55 * semantic + 0.25 * coverage + 0.15 * title_hit + h.raw_score * 0.05, 4)

        stype, type_reasons = classify_source(h.url, h.publisher, h.source_type)
        h.source_type = stype  # normalize to classified type
        type_w = TRUSTED_TYPES.get(stype, 0.35)
        domain_bonus = 0.12 if h.domain and any(d in h.domain for d in _TRUSTED_DOMAINS) else 0.0
        recency = 0.5  # neutral: most web results lack reliable dates; never invent one
        quality = round(min(1.0, 0.60 * type_w + 0.25 * (0.5 + domain_bonus * 2) + 0.15 * recency), 4)

        length_factor = min(1.0, len(h.content or "") / 2000)
        usefulness = round(0.7 * coverage + 0.3 * length_factor, 4)
        final = round(0.50 * relevance + 0.30 * quality + 0.20 * usefulness, 4)

        reasons = list(type_reasons)
        if domain_bonus:
            reasons.append("trusted-domain bonus (official/academic venue)")
        if coverage >= 0.4:
            reasons.append(f"high query-term coverage ({coverage:.0%})")
        elif coverage < 0.15:
            reasons.append(f"low query-term coverage ({coverage:.0%}) — ranked on semantic similarity")
        if length_factor >= 0.5:
            reasons.append("substantive retrievable content")
        else:
            reasons.append("thin content — snippet only")
        reasons.append("publication date unavailable; recency scored neutral")
        ranked.append(RankedSource(hit=h, relevance=relevance, quality=quality,
                                   usefulness=usefulness, final=final,
                                   breakdown={"semantic_relevance": round(semantic, 4),
                                              "query_coverage": round(coverage, 4),
                                              "title_coverage": round(title_hit, 4),
                                              "source_quality": quality,
                                              "source_type_weight": type_w,
                                              "domain_bonus": domain_bonus,
                                              "recency": recency,
                                              "content_usefulness": usefulness,
                                              "formula": RANKING_FORMULA},
                                   reasons=reasons))
    ranked.sort(key=lambda r: r.final, reverse=True)
    return ranked


def select_diverse(ranked: list[RankedSource], k: int, *, per_domain_cap: int = 2,
                   mmr_lambda: float = 0.7) -> list[RankedSource]:
    """MMR-style selection: relevance minus redundancy penalty + per-domain cap.

    Prevents ten near-identical sources from crowding out a primary paper,
    a government report, and an independent review.
    """
    from app.services.embeddings.hash_embeddings import HashEmbeddingProvider, cosine
    embed = HashEmbeddingProvider()
    vecs = [embed.embed(f"{r.hit.title} {r.hit.content[:800]}") for r in ranked]
    selected: list[RankedSource] = []
    sel_idx: list[int] = []
    domain_counts: dict[str, int] = {}
    remaining = list(range(len(ranked)))
    while remaining and len(selected) < k:
        best, best_score = None, -1.0
        for i in remaining:
            dom = ranked[i].hit.domain or "?"
            if domain_counts.get(dom, 0) >= per_domain_cap:
                continue
            redundancy = max([cosine(vecs[i], vecs[j]) for j in sel_idx] or [0.0])
            # bonus for source-type diversity: prefer types not yet selected
            have_types = {ranked[j].hit.source_type for j in sel_idx}
            div_bonus = 0.05 if ranked[i].hit.source_type not in have_types else 0.0
            score = mmr_lambda * ranked[i].final - (1 - mmr_lambda) * redundancy + div_bonus
            if score > best_score:
                best, best_score = i, score
        if best is None:
            break
        remaining.remove(best)
        sel_idx.append(best)
        selected.append(ranked[best])
        dom = ranked[best].hit.domain or "?"
        domain_counts[dom] = domain_counts.get(dom, 0) + 1
    return selected
