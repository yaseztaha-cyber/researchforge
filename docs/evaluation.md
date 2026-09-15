# ResearchForge — Evaluation

Dataset: `evaluation/dataset/questions.jsonl` — 24 questions across environment,
energy, biology, climate, engineering, health, technology, history, computer
science, education. Each row: question + domain + expected topics + min sources.
(No fabricated expected answers; topics are retrieval-relevance criteria.)

Scripts:
- `evaluation/scripts/run_evaluation.py [--out report.json] [--limit N] [--version X]` —
  runs each question through the real pipeline (mock providers) and prints/writes
  per-run + aggregate metrics incl. latency, sources/claims counts, search/LLM
  calls, estimated cost. Reports are versioned JSON under `evaluation/reports/`.
- `evaluation/scripts/metrics.py <export.json>` — scores a single exported report.
- `evaluation/scripts/calibration.py` — Brier score / ECE when labels exist;
  otherwise honestly reports "unavailable".

Metrics: citation correctness, citation completeness, unsupported-claim rate,
retrieval precision, latency, sources/claims per run, estimated cost.
Dashboard: `/evaluation` page + `GET /api/eval/dashboard` (live DB metrics,
confidence distribution, cost, per-mode breakdown, versioned benchmark table).

All numbers are computed from actual runs. No benchmark results are hardcoded.
Known honest caveat: fixtures cover desalination only, so off-domain benchmark
questions score low retrieval precision in mock mode (v0.2 full-set: 0.35;
desalination subset: 0.69, matching v0.1's 0.69).
