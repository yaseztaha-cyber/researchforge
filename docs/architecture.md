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
- **frontend/**: landing (modes + advanced settings), progress timeline with live counts,
  report+evidence split view, **claim inspector ("show me why")**, **research graph (SVG +
  list fallback)**, why-ranked source inspector, conflict comparison, history, eval dashboard.
- **api/**: thin REST layer; research runs execute as background tasks; progress via in-memory + DB row.
  New: `GET .../queries` (audit), `GET .../claims/{id}/trace`, `GET .../graph`; rate limit on POST.
- **orchestrator**: owns stage order, modes (web/private/hybrid), stopping criteria + `stop_reason`,
  persistence, cost/latency metering (`_CountingLLM`), failure handling, run logging.
- **agents/**: single-responsibility stages; planner output always Pydantic-validated with rule fallback.
  researcher: parallel typed queries, canonical dedup + provenance, MMR diversity, time budget.
- **services/**: provider interfaces so vendors are swappable; scoring breakdowns + ranking reasons persisted.
- **db/models**: sources (`origin`, `discovered_by`, `ranking_reasons`), chunks (embeddings),
  evidence (verbatim), claims (`sub_question`, `agreement`), reports (`research_method`),
  runs (`stop_reason`, `stage_ms`, usage/cost), `research_queries` audit.
- **evaluation/**: 24-question multi-domain dataset + scripts computing real metrics from real
  runs + versioned JSON reports + calibration module (honest "unavailable" without labels).
