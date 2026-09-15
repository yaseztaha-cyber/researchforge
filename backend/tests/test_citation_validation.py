"""Unit: citation verification catches dangling markers; verifier flags overstatement."""

from app.agents.verifier import verify_claim
from app.schemas.research import EvidenceItem
from app.services.citations.verifier import build_citations, verify_citations


def _ev(quote, claim="Desalination needs energy"):
    return EvidenceItem(claim=claim, quote=quote, source_id="s1",
                        relevance_score=0.8, confidence_score=0.8)


def test_causation_overstatement_flagged():
    v = verify_claim("X causes Y in all cases",
                     [_ev("X is correlated with Y in some samples.")])
    assert v.supported is False
    assert any("causation" in i.lower() for i in v.issues)


def test_supported_claim_passes():
    v = verify_claim("Desalination requires substantial energy input",
                     [_ev("Desalination requires substantial energy input of 3 to 6 kWh per cubic meter.")])
    assert v.supported is True


def test_dangling_citation_detected():
    issues = verify_citations("Finding text [1][7]", [{"index": 1}])
    assert any("[7]" in i for i in issues)
    assert verify_citations("Finding [1]", [{"index": 1}]) == []
