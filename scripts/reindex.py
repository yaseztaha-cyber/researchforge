#!/usr/bin/env python3
"""Safe reindex for one document (v0.3). Never destroys unrelated vectors."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.db.session import SessionLocal, init_db
from app.models.db_models import Document, DocumentChunk
from app.services.embeddings.factory import get_embedding_provider
from app.services.vector_store import get_vector_store


def reindex_one(document_id: str, force: bool = False) -> None:
    init_db()
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if not doc:
            print(f"Document {document_id} not found")
            sys.exit(1)
        emb = get_embedding_provider()
        if not force and doc.embedding_model and doc.embedding_model != emb.name:
            print(f"Model mismatch: document {doc.embedding_model!r} vs current {emb.name!r} -- use --force to re-embed anyway")
            sys.exit(1)
        if not force and doc.embedding_dim and doc.embedding_dim != emb.dim:
            print(f"Dim mismatch: {doc.embedding_dim} vs {emb.dim} -- use --force")
            sys.exit(1)
        vs = get_vector_store()
        # Delete only this document's vectors
        deleted = vs.delete_by_document(db, document_id)
        print(f"Deleted {deleted} old vector rows for document {document_id}")
        chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
        if not chunks:
            # legacy SourceChunk path
            from app.models.db_models import SourceChunk
            from app.services.embeddings.cache import EmbeddingCache
            legacy = db.query(SourceChunk).filter(SourceChunk.source_id == document_id).all()
            if not legacy:
                print("No chunks found")
                return
            cache = EmbeddingCache(emb)
            vecs = cache.embed_many_cached([c.text[:2000] for c in legacy])
            for c, vec in zip(legacy, vecs):
                c.embedding = vec
            db.commit()
            print(f"Reindexed {len(legacy)} legacy SourceChunk rows")
            return
        # Re-embed DocumentChunk rows
        from app.services.embeddings.cache import EmbeddingCache
        cache = EmbeddingCache(emb)
        vecs = cache.embed_many_cached([c.text[:2000] for c in chunks])
        for c, vec in zip(chunks, vecs):
            c.embedding = vec
            c.embedding_model = emb.name
            c.embedding_dim = emb.dim
        db.commit()
        vs.upsert(db, chunks)
        doc.embedding_model = emb.name
        doc.embedding_dim = emb.dim
        db.commit()
        print(f"Reindexed {len(chunks)} DocumentChunk rows with {emb.name} dim {emb.dim}")
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Safe reindex for one document")
    ap.add_argument("--document", required=True, help="document id")
    ap.add_argument("--force", action="store_true", help="force re-embed despite model/dim mismatch")
    args = ap.parse_args()
    reindex_one(args.document, force=args.force)
