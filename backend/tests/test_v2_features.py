"""v0.2: conflict classification, agreement, confidence-2.0, calibration, security."""

import pytest

from app.agents.conflict_detector import agreement_summary, classify_pair, detect_conflicts
from app.core.security import SecurityError, sniff_content
from app.schemas.research import EvidenceItem
from app.services.confidence import compute_confidence
from evaluation.scripts.calibration import expected_calibration_error, reliability_report


def _ev(quote, sid="s1"):
    return EvidenceItem(claim=quote[:120], quote=quote, source_id=sid,
                        relevance_score=0.8, confidence_score=0.8)


def test_classification_defaults_to_unclear():
    cls, reason = classify_pair("Desalination needs energy input.", "Brine affects fish nearby.")
    assert cls == "unclear"
    assert "could not be established" in reason


def test_time_period_classification():
    cls, _ = classify_pair("2010 monitoring shows effects on fish.",
                           "2024 monitoring shows little effect on fish.")
    assert cls == "time_period"


def test_conflicts_carry_classification():
    ev = [_ev("Brine discharge from desalination outfalls increases salinity and harms benthic organisms near outfalls."),
          _ev("Some brine outfall studies report little measurable effect on fish beyond the mixing zone; outfall salinity declines with distance.", sid="s2")]
    conflicts = detect_conflicts(ev)
    assert conflicts
    assert all(c.classification for c in conflicts)


def test_agreement_summary_honest_note():
    a = agreement_summary([_ev("x " * 20)], [_ev("y " * 20, sid="s2")], [], ["government", "blog"])
    assert a.supporting == 1 and a.contradicting == 1
    assert "does not establish truth" in a.note


def test_confidence_v2_components():
    c = compute_confidence(evidence=[_ev("Desalination needs 3 kWh per cubic meter here")] * 6,
                           num_subquestions=3, avg_quality=0.9, conflicts=[],
                           claims_supported=4, claims_total=4,
                           claim_texts=["Desalination needs 3 kWh per cubic meter here"] * 4)
    assert c.claim_specificity >= 0.8
    assert "heuristic" in c.method
    assert c.label in ("Low", "Medium", "High")


def test_calibration_unavailable_without_labels():
    r = reliability_report()
    assert r["status"] == "unavailable"


def test_calibration_computes_with_labels():
    r = reliability_report([0.9, 0.1, 0.8], [1, 0, 1])
    assert r["status"] == "ok"
    assert 0.0 <= r["brier_score"] <= 1.0
    assert 0.0 <= r["expected_calibration_error"] <= 1.0


def test_sniff_rejects_masquerading_exe():
    with pytest.raises(SecurityError):
        sniff_content("notes.pdf", b"MZ" + b"\x00" * 100)


def test_sniff_rejects_fake_pdf():
    with pytest.raises(SecurityError):
        sniff_content("paper.pdf", b"Hello world, not a pdf")


def test_sniff_accepts_realistic_pdf_header():
    sniff_content("paper.pdf", b"%PDF-1.7 fake body")
    sniff_content("notes.md", b"# hello")
