"""Conflict detector v2: structured disagreement classification.

Keeps the v0.1 heuristic signals but only labels a disagreement what the
evidence actually supports. Default classification is "unclear" with the
explicit message "Reason for disagreement could not be established from the
available evidence." — never a hallucinated explanation.
"""

from __future__ import annotations

import re

from app.schemas.research import AgreementSummary, ConflictItem, EvidenceItem

_A = [r"\bincreas", r"\bharm", r"\bthreat", r"\bsignificant effect", r"\bsubstantial",
      r"\bhigh\b.*\b(risk|impact|emission)"]
_B = [r"\blittle .*effect", r"\bno .*effect", r"\bminimal", r"\bnegligible", r"\bunclear",
      r"\blimited evidence", r"\bdeclin.*with distance", r"\bbeyond.*mixing zone"]

_TIME = re.compile(r"\b(19\d{2}|20\d{2}|recent|long-term|short-term|decade)\b", re.IGNORECASE)
_METHOD = re.compile(r"\b(model|survey|monitor|sampl|experiment|meta-analys|/review|assess)\w*\b", re.IGNORECASE)
_MEASURE = re.compile(r"\b(mortalit|abundance|diversity|concentration|salinity|emission|kwh|mg/l|percent|%)\b", re.IGNORECASE)
_POP = re.compile(r"\b(population|species|community|children|adults|region|country|coastal|offshore)\b", re.IGNORECASE)
_SCOPE_WORDS = re.compile(r"\b(local|regional|global|near-field|far-field|mixing zone|ecosystem)\b", re.IGNORECASE)


def _side(text: str) -> str | None:
    t = text.lower()
    a = any(re.search(p, t) for p in _A)
    b = any(re.search(p, t) for p in _B)
    if a and not b:
        return "concern"
    if b and not a:
        return "limited-effect"
    return None


def classify_pair(a: str, b: str) -> tuple[str, str]:
    """Conservative classification: specific labels only with textual cues on BOTH sides."""
    ta, tb = a.lower(), b.lower()
    shared_time = set(_TIME.findall(ta)) & set(_TIME.findall(tb))
    if shared_time:
        # same period mentioned but positions differ -> likely measurement/method, not time
        pass
    times_a, times_b = set(_TIME.findall(ta)), set(_TIME.findall(tb))
    if times_a and times_b and not (times_a & times_b):
        return "time_period", "Sources cite different time periods."
    meth_a, meth_b = set(_METHOD.findall(ta)), set(_METHOD.findall(tb))
    if meth_a and meth_b and not (meth_a & meth_b):
        return "methodological", "Sources appear to use different methods."
    meas_a, meas_b = set(_MEASURE.findall(ta)), set(_MEASURE.findall(tb))
    if meas_a and meas_b and not (meas_a & meas_b):
        return "measurement", "Sources measure different outcomes."
    pop_a, pop_b = set(_POP.findall(ta)), set(_POP.findall(tb))
    if pop_a and pop_b and not (pop_a & pop_b):
        return "population", "Sources study different populations or settings."
    scope_a, scope_b = set(_SCOPE_WORDS.findall(ta)), set(_SCOPE_WORDS.findall(tb))
    if scope_a and scope_b and not (scope_a & scope_b):
        return "scope", "Sources address different spatial scopes."
    if "insufficient" in ta + tb or "understudied" in ta + tb or "limited evidence" in ta + tb:
        return "insufficient_evidence", "At least one side notes limited evidence."
    # Direct contradiction requires explicit negation of the same proposition.
    if re.search(r"\b(no|not|never|fails to)\b", tb) and len(set(ta.split()) & set(tb.split())) > 6:
        return "direct_contradiction", "Sources make opposing claims about the same proposition."
    return ("unclear",
            "Reason for disagreement could not be established from the available evidence.")


def detect_conflicts(evidence: list[EvidenceItem]) -> list[ConflictItem]:
    concerns = [e for e in evidence if _side(e.quote) == "concern"]
    limited = [e for e in evidence if _side(e.quote) == "limited-effect"]
    conflicts: list[ConflictItem] = []
    for c in concerns[:4]:
        c_toks = {w for w in re.findall(r"[a-z]{4,}", c.quote.lower())}
        ranked = sorted(limited, key=lambda l: len(
            c_toks & set(re.findall(r"[a-z]{4,}", l.quote.lower()))), reverse=True)
        for l in ranked[:2]:
            shared = c_toks & set(re.findall(r"[a-z]{4,}", l.quote.lower()))
            if len(shared) < 2:
                continue
            cls, reason = classify_pair(c.quote, l.quote)
            conflicts.append(ConflictItem(
                topic="Magnitude / spatial extent of effects",
                position_a=c.quote[:400], source_a=c.source_id,
                position_b=l.quote[:400], source_b=l.source_id,
                possible_reason=reason, classification=cls))
            if len(conflicts) >= 3:
                return conflicts
    return conflicts


def agreement_summary(supporting: list[EvidenceItem], contradicting: list[EvidenceItem],
                      neutral: list[EvidenceItem], source_types: list[str]) -> AgreementSummary:
    n_sup, n_con, n_neu = len(supporting), len(contradicting), len(neutral)
    total = max(1, n_sup + n_con + n_neu)
    diversity = len(set(source_types)) / max(1, len(source_types))
    return AgreementSummary(
        supporting=n_sup, contradicting=n_con, neutral=n_neu,
        support_ratio=round(n_sup / total, 3), source_diversity=round(diversity, 3))
