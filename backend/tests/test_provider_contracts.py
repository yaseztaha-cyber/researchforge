"""Provider contract tests: each provider must satisfy the same interface."""

import pytest

from app.services.embeddings.factory import get_embedding_provider
from app.services.llm.factory import get_llm_provider
from app.services.retrieval.factory import get_search_provider
from app.services.retrieval.providers.mock_provider import MockSearchProvider
from app.services.retrieval.providers.replay_provider import ReplaySearchProvider


def test_llm_provider_contract():
    p = get_llm_provider()
    assert hasattr(p, "complete")
    assert hasattr(p, "complete_json")


@pytest.mark.asyncio
async def test_llm_mock_returns_text():
    p = get_llm_provider()
    resp = await p.complete(system="you are planner", user="Question: What is X?")
    assert isinstance(resp.text, str) and len(resp.text) > 0
    assert resp.model


def test_search_provider_contract():
    for prov in [MockSearchProvider(), ReplaySearchProvider()]:
        assert hasattr(prov, "search")
        assert hasattr(prov, "fetch")


@pytest.mark.asyncio
async def test_search_providers_return_hits_schema():
    for prov in [MockSearchProvider(), ReplaySearchProvider()]:
        hits = await prov.search("desalination impacts", limit=2)
        assert isinstance(hits, list)
        for h in hits:
            assert hasattr(h, "title") and h.title
            assert hasattr(h, "snippet")
            assert hasattr(h, "source_type")


@pytest.mark.asyncio
async def test_search_empty_results_handled():
    # Replay with nonexistent specific query falls back to example
    prov = ReplaySearchProvider()
    hits = await prov.search("this query does not match any fixture file at all xyzzy", limit=2)
    assert isinstance(hits, list)


def test_embedding_provider_contract():
    emb = get_embedding_provider()
    assert emb.dim == 384
    vec = emb.embed("hello world")
    assert len(vec) == 384
    # normalize and batch
    assert len(emb.normalize("  hello ")) > 0
    vecs = emb.embed_many(["a", "b"])
    assert len(vecs) == 2 and len(vecs[0]) == 384
    # Failure handling: embed empty string should not crash
    assert len(emb.embed("")) == 384


def test_document_parser_contract():
    from app.services.documents.parser import parse_document
    # TXT
    doc = parse_document("notes.txt", b"hello world\n\nsecond para")
    assert doc.text
    # Markdown
    doc2 = parse_document("notes.md", b"# Title\n\ncontent")
    assert "Title" in doc2.text
    # Invalid: unsupported extension
    with pytest.raises(ValueError):
        parse_document("evil.exe", b"MZ")
    # Malformed PDF
    with pytest.raises(ValueError):
        parse_document("bad.pdf", b"not a pdf at all")


@pytest.mark.asyncio
async def test_search_429_not_crash():
    # Mock provider never raises 429; replay also not. Verify interface survives empty.
    prov = MockSearchProvider()
    hits = await prov.search("", limit=1)
    assert isinstance(hits, list)
