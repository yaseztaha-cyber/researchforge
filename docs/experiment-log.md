# Experiment Log

## EXP-001 — Vector vs Hybrid (baseline validation)

- **ID:** EXP-001
- **Date:** 2026-09-15
- **Hypothesis:** Hybrid (0.45/0.20/0.15/0.20) outperforms pure vector or lexical on fixture-limited 60-question benchmark.
- **Configuration:** `vector_only` (1.0/0/0/0) vs `hybrid_baseline` (0.45/0.20/0.15/0.20) vs `high_lexical` (0.35/0.30/0.15/0.20)
- **Dataset:** `questions_v03.jsonl` (limit 5, categories: environmental, environmental, environmental, environmental, environmental) — mock fixtures, SQLite fallback
- **Result:** All three configs `precision 0.35, recall_proxy 0.5` (no measurable difference). See `evaluation/reports/experiments/summary.json`.
- **Decision:** **Reject** weight tuning on fixture-limited data. No change to defaults. Fixture corpus does not discriminate between strategies (all return same 4 mock sources).
- **Follow-up:** Rerun on seeded 600-chunk corpus (`seed_corpus.json`) + recorded-live fixtures when available.

## EXP-002 — SQLite vector_only latency

- **ID:** EXP-002
- **Date:** 2026-09-15
- **Hypothesis:** Vector-only retrieval is faster than hybrid due to no reranking.
- **Configuration:** `vector_only_ms 2.6` vs `hybrid_total_ms 3.7` (SQLite, 600 chunks, 5 queries)
- **Dataset:** Seeded 600-chunk corpus, hash-384, win32
- **Result:** Hybrid adds ~1.1 ms overhead (rerank + MMR). See `sqlite_vs_pgvector.json` and `performance/latest.json`.
- **Decision:** **Accept** hybrid as default (small latency cost for diversity/quality). No regression.

## General Rule

Every experiment stores `experiment_id, date, hypothesis, configuration, dataset, precision, recall, diversity, latency, cost, decision` under `evaluation/reports/experiments/`. Failed experiments are kept. No benchmark-specific hacks.
