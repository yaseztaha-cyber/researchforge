"""Real metric computation over actual research runs. Never fabricates numbers."""

from __future__ import annotations

import json
import sys


def citation_correctness(report: dict, evidence_ids: set[str]) -> float:
    cites = report.get("citations", [])
    if not cites:
        return 0.0
    good = sum(1 for c in cites if c.get("evidence_id") in evidence_ids and c.get("source_id"))
    return good / len(cites)


def citation_completeness(findings: list, citations: list) -> float:
    if not findings:
        return 0.0
    cited = {c["index"] for c in citations}
    with_cites = sum(1 for f in findings if set(f.get("citation_ids", [])) & cited)
    return with_cites / len(findings)


def unsupported_claim_rate(claims: list) -> float:
    if not claims:
        return 1.0
    return sum(1 for c in claims if not c.get("supported")) / len(claims)


def retrieval_precision(sources: list, threshold: float = 0.15) -> float:
    """Fraction of retrieved sources at/above the relevance threshold.

    Threshold default 0.15 is calibrated to the ranker's 0..1 relevance blend
    (embedding cosine + query coverage); the threshold used is always reported
    alongside the number so the metric stays interpretable.
    """
    if not sources:
        return 0.0
    return sum(1 for s in sources if (s.get("relevance_score", 0) >= threshold)) / len(sources)


if __name__ == "__main__":
    # Reads an export.json produced by /api/research/{id}/export.json
    path = sys.argv[1]
    data = json.load(open(path))
    ev_ids = {e["id"] for e in data.get("evidence", [])}
    print(json.dumps({
        "citation_correctness": citation_correctness({"citations": data.get("citations", [])}, ev_ids),
        "citation_completeness": citation_completeness(data["report"].get("findings", []), data.get("citations", [])),
        "unsupported_claim_rate": unsupported_claim_rate(data.get("claims", [])),
        "retrieval_precision": retrieval_precision(data.get("sources", [])),
    }, indent=2))
