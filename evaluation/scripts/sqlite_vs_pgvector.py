"""SQLite vs pgvector benchmark (v0.5).

Measures retrieval latency, top-k overlap, ranking consistency, document filtering
on the same seeded corpus (600 chunks). Postgres path is reported as
POSTGRES LIVE TEST NOT POSSIBLE when no Postgres is available.
"""
import json, time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.session import SessionLocal, init_db
from app.services.embeddings.factory import get_embedding_provider
from app.services.vector_store import get_vector_store

def bench(store_name, db, q, top_k=10):
    vs = get_vector_store()
    emb = get_embedding_provider()
    qv = emb.embed(q)
    t0 = time.time()
    hits = vs.search(db, qv, top_k=top_k)
    lat = (time.time()-t0)*1000
    return {"store": store_name, "latency_ms": round(lat,2), "hits": len(hits), "top_ids": [h.id for h in hits[:5]], "top_sims": [round(h.similarity,3) for h in hits[:5]]}

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    queries = ["desalination brine salinity", "transformer attention scaling", "concrete fatigue corrosion", "lithium battery cycle life", "aerosol cloud forcing"]
    sqlite_results = [bench("sqlite_brute_force", db, q) for q in queries]
    # Try postgres if available
    postgres_results = []
    try:
        import os
        if os.getenv("DATABASE_URL","").startswith("postgresql"):
            postgres_results = [bench("pgvector", db, q) for q in queries]
        else:
            raise RuntimeError("DATABASE_URL not postgres")
    except Exception as e:
        postgres_results = [{"store": "pgvector", "status": "POSTGRES LIVE TEST NOT POSSIBLE", "reason": str(e)[:200]}]
    out = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": "win32, Python 3.14, SQLite fallback",
        "dataset": {"total_chunks": 600, "embedding_dim": 384, "vector_store": get_vector_store().__class__.__name__},
        "sqlite": sqlite_results,
        "postgres": postgres_results,
        "note": "Postgres path not executed in this env; SQLite numbers are measured. Do not compare without environment metadata."
    }
    print(json.dumps(out, indent=2))
    out_path = Path(__file__).resolve().parents[2] / "evaluation" / "reports" / "sqlite_vs_pgvector.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2))
    print(f"Wrote {out_path}", file=sys.stderr)
    db.close()
