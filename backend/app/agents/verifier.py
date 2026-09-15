"""Claim verifier: downgrades or rejects claims the evidence does not support."""

from __future__ import annotations

import re

from app.schemas.research import EvidenceItem, VerificationResult

OVERSTATEMENT = [r"\bproves?\b", r"\bdefinitively\b", r"\ball\b", r"\bnever\b", r"\balways\b",
                 r"\bcauses\b"]
CAUSAL = re.compile(r"\bcaus\w*")
CORREL = re.compile(r"\b(correlat\w*|associat\w*|linked)\b")


def verify_claim(claim_text: str, evidence: list[EvidenceItem]) -> VerificationResult:
    if not evidence:
        return VerificationResult(claim=claim_text, supported=False, confidence=0.0,
                                  evidence_ids=[], issues=["No supporting evidence found."])
    issues: list[str] = []
    low = claim_text.lower()
    for pat in OVERSTATEMENT:
        if re.search(pat, low):
            # allow if evidence itself contains the same strong word
            if not any(re.search(pat, e.quote.lower()) for e in evidence):
                issues.append(f"Claim uses strong wording ({pat.strip(chr(92)+'b')}) not present in evidence.")
    if CAUSAL.search(low) and any(CORREL.search(e.quote.lower()) for e in evidence):
        if not any(CAUSAL.search(e.quote.lower()) for e in evidence):
            issues.append("Source mentions correlation, but generated text states causation.")
    # grounding: claim keywords should appear in at least one quote
    keywords = [w for w in re.findall(r"[a-z]{4,}", low) if w not in
                {"that", "with", "from", "this", "evidence", "effects", "effect"}][:6]
    grounded = sum(1 for e in evidence if sum(k in e.quote.lower() for k in keywords) >= 2)
    if grounded == 0:
        issues.append("Claim keywords do not overlap supporting passages; possible drift.")
    supported = len(issues) == 0
    conf = round(min(0.95, sum(e.confidence_score for e in evidence) / len(evidence)
                     * (1.0 if supported else 0.5)), 3)
    return VerificationResult(claim=claim_text, supported=supported, confidence=conf,
                              evidence_ids=[e.source_id for e in evidence], issues=issues)
