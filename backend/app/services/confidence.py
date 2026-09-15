"""Transparent confidence v2: component scores stored so confidence is explainable.

Formula (heuristic — NOT a calibrated probability):
  overall = 0.25*coverage + 0.20*quality + 0.15*agreement
          + 0.20*citation_completeness + 0.10*specificity - 0.10*contradiction_penalty
Labels: High >= 0.75, Medium >= 0.45, else Low. Never display false precision.
"""

from __future__ import annotations

import re

from app.schemas.research import ConfidenceBreakdown, ConflictItem, EvidenceItem

_SPECIFIC = re.compile(r"\d|%|mg/l|kwh|km|page \d", re.IGNORECASE)


def claim_specificity(claim_text: str) -> float:
    """Concrete claims (numbers, units, named entities) score higher than vague ones."""
    if _SPECIFIC.search(claim_text):
        return 0.9
    if len(claim_text.split()) >= 12:
        return 0.65
    return 0.4


def compute_confidence(*, evidence: list[EvidenceItem], num_subquestions: int,
                       avg_quality: float, conflicts: list[ConflictItem],
                       claims_supported: int, claims_total: int,
                       claim_texts: list[str] | None = None) -> ConfidenceBreakdown:
    coverage = min(1.0, len(evidence) / max(1, num_subquestions * 2))
    agreement = 1.0 if not conflicts else max(0.0, 1.0 - 0.25 * len(conflicts))
    contradiction = "Low" if not conflicts else ("Medium" if len(conflicts) == 1 else "High")
    penalty = 0.0 if not conflicts else (0.3 if len(conflicts) == 1 else 0.6)
    citation_completeness = (claims_supported / claims_total) if claims_total else 0.0
    quality = max(0.0, min(1.0, avg_quality))
    specificity = 0.5
    if claim_texts:
        specificity = round(sum(claim_specificity(c) for c in claim_texts) / len(claim_texts), 3)
    overall = round(0.25 * coverage + 0.20 * quality + 0.15 * agreement
                    + 0.20 * citation_completeness + 0.10 * specificity
                    - 0.10 * penalty, 3)
    overall = max(0.0, min(1.0, overall))
    label = "High" if overall >= 0.75 else ("Medium" if overall >= 0.45 else "Low")
    return ConfidenceBreakdown(overall=overall, label=label, evidence_coverage=round(coverage, 3),
                               source_agreement=round(agreement, 3), source_quality=round(quality, 3),
                               contradiction_level=contradiction,
                               citation_completeness=round(citation_completeness, 3),
                               claim_specificity=specificity,
                               contradiction_penalty=round(penalty, 3))
