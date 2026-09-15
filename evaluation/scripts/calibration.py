"""Confidence calibration tooling (evaluation module).

Computes reliability stats (Brier score, expected calibration error) WHEN labeled
data exists: predictions + binary outcomes. With no labels it honestly reports
unavailability instead of fabricating calibration.
"""

from __future__ import annotations


def brier_score(predictions: list[float], outcomes: list[int]) -> float:
    if not predictions or len(predictions) != len(outcomes):
        raise ValueError("Need equal-length non-empty predictions and outcomes.")
    return sum((p - o) ** 2 for p, o in zip(predictions, outcomes)) / len(predictions)


def expected_calibration_error(predictions: list[float], outcomes: list[int],
                               n_bins: int = 5) -> float:
    if not predictions or len(predictions) != len(outcomes):
        raise ValueError("Need equal-length non-empty predictions and outcomes.")
    bins: list[list[int]] = [[] for _ in range(n_bins)]
    for i, p in enumerate(predictions):
        b = min(n_bins - 1, int(p * n_bins))
        bins[b].append(i)
    ece, n = 0.0, len(predictions)
    for b in bins:
        if not b:
            continue
        acc = sum(outcomes[i] for i in b) / len(b)
        conf = sum(predictions[i] for i in b) / len(b)
        ece += len(b) / n * abs(acc - conf)
    return round(ece, 4)


def reliability_report(predictions: list[float] | None = None,
                       outcomes: list[int] | None = None) -> dict:
    if not predictions or not outcomes:
        return {"status": "unavailable",
                "reason": "Calibration unavailable due to insufficient labeled benchmark data."}
    return {"status": "ok",
            "n": len(predictions),
            "brier_score": round(brier_score(predictions, outcomes), 4),
            "expected_calibration_error": expected_calibration_error(predictions, outcomes)}
