"""Transparent confidence: component scores stored so confidence is explainable."""

from __future__ import annotations

from app.schemas.research import ConfidenceBreakdown, ConflictItem, EvidenceItem


def compute_confidence(*, evidence: list[EvidenceItem], num_subquestions: int,
                       avg_quality: float, conflicts: list[ConflictItem],
                       claims_supported: int, claims_total: int) -> ConfidenceBreakdown:
    coverage = min(1.0, len(evidence) / max(1, num_subquestions * 2))
    agreement = 1.0 if not conflicts else max(0.0, 1.0 - 0.25 * len(conflicts))
    contradiction = "Low" if not conflicts else ("Medium" if len(conflicts) == 1 else "High")
    citation_completeness = (claims_supported / claims_total) if claims_total else 0.0
    quality = max(0.0, min(1.0, avg_quality))
    overall = round(0.3 * coverage + 0.25 * quality + 0.2 * agreement + 0.25 * citation_completeness, 3)
    label = "High" if overall >= 0.75 else ("Medium" if overall >= 0.45 else "Low")
    return ConfidenceBreakdown(overall=overall, label=label, evidence_coverage=round(coverage, 3),
                               source_agreement=round(agreement, 3), source_quality=round(quality, 3),
                               contradiction_level=contradiction,
                               citation_completeness=round(citation_completeness, 3))
