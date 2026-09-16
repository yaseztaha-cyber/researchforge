# Human Evaluation

## Task

Each task shows `QUESTION, CLAIM, SOURCE, EVIDENCE` (verbatim quote). Evaluator chooses:
- **SUPPORTED** — Evidence directly supports claim
- **PARTIALLY_SUPPORTED** — Only part of claim supported or wording broader than evidence
- **UNSUPPORTED** — No support
- **CONTRADICTED** — Evidence conflicts

## Blindness

System confidence (`Claim.confidence`) is **hidden** on the task view (`GET /api/eval/human/tasks` returns claim_text + evidence only). Confidence is revealed only after labeling via `/api/eval/human/labels` + separate `/calibration` endpoint. This prevents confirmation bias.

## Storage

`evaluation_labels` table: `id, question_id, claim_id, source_id, evidence_id, run_id, label, notes, evaluator_id, created_at, evaluation_version`. Multiple evaluations per claim allowed (no overwrite). Agreement measured via `GET /api/eval/human/summary` (`multi_labeled_claims, agreed, agreement_rate`).

## Calibration

`GET /api/eval/human/calibration` returns `Brier score, ECE` when ≥5 labels with claim confidence, else `status: unavailable` (honest, never faked). See `docs/calibration.md`.

## UI

`/evaluation/human` — blind task list, label dropdown, submit, summary, calibration. See `frontend/app/evaluation/human/page.tsx`. Instructions displayed inline.

## Current Labels

As of v0.5, **no human labels yet** — calibration reports `unavailable` (expected, not a failure). Labels will be collected after recorded-live corpus is seeded.
