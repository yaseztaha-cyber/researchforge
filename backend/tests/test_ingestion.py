"""Integration: document ingestion -> chunking -> embeddings."""

from app.services.documents.parser import chunk_text, parse_document
from app.services.embeddings.factory import get_embedding_provider
from app.services.embeddings.hash_embeddings import cosine


def test_ingest_and_chunk_txt():
    parsed = parse_document("notes.md", b"# Energy\n\nDesalination needs energy. " * 50)
    chunks = chunk_text(parsed.text, target=30, overlap=5)
    assert len(chunks) >= 2
    assert chunks[0].section == "Energy"


def test_embeddings_deterministic():
    emb = get_embedding_provider()
    a = emb.embed("desalination brine energy")
    b = emb.embed("desalination brine energy")
    assert cosine(a, b) > 0.999
    c = emb.embed("completely unrelated quantum baking recipes")
    assert cosine(a, c) < 0.5
