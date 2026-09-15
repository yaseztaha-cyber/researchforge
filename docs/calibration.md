# ResearchForge — Confidence & Calibration

## Heuristic confidence (implemented)
Confidence is **not** a calibrated probability. Formula:
```
overall = 0.25*coverage + 0.20*quality + 0.15*agreement + 0.20*citation + 0.10*specificity - 0.10*contradiction_penalty
labels: High ≥0.75, Medium ≥0.45 else Low
```
Components: `evidence_coverage`, `source_agreement`, `source_quality`, `contradiction_level`, `citation_completeness`, `claim_specificity`, `contradiction_penalty` + `method` string stored per report.

## Calibration infrastructure
- Labeled dataset schema: `claim, predicted_confidence, actual_supported (0/1 or supported/partially_supported/unsupported/contradicted), label_source, evaluation_version`.
- Metrics: `Brier score`, `Expected Calibration Error (ECE, 5 bins)`, reliability curves (evaluation/scripts/calibration.py).
- Behavior: `reliability_report(predictions, outcomes)` returns `{status: "unavailable", reason: "Calibration not available..."}` when insufficient labels; no fake calibration is ever shown. Evaluation dashboard and report both surface this status honestly.

## UI
Report shows `Confidence: HIGH` plus component breakdown (`Evidence coverage: High` …). No chain-of-thought is exposed.
