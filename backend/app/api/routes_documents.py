"""Document upload + indexing (PDF/TXT/MD -> chunks + embeddings for RAG)."""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import SecurityError, sniff_content, validate_upload
from app.db.session import get_db
from app.models.db_models import Document, SourceChunk
from app.services.documents.parser import chunk_text, parse_document
from app.services.embeddings.factory import get_embedding_provider

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
        return {"document_id": existing.id, "duplicate": True, "num_chunks": existing.num_chunks}
    chunks = chunk_text(parsed.text)
    emb = get_embedding_provider()
    doc = Document(filename=file.filename or "upload", content_hash=chash, num_chunks=len(chunks))
    db.add(doc)
    db.flush()
    # Chunks are attached to a synthetic per-document source namespace via run_id when given.
    for c in chunks[:50]:
        db.add(SourceChunk(source_id=doc.id, run_id=run_id or doc.id, chunk_index=c.index,
                           page=c.page, section=c.section, text=c.text[:3000],
                           embedding=emb.embed(c.text[:2000])))
    db.commit()
    return {"document_id": doc.id, "duplicate": False, "num_chunks": len(chunks), "extension": ext}


@router.post("/{document_id}/index")
def index_document(document_id: str, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(404, "Document not found")
    n = db.query(SourceChunk).filter(SourceChunk.source_id == document_id).count()
    return {"document_id": document_id, "indexed_chunks": n}
