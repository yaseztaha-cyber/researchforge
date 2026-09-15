# ResearchForge — Benchmark

## Datasets
- `questions.jsonl` (24, legacy, desalination-heavy) — retained for v0.1/v0.2 comparison.
- `questions_v03.jsonl` (60, v0.3) — 10 each: environmental, energy, biology, computer science, engineering, general science.

Each record:
```
id, category, question, subquestions, expected_topics, relevant_source_types, gold_sources, evaluation_notes
```
Gold sources are empty where no single canonical answer exists (many valid sources). `expected_topics` are relevance proxies, not required answer strings.

## Metrics
All computed by `evaluation/scripts/metrics.py` from real runs (`export.json` or `run_evaluation.py`):
- `citation_correctness` / `citation_completeness` / `unsupported_claim_rate` / `overstatement_rate`
- `retrieval_precision` (threshold 0.15) and `retrieval_recall_proxy` (relevant / expected_min)
- `source_diversity` (domains, publishers, diversity_ratio), `redundancy_rate`, `evidence_relevance`, `evidence_alignment` (quote in source), `claim_evidence_alignment`

Formulas documented in code; no single collapsed score.

## Running
```
python evaluation/scripts/run_evaluation.py --dataset evaluation/dataset/questions_v03.jsonl --out evaluation/reports/v0.3_mock.json --version 0.3.0
python evaluation/scripts/run_evaluation.py --dataset evaluation/dataset/questions.jsonl --out evaluation/reports/v0.2_mock.json --limit 24
```

## Version comparison
Reports are JSON with `aggregate` + per-run `runs`. Dashboard (`/evaluation`) lists versioned reports for v0.1 vs v0.2 vs v0.3 comparison. Do not manipulate metrics to make vN look better; if a metric regresses, report it.
