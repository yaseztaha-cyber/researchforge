# ResearchForge — Performance & Cost

## What is measured
Per-run `stage_ms` (planning, searching, filtering, extracting, analyzing, synthesizing, verifying, done), `duration_ms`, plus `search_calls`, `llm_calls`, `embedding_calls`, `estimated_cost_usd`. Stored on `ResearchRun` and shown in report's Research Method and `/api/research/{id}`.

## Benchmarks
Run `python evaluation/scripts/performance.py` — outputs to `evaluation/reports/performance/latest.json`:
```
vector_only_ms, hybrid_total_ms,
no_cache_ms vs cache_warm_ms vs cache_hit_ms,
serial_ms vs parallel_ms
```
Current SQLite fallback numbers (this host): `vector_only 2.6 ms, hybrid 3.7 ms, cache_hit 0.07 ms` (see file). Postgres+pgvector would show different `vector_only_ms` but same API.

## Budgets & partial results
Configurable `max research time`, `max sources/queries/model calls/embedding calls/cost`. When a budget is hit, `stop_reason` says `"Research stopped because ..."` and `status: partial` with available evidence — not `"Research completed"`.

## Acceptance
No arbitrary impossible thresholds. Compare `baseline` vs `optimized` for each change and only call it an improvement if measured.
