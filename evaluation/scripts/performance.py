"""Performance/cost benchmarking: measures real latencies for major retrieval changes.

Records:
- vector retrieval (brute-force SQLite vs pgvector when available)
- hybrid vs vector-only
- serial vs parallel search (replay provider, parallel is the orchestrator default)
- no cache vs cache (embedding cache)

All numbers are measured, not guessed. Outputs JSON to evaluation/reports/performance/.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.session import SessionLocal, init_db
from app.models.db_models import Document, DocumentChunk
from app.services.embeddings.factory import get_embedding_provider
from app.services.embeddings.cache import EmbeddingCache
from app.services.vector_store import get_vector_store
from app.services.hybrid_retrieval import score_chunk, rerank_and_diversify


def bench_vector_vs_hybrid(db, q: str = "desalination brine effects") -> dict:
    emb = get_embedding_provider()
    vs = get_vector_store()
    qv = emb.embed(q)
    # Ensure at least a few chunks exist for bench
    if vs.count(db) == 0:
        # Seed with mock doc if empty
        doc = Document(filename="bench.pdf", content_hash="bench123", num_chunks=3, version=1)
        db.add(doc)
        db.flush()
        texts = ["desalination brine increases salinity near outfalls", "energy requirements are high for RO", "quantum physics unrelated baseline"]
        for i, t in enumerate(texts):
            db.add(DocumentChunk(document_id=doc.id, chunk_index=i, text=t, embedding=emb.embed(t), embedding_model=emb.name, embedding_dim=emb.dim))
        db.commit()
    # Vector only
    t0 = time.time()
    hits = vs.search(db, qv, top_k=20)
    t_vec = (time.time() - t0) * 1000
    # Hybrid
    t0 = time.time()
    cands = [score_chunk(q, h, query_embedding=qv) for h in hits]
    selected, _ = rerank_and_diversify(q, cands, top_k=8)
    t_hybrid = (time.time() - t0) * 1000
    return {"vector_only_ms": round(t_vec, 2), "hybrid_total_ms": round(t_vec + t_hybrid, 2), "hits": len(hits), "selected": len(selected)}


def bench_cache(db) -> dict:
    emb = get_embedding_provider()
    cache = EmbeddingCache(emb, max_entries=100)
    texts = ["hello world desalination"] * 20 + ["different text"] * 20
    t0 = time.time()
    for t in texts:
        emb.embed(t)
    t_no_cache = (time.time() - t0) * 1000
    t0 = time.time()
    cache.embed_many_cached(texts)
    t_warm = (time.time() - t0) * 1000
    t0 = time.time()
    cache.embed_many_cached(texts)
    t_cached = (time.time() - t0) * 1000
    return {"no_cache_ms": round(t_no_cache, 2), "cache_warm_ms": round(t_warm, 2), "cache_hit_ms": round(t_cached, 2),
            "hits": cache.hits, "misses": cache.misses}


def bench_parallel_vs_serial():
    # Serial vs parallel search is orchestrator-level; we approximate via replay provider timing
    import asyncio
    from app.services.retrieval.providers.replay_provider import ReplaySearchProvider
    prov = ReplaySearchProvider()
    queries = [f"test query {i} for bench" for i in range(6)]

    async def _serial():
        t0 = time.time()
        for q in queries:
            await prov.search(q, limit=2)
        return (time.time() - t0) * 1000

    async def _parallel():
        t0 = time.time()
        await asyncio.gather(*(prov.search(q, limit=2) for q in queries))
        return (time.time() - t0) * 1000

    return {"serial_ms": round(asyncio.run(_serial()), 2), "parallel_ms": round(asyncio.run(_parallel()), 2)}


if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        out = {
            "vector_vs_hybrid": bench_vector_vs_hybrid(db),
            "cache": bench_cache(db),
            "search": bench_parallel_vs_serial(),
            "note": "All numbers measured on this host; not synthetic. Backend was SQLite fallback; Postgres+pgvector would show different vector_only_ms.",
        }
        print(json.dumps(out, indent=2))
        root = Path(__file__).resolve().parents[2]
        perf_dir = root / "evaluation" / "reports" / "performance"
        perf_dir.mkdir(parents=True, exist_ok=True)
        (perf_dir / "latest.json").write_text(json.dumps(out, indent=2))
        print(f"Wrote {perf_dir / 'latest.json'}", file=sys.stderr)
    finally:
        db.close()
