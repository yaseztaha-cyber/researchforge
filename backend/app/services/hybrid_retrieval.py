"""Hybrid retrieval: fuses lexical, semantic, coverage, quality, and usefulness.

final_score =
  w_sem * cosine + w_lex * lexical_relevance + w_cov * query_coverage
  + w_qual * source_quality  - redundancy + diversity_bonus

Weights are configurable (env). Component scores are stored for audit
(`score_breakdown`) so the UI can explain "why ranked here".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import get_settings
from app.services.embeddings.hash_embeddings import cosine
from app.services.retrieval.base import term_coverage, token_overlap
from app.services.vector_store import ChunkHit


@dataclass
class HybridCandidate:
    hit: ChunkHit
    semantic: float
    lexical: float
    coverage: float
    quality: float
    usefulness: float
    final: float
    breakdown: dict = field(default_factory=dict)


def score_chunk(
    query: str,
    hit: ChunkHit,
    *,
    query_embedding: list[float],
    source_quality: float = 0.5,
) -> HybridCandidate:
    """Score one vector hit with hybrid weights."""
    s = get_settings()
    # semantic already computed as hit.similarity, but recompute if needed
    semantic = float(hit.similarity or 0.0)
    # lexical: token Jaccard over chunk text
    lexical = token_overlap(query, hit.text)
    coverage = term_coverage(query, hit.text)
    length_factor = min(1.0, len(hit.text or "") / 1500)
    usefulness = round(0.7 * coverage + 0.3 * length_factor, 4)
    quality = max(0.0, min(1.0, source_quality))
    final = round(
        s.HYBRID_SEMANTIC_WEIGHT * semantic
        + s.HYBRID_LEXICAL_WEIGHT * lexical
        + s.HYBRID_COVERAGE_WEIGHT * coverage
        + s.HYBRID_QUALITY_WEIGHT * quality,
        4,
    )
    breakdown = {
        "semantic_similarity": round(semantic, 4),
        "lexical_relevance": round(lexical, 4),
        "query_coverage": round(coverage, 4),
        "source_quality": round(quality, 4),
        "content_usefulness": usefulness,
        "final_score": final,
        "weights": {
            "semantic": s.HYBRID_SEMANTIC_WEIGHT,
            "lexical": s.HYBRID_LEXICAL_WEIGHT,
            "coverage": s.HYBRID_COVERAGE_WEIGHT,
            "quality": s.HYBRID_QUALITY_WEIGHT,
        },
        "formula": "final = w_sem*cosine + w_lex*lexical + w_cov*coverage + w_qual*quality",
    }
    return HybridCandidate(hit=hit, semantic=semantic, lexical=lexical, coverage=coverage,
                           quality=quality, usefulness=usefulness, final=final, breakdown=breakdown)


def rerank_and_diversify(
    query: str,
    candidates: list[HybridCandidate],
    *,
    top_k: int = 8,
    lambda_mmr: float = 0.7,
    per_doc_cap: int = 3,
) -> tuple[list[HybridCandidate], dict]:
    """Deduplicate + rerank + MMR diversity selection."""
    from app.services.embeddings.hash_embeddings import HashEmbeddingProvider
    embed = HashEmbeddingProvider()

    # Near-duplicate suppression: drop chunks with same content_hash or >0.92 cosine duplicate
    seen_hashes: set[str] = set()
    deduped: list[HybridCandidate] = []
    vecs: list[list[float]] = []
    for c in candidates:
        h = c.hit.text[:200]
        if h in seen_hashes:
            continue
        # Check near-duplicate via embedding similarity to already kept
        v = embed.embed(c.hit.text[:800])
        is_dup = any(cosine(v, pv) > 0.92 for pv in vecs)
        if is_dup:
            continue
        seen_hashes.add(h)
        deduped.append(c)
        vecs.append(v)

    # MMR + per-document cap + query-coverage diversity
    vecs = [embed.embed(c.hit.text[:800]) for c in deduped]
    selected: list[HybridCandidate] = []
    sel_idx: list[int] = []
    doc_counts: dict[str, int] = {}
    remaining = list(range(len(deduped)))
    # Sort remaining by final descending for deterministic tie-breaking
    remaining.sort(key=lambda i: deduped[i].final, reverse=True)

    while remaining and len(selected) < top_k:
        best = None
        best_score = -1.0
        for i in list(remaining):
            doc_id = deduped[i].hit.document_id or "?"
            if doc_counts.get(doc_id, 0) >= per_doc_cap:
                continue
            redundancy = max([cosine(vecs[i], vecs[j]) for j in sel_idx] or [0.0])
            cov_bonus = 0.03 if deduped[i].coverage > 0.3 else 0.0
            score = lambda_mmr * deduped[i].final - (1 - lambda_mmr) * redundancy + cov_bonus
            if score > best_score:
                best, best_score = i, score
        if best is None:
            break
        remaining.remove(best)
        sel_idx.append(best)
        selected.append(deduped[best])
        doc_id = deduped[best].hit.document_id or "?"
        doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1

    meta = {
        "candidate_count": len(candidates),
        "deduped_count": len(deduped),
        "selected_count": len(selected),
        "lambda": lambda_mmr,
        "per_doc_cap": per_doc_cap,
    }
    return selected, meta
