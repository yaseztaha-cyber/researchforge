# ResearchForge — Architecture

```
[Next.js app/ + components/] --REST--> [FastAPI api/]
        polling /progress                         |
                                                  v
                                      [agents/orchestrator.py]
       planner -> researcher -> extractor -> conflict_detector -> synthesizer -> verifier
                                                  |
         +------------------+----------------------+-------------------+------------------+
         |                  |                      |                   |                  |
  services/llm/      services/retrieval/   services/documents/  services/embeddings/  services/vector_store
  (mock/api)   (mock/web/replay/docs) (parser + chunking_v3) (hash-384 + cache)  (pgvector/SQLite)
                                                   |                  |                  |
                                             hybrid_retrieval + MMR diversity            |
                                                   +------------------+-------------------+
                                                   |
                                             [citations/verifier]
                                                   v
                                      [SQLAlchemy models] -> SQLite (dev) / Postgres+pgvector (prod)
```

## Responsibilities
- **frontend/**: landing (modes + advanced settings), progress timeline with live counts,
  report+evidence split view, **claim inspector ("show me why")**, **research graph (SVG +
  list fallback)**, **evidence timeline (chronology + conflict timeline)**, why-ranked source inspector, conflict comparison, history, eval dashboard (versioned benchmarks, performance).
- **api/**: thin REST layer; research runs execute as background tasks; progress via in-memory + DB row.
  `GET .../queries` (audit), `GET .../claims/{id}/trace`, `GET .../graph`, `GET .../timeline` (source/claim/conflict chronology), `POST /documents/{id}/reindex`, `GET /documents`; rate limit on POST.
- **orchestrator**: owns stage order, modes (web/private/hybrid), stopping criteria + `stop_reason`,
  persistence, cost/latency metering (`_CountingLLM`), failure handling, run logging; document RAG via vector_store + hybrid scoring.
- **agents/**: single-responsibility stages; planner output always Pydantic-validated with rule fallback.
  researcher: parallel typed queries, canonical dedup + provenance, MMR diversity, time/cost budgets.
- **services/**: provider interfaces so vendors are swappable; scoring breakdowns + ranking reasons persisted.
  `vector_store` (pgvector/ivfflat vs SQLite brute-force), `hybrid_retrieval`, `chunking_v3`, `EmbeddingCache`, `replay_provider` (record/replay).
- **db/models**: sources (`origin`, `discovered_by`, `ranking_reasons`), `Document` (version, first/last_seen, embedding_model/dim), `DocumentChunk` (page/section/heading/char offsets/hash/embedding), legacy `SourceChunk` (compat), evidence (verbatim), claims (`sub_question`, `agreement`), reports (`research_method`), runs (`stop_reason`, `stage_ms`, usage/cost), `research_queries` audit.
- **evaluation/**: 60-question multi-domain v03 dataset (+ legacy 24), scripts computing real metrics (precision/recall/diversity/redundancy/evidence alignment) + versioned JSON reports + performance benchmarks + calibration module (honest "unavailable" without labels) + sanitized provider fixtures.
