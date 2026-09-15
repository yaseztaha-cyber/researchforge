# ResearchForge — Evaluation

Dataset: `evaluation/dataset/questions.jsonl` (question + expected topics + min sources).

Scripts:
- `evaluation/scripts/run_evaluation.py` — runs each question through the real pipeline
  (mock providers) and prints per-run + aggregate metrics.
- `evaluation/scripts/metrics.py <export.json>` — scores a single exported report.

Metrics: citation correctness, citation completeness, unsupported-claim rate,
retrieval precision, latency, sources/claims per run, estimated cost.
Dashboard: `/evaluation` page + `GET /api/eval/dashboard`.

All numbers are computed from actual runs. No benchmark results are hardcoded.
