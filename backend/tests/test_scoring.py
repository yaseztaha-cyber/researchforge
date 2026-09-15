"""Unit: ranking is transparent and prefers trustworthy source types."""

from app.services.retrieval.base import SearchHit, rank_hits


def _hit(title, stype, domain):
    return SearchHit(title=title, url=f"https://{domain}/x", snippet=title,
                     source_type=stype, domain=domain, content=title + " desalination brine energy")


def test_ranking_prefers_government_over_blog():
    q = "environmental impacts of desalination brine"
    gov = _hit("EPA desalination brine environmental impacts", "government", "epa.gov")
    blog = _hit("desalination brine environmental impacts hot take", "blog", "randomblog.example.com")
    ranked = rank_hits(q, [blog, gov])
    assert ranked[0].hit.source_type == "government"
    assert "formula" in ranked[0].breakdown
    assert 0.0 <= ranked[0].relevance <= 1.0
    assert 0.0 <= ranked[0].quality <= 1.0


def test_scores_bounded():
    ranked = rank_hits("test", [_hit("t", "unknown", "x.example")])
    assert 0.0 <= ranked[0].relevance <= 1.0
