"""Document upload + indexing (PDF/TXT/MD -> chunks + embeddings for RAG)."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import SecurityError, sniff_content, validate_upload
from app.db.session import get_db
import datetime as dt

from app.models.db_models import Document, DocumentChunk, SourceChunk
from app.services.documents.chunking import chunk_document_v3
from app.services.documents.parser import chunk_text, parse_document
from app.services.embeddings.cache import EmbeddingCache
from app.services.embeddings.factory import get_embedding_provider
from app.services.vector_store import get_vector_store

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
async def upload(file: UploadFile, run_id: str | None = None, db: Session = Depends(get_db)):
    settings = get_settings()
    raw = await file.read()
    try:
        ext = validate_upload(file.filename or "upload.bin", len(raw), settings.MAX_UPLOAD_MB)
        sniff_content(file.filename or "upload.bin", raw)
    except SecurityError as e:
        raise HTTPException(400, str(e))
    try:
        parsed = parse_document(file.filename or "doc.txt", raw)
    except ValueError as e:
        raise HTTPException(400, str(e))
    chash = hashlib.sha256(raw).hexdigest()
    existing = db.query(Document).filter(Document.content_hash == chash).first()
    if existing is not None:
        existing.last_seen = dt.datetime.now(dt.timezone.utc)
        db.commit()
        return {"document_id": existing.id, "duplicate": True, "num_chunks": existing.num_chunks, "version": existing.version}
    chunks = chunk_document_v3(parsed.text, target_words=settings.CHUNK_TARGET_TOKENS,
                               overlap_words=settings.CHUNK_OVERLAP_TOKENS, pages=parsed.pages if parsed.pages else None)
    # Fallback legacy chunker if v3 produced nothing
    if not chunks:
        legacy = chunk_text(parsed.text)
        chunks = [type(chunks[0])(index=c.index, text=c.text, page=c.page, section=c.section, heading=c.section,
                                  char_start=0, char_end=len(c.text), content_hash=hashlib.sha256(c.text.encode()).hexdigest()) for c in legacy] if legacy else []
    emb = get_embedding_provider()
    cache = EmbeddingCache(emb)
    texts = [c.text[:2000] for c in chunks[:50]]
    vecs = cache.embed_many_cached(texts)
    # Versioning: new document gets version 1, first_seen/last_seen now
    now = dt.datetime.now(dt.timezone.utc)
    doc = Document(filename=file.filename or "upload", content_hash=chash, num_chunks=len(chunks[:50]),
                   version=1, first_seen=now, last_seen=now,
                   embedding_model=emb.name, embedding_dim=emb.dim)
    db.add(doc)
    db.flush()
    # Store in v0.3 DocumentChunk (primary) + legacy SourceChunk (compat for old orchestrator path)
    for c, vec in zip(chunks[:50], vecs):
        db.add(DocumentChunk(document_id=doc.id, chunk_index=c.index, page=c.page, section=c.section,
                             heading=c.heading, text=c.text[:8000], char_start=c.char_start, char_end=c.char_end,
                             content_hash=c.content_hash, embedding=vec, embedding_model=emb.name, embedding_dim=emb.dim))
        db.add(SourceChunk(source_id=doc.id, run_id=run_id or doc.id, chunk_index=c.index,
                           page=c.page, section=c.section, text=c.text[:3000], embedding=vec))
    db.commit()
    # Also upsert into vector store (pgvector mirror if postgres)
    try:
        rows = db.query(DocumentChunk).filter(DocumentChunk.document_id == doc.id).all()
        get_vector_store().upsert(db, rows)
    except Exception:
        pass
    return {"document_id": doc.id, "duplicate": False, "num_chunks": len(chunks[:50]), "extension": ext, "version": 1}


@router.post("/{document_id}/index")
def index_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    n = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).count()
    legacy = db.query(SourceChunk).filter(SourceChunk.source_id == document_id).count()
    return {"document_id": document_id, "indexed_chunks": n, "legacy_chunks": legacy}


@router.post("/{document_id}/reindex")
def reindex_document(document_id: str, db: Session = Depends(get_db)):
    """Safe reindex: deletes and regenerates embeddings for one document only."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    emb = get_embedding_provider()
    # Dimension guard: if model changed, require explicit reindex — we support hash-384 only for now
    if doc.embedding_model and doc.embedding_model != emb.name:
        raise HTTPException(400, f"Embedding model mismatch: document has {doc.embedding_model!r} vs current {emb.name!r}; re-upload or force reindex via CLI.")
    if doc.embedding_dim and doc.embedding_dim != emb.dim:
        raise HTTPException(400, f"Embedding dim mismatch: {doc.embedding_dim} vs {emb.dim}")
    chunks = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).all()
    if not chunks:
        # Legacy fallback: reindex SourceChunk rows
        from app.models.db_models import SourceChunk as _SC
        legacy = db.query(_SC).filter(_SC.source_id == document_id).all()
        if not legacy:
            raise HTTPException(400, "No chunks to reindex")
        cache = EmbeddingCache(emb)
        lvecs = cache.embed_many_cached([c.text[:2000] for c in legacy])
        for c, vec in zip(legacy, lvecs):
            c.embedding = vec
        db.commit()
        return {"document_id": document_id, "reindexed_chunks": len(legacy), "legacy": True}
    cache = EmbeddingCache(emb)
    vecs = cache.embed_many_cached([c.text[:2000] for c in chunks])
    for c, vec in zip(chunks, vecs):
        c.embedding = vec
        c.embedding_model = emb.name
        c.embedding_dim = emb.dim
    db.commit()
    vs.upsert(db, chunks)
    doc.last_seen = dt.datetime.now(dt.timezone.utc)
    doc.embedding_model = emb.name
    doc.embedding_dim = emb.dim
    db.commit()
    return {"document_id": document_id, "reindexed_chunks": len(chunks)}


@router.get("")
def list_documents(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.query(Document).order_by(Document.created_at.desc()).limit(min(limit, 100)).all()
    return {"documents": [{"id": d.id, "filename": d.filename, "version": d.version,
                           "num_chunks": d.num_chunks, "embedding_model": d.embedding_model,
                           "embedding_dim": d.embedding_dim} for d in rows]}
