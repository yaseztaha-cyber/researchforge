"""Citation verification + formatting. Every [n] must trace Claim -> Evidence -> Source."""

from __future__ import annotations

from app.models.db_models import Evidence, Source


def build_citations(evidences: list[Evidence], sources: list[Source]) -> list[dict]:
    by_source = {s.id: s for s in sources}
    citations = []
    for i, e in enumerate(evidences, start=1):
        s = by_source.get(e.source_id)
        citations.append({"index": i, "evidence_id": e.id, "source_id": e.source_id,
                          "source_title": s.title if s else "Unknown source",
                          "url": s.url if s else None, "page": e.page, "section": e.section,
                          "quote": e.quote[:500]})
    return citations


def verify_citations(report_text: str, citations: list[dict]) -> list[str]:
    """Return issues: markers like [7] with no matching citation, or citations never referenced."""
    import re
    markers = {int(m) for m in re.findall(r"\[(\d+)\]", report_text)}
    valid = {c["index"] for c in citations}
    issues = []
    for m in sorted(markers):
        if m not in valid:
            issues.append(f"Citation [{m}] has no matching source — removed or marked insufficient evidence.")
    return issues
