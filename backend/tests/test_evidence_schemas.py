"""Unit: evidence extraction is extractive (quotes are substrings) + schema-validated."""

import pytest

from app.agents.extractor import extract_evidence
from app.schemas.research import EvidenceItem


def test_quotes_are_verbatim():
    content = ("Desalination can require substantial energy input. Reverse osmosis plants typically "
               "consume 3 to 6 kilowatt-hours per cubic meter. Brine discharge can raise local salinity.")
    items = extract_evidence("energy requirements of desalination", "s1", content)
    assert items
    for it in items:
        assert it.quote in content
        EvidenceItem.model_validate(it.model_dump())


def test_empty_content_yields_nothing():
    assert extract_evidence("anything", "s1", "too short") == []


def test_schema_rejects_short_quote():
    with pytest.raises(Exception):
        EvidenceItem(claim="ok claim here", quote="short", source_id="s",
                     relevance_score=0.5, confidence_score=0.5)
