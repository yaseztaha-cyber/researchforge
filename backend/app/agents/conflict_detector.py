"""Conflict detector: surfaces disagreements instead of silently picking a side."""

from __future__ import annotations

import re

from app.schemas.research import ConflictItem, EvidenceItem

_A = [r"\bincreas", r"\bharm", r"\bthreat", r"\bsignificant effect", r"\bsubstantial",
      r"\bhigh\b.*\b(risk|impact|emission)"]
_B = [r"\blittle .*effect", r"\bno .*effect", r"\bminimal", r"\bnegligible", r"\bunclear",
      r"\blimited evidence", r"\bdeclin.*with distance", r"\bbeyond.*mixing zone"]


def _side(text: str) -> str | None:
    t = text.lower()
    a = any(re.search(p, t) for p in _A)
    b = any(re.search(p, t) for p in _B)
    if a and not b:
        return "concern"
    if b and not a:
        return "limited-effect"
    return None


def detect_conflicts(evidence: list[EvidenceItem]) -> list[ConflictItem]:
    concerns = [e for e in evidence if _side(e.quote) == "concern"]
    limited = [e for e in evidence if _side(e.quote) == "limited-effect"]
    conflicts: list[ConflictItem] = []
    for c in concerns[:4]:
        # Only pair passages that actually discuss the same topic (token overlap),
        # otherwise an energy sentence would be "contrasted" with a brine sentence.
        c_toks = {w for w in re.findall(r"[a-z]{4,}", c.quote.lower())}
        ranked = sorted(limited, key=lambda l: len(
            c_toks & set(re.findall(r"[a-z]{4,}", l.quote.lower()))), reverse=True)
        for l in ranked[:2]:
            shared = c_toks & set(re.findall(r"[a-z]{4,}", l.quote.lower()))
            if len(shared) < 2:
                continue
            conflicts.append(ConflictItem(
                topic="Magnitude / spatial extent of effects",
                position_a=c.quote[:400], source_a=c.source_id,
                position_b=l.quote[:400], source_b=l.source_id,
                possible_reason=("different outfall designs, time periods, or measurement criteria; "
                                 "reason unclear in several comparisons.")))
            if len(conflicts) >= 3:
                return conflicts
    return conflicts
