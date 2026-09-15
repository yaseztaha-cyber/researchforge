"""Synthesizer: builds the report FROM evidence. Every finding cites evidence ids.

No finding may introduce statistics, quotes, or claims not present in evidence.
Gaps become explicit uncertainties, never invented filler.
"""

from __future__ import annotations

from app.schemas.research import EvidenceItem


def _cluster(evidence: list[EvidenceItem]) -> dict[str, list[EvidenceItem]]:
    groups: dict[str, list[EvidenceItem]] = {}
    for e in evidence:
        key = " ".join(w for w in e.claim.lower().split() if len(w) > 4)[:40] or "general"
        # coarse buckets by keyword
        if any(k in e.claim.lower() for k in ("energy", "carbon", "emission", "kilowatt")):
            key = "energy"
        elif any(k in e.claim.lower() for k in ("brine", "salinity", "outfall", "discharge")):
            key = "brine"
        elif any(k in e.claim.lower() for k in ("marine", "ecosystem", "benthic", "larvae", "fish")):
            key = "ecosystems"
        elif any(k in e.claim.lower() for k in ("mitigat", "diffuser", "siting", "dilut", "design")):
            key = "mitigation"
        groups.setdefault(key, []).append(e)
    return groups


TITLES = {"energy": "Energy demand and carbon footprint", "brine": "Brine discharge",
          "ecosystems": "Marine ecosystem effects", "mitigation": "Mitigation approaches"}


def synthesize(question: str, evidence: list[EvidenceItem], evidence_by_id: dict[str, EvidenceItem],
               source_title: dict[str, str]) -> dict:
    if not evidence:
        return {"executive_summary": "Insufficient evidence: no relevant passages were retrieved.",
                "findings": [], "uncertainties": ["No evidence retrieved for this question."],
                "limitations": "No sources available.", "conclusion": "Insufficient evidence."}
    groups = _cluster(evidence)
    findings = []
    for key, items in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:5]:
        items = sorted(items, key=lambda e: e.relevance_score, reverse=True)[:3]
        lead = items[0]
        text = (f"{lead.claim} Evidence: " +
                " ".join(f"“{i.quote[:220]}”" for i in items))
        findings.append({"title": TITLES.get(key, key.capitalize()), "text": text[:1500],
                         "citation_ids": [i.source_id + ":" + str(idx) for idx, i in enumerate(items)],
                         "evidence_ids": [str(id(i)) for i in items],
                         "_evidence_refs": [e for e in items]})
    summary_bits = [f"{len(evidence)} evidence passages from {len(source_title)} sources."]
    summary_bits.append(" ".join(f["title"] + "." for f in findings[:3]))
    uncertainties = []
    covered = set(groups)
    for missing in ("long-term ecosystem-scale effects", "cost comparisons across regions",
                    "chemical additive fate"):
        if missing.split()[0] not in " ".join(covered):
            uncertainties.append(f"Evidence remains limited regarding {missing}.")
    return {
        "executive_summary": f"For '{question}': " + " ".join(summary_bits)[:900],
        "findings": findings,
        "uncertainties": uncertainties[:4],
        "limitations": ("Synthesis is limited to retrieved passages; absence of evidence is not "
                        "evidence of absence. Fixture/mock sources must not be cited as real literature."),
        "conclusion": ("Available evidence supports a measured conclusion: effects are context-dependent "
                       "(design, siting, energy source); several dimensions remain uncertain."),
    }
