# ResearchForge — Architecture

```
[Next.js app/ + components/] --REST--> [FastAPI api/]
        polling /progress                         |
                                                  v
                                      [agents/orchestrator.py]
       planner -> researcher -> extractor -> conflict_detector -> synthesizer -> verifier
                                                  |
        +------------------+----------------------+-------------------+
        |                  |                      |                   |
 services/llm/      services/retrieval/   services/documents/  services/embeddings/
 (mock/api)          (mock/web/docs)       (pdf/txt/md)          (hash-384)
                                                  |
                                            [citations/verifier]
                                                  v
                                     [SQLAlchemy models] -> SQLite (dev) / Postgres+pgvector (prod)
```

## Responsibilities
- **frontend/**: landing, progress timeline, report+evidence split view, inspector, history, eval dashboard.
- **api/**: thin REST layer; research runs execute as background tasks; progress via in-memory + DB row.
- **orchestrator**: owns stage order, stopping criteria, persistence, failure handling, run logging.
- **agents/**: single-responsibility stages; planner output always Pydantic-validated with rule fallback.
- **services/**: provider interfaces so vendors are swappable; scoring breakdowns persisted.
- **db/models**: sources, chunks (embeddings), evidence (verbatim), claims, reports, runs.
- **evaluation/**: dataset + scripts computing real metrics from real runs.
