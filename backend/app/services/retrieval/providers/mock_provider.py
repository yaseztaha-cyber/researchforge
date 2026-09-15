"""Deterministic mock search: curated fixtures, clearly labeled mock:// URLs.

Production rule: mock results are ONLY used when MOCK_MODE is on or no search
key is configured. The API/UI always surfaces mock_mode so fixtures can never
be mistaken for live web sources.
"""

from __future__ import annotations

from app.services.retrieval.base import SearchHit, SearchProvider

FIXTURES: list[dict] = [
    {
        "title": "EPA — Desalination: Energy and Brine Management Overview (fixture)",
        "url": "mock://fixtures/epa-desalination-overview",
        "publisher": "U.S. Environmental Protection Agency (fixture)",
        "source_type": "government",
        "domain": "epa.gov",
        "snippet": "Desalination requires substantial energy input; brine discharge can raise local salinity.",
        "content": (
            "Desalination can require substantial energy input. Reverse osmosis plants typically consume "
            "3 to 6 kilowatt-hours per cubic meter of product water. Brine discharge can raise local salinity "
            "near the outfall, which may affect benthic organisms. Diffuser systems and siting can reduce impacts. "
            "Page 12, section Energy requirements."
        ),
    },
    {
        "title": "UNESCO-IOC — Desalination and the Marine Environment (fixture)",
        "url": "mock://fixtures/unesco-desalination-marine",
        "publisher": "UNESCO-IOC (fixture)",
        "source_type": "institutional",
        "domain": "unesco.org",
        "snippet": "Brine plumes and intake impingement are the main marine pressures; mitigation exists.",
        "content": (
            "Brine discharge increases salinity and temperature in the mixing zone. Intake systems can impinge "
            "larvae and plankton. Studies report measurable effects within hundreds of meters of outfalls, with "
            "effects declining with distance. Co-location with power-plant cooling water can dilute brine."
        ),
    },
    {
        "title": "Peer-reviewed synthesis — Life-cycle impacts of seawater desalination (fixture)",
        "url": "mock://fixtures/journal-swro-lifecycle",
        "publisher": "Journal fixture",
        "source_type": "academic",
        "domain": "example-journal.org",
        "snippet": "Energy source dominates carbon footprint; brine effects are local but real.",
        "content": (
            "The carbon footprint of seawater reverse osmosis is dominated by electricity source: grids with high "
            "renewable share show markedly lower emissions per cubic meter. Brine constituents include elevated salt "
            "plus residual treatment chemicals. Long-term ecosystem-scale effects remain understudied."
        ),
    },
    {
        "title": "National Academy-style review — Conflicting findings on brine dispersion (fixture)",
        "url": "mock://fixtures/nas-brine-review",
        "publisher": "Academy review (fixture)",
        "source_type": "scientific",
        "domain": "academies.example.org",
        "snippet": "Some near-field studies report little measurable effect beyond the mixing zone.",
        "content": (
            "Some near-field monitoring studies report little measurable effect on fish abundance beyond the "
            "regulated mixing zone, while other studies document reduced benthic diversity close to outfalls. "
            "Differences likely reflect different outfall designs, time periods, and measurement criteria; "
            "reason unclear in several comparisons."
        ),
    },
]


class MockSearchProvider(SearchProvider):
    name = "mock"

    async def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        q = query.lower()
        scored: list[tuple[float, dict]] = []
        for f in FIXTURES:
            text = (f["title"] + " " + f["snippet"] + " " + f["content"]).lower()
            overlap = len(set(q.split()) & set(text.split()))
            scored.append((overlap, f))
        scored.sort(key=lambda t: t[0], reverse=True)
        out: list[SearchHit] = []
        for _, f in scored[:limit]:
            out.append(SearchHit(title=f["title"], url=f["url"], snippet=f["snippet"],
                                 publisher=f["publisher"], source_type=f["source_type"],
                                 domain=f["domain"], content=f["content"], raw_score=0.5))
        # Generic fallback fixture so arbitrary questions still yield traceable evidence.
        if not out or scored[0][0] == 0:
            out.append(SearchHit(
                title=f"Fixture overview for: {query[:80]}",
                url="mock://fixtures/generic-overview",
                snippet="General fixture evidence; replace with live search in production.",
                publisher="ResearchForge fixtures",
                source_type="unknown", domain="fixtures.local",
                content=(f"This fixture passage discusses '{query[:120]}'. It states that evidence is limited "
                         "and that findings depend on context and methodology. Treat as development placeholder."),
                raw_score=0.1))
        return out
