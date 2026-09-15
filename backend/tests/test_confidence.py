"""Unit: confidence components behave transparently."""

from app.schemas.research import EvidenceItem
from app.services.confidence import compute_confidence


def _ev():
    return EvidenceItem(claim="Desalination needs substantial energy input here",
                        quote="Desalination needs substantial energy input of several kWh per cubic meter here.",
                        source_id="s1", relevance_score=0.9, confidence_score=0.9)


def test_high_confidence_with_good_inputs():
    c = compute_confidence(evidence=[_ev()] * 6, num_subquestions=3, avg_quality=0.9,
                           conflicts=[], claims_supported=4, claims_total=4)
    assert c.label == "High"
    assert c.overall >= 0.75


def test_conflicts_lower_agreement():
    c = compute_confidence(evidence=[_ev()] * 6, num_subquestions=3, avg_quality=0.9,
                           conflicts=[object()], claims_supported=4, claims_total=4)  # type: ignore
    assert c.source_agreement < 1.0
    assert c.contradiction_level in ("Medium", "High")
