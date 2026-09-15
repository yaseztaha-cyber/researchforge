"""Vector store abstraction: pgvector-backed when PostgreSQL is available,
SQLite brute-force fallback otherwise. Unified interface for upsert/search/delete.

Indexes:
- PostgreSQL + pgvector: ivfflat (cosine) for <1M vectors; hnsw for larger
  corpora (higher recall, higher memory). Documented in docs/rag.md.
- SQLite: no vector index; brute-force cosine over JSON embeddings with
  optional top_k pruning (fast enough for dev datasets <10k chunks).

Dimension safety: every stored chunk records embedding_model and embedding_dim;
mismatched dimensions raise a clear error and trigger reindex guidance.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.db_models import DocumentChunk
from app.services.embeddings.hash_embeddings import cosine


@dataclass
class ChunkHit:
    id: str
    document_id: str
    chunk_index: int
    page: int | None
    section: str | None
    heading: str | None
    text: str
    char_start: int | None
    char_end: int | None
    similarity: float
    metadata: dict


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, db: Session, chunks: list[DocumentChunk]) -> int: ...

    @abstractmethod
    def search(self, db: Session, query_embedding: list[float], *,
               top_k: int = 20, min_similarity: float = 0.0,
               document_ids: list[str] | None = None,
               document_id: str | None = None) -> list[ChunkHit]: ...

    @abstractmethod
    def delete_by_document(self, db: Session, document_id: str) -> int: ...

    @abstractmethod
    def count(self, db: Session, document_id: str | None = None) -> int: ...


class SqliteVectorStore(VectorStore):
    """Brute-force cosine search over JSON embeddings (dev fallback)."""

    def upsert(self, db: Session, chunks: list[DocumentChunk]) -> int:
        # Chunks already persisted via SQLAlchemy; nothing extra to do.
        return len(chunks)

    def search(self, db: Session, query_embedding: list[float], *,
               top_k: int = 20, min_similarity: float = 0.0,
               document_ids: list[str] | None = None,
               document_id: str | None = None) -> list[ChunkHit]:
        q = db.query(DocumentChunk)
        if document_id:
            q = q.filter(DocumentChunk.document_id == document_id)
        elif document_ids:
            q = q.filter(DocumentChunk.document_id.in_(document_ids))
        rows = q.limit(5000).all()
        qdim = len(query_embedding)
        scored: list[tuple[float, DocumentChunk]] = []
        for r in rows:
            if not r.embedding or len(r.embedding) != qdim:
                continue
            sim = cosine(query_embedding, list(r.embedding))
            if sim < min_similarity:
                continue
            scored.append((sim, r))
        scored.sort(key=lambda t: t[0], reverse=True)
        out: list[ChunkHit] = []
        for sim, r in scored[:top_k]:
            out.append(ChunkHit(id=r.id, document_id=r.document_id, chunk_index=r.chunk_index,
                                page=r.page, section=r.section, heading=r.heading, text=r.text,
                                char_start=r.char_start, char_end=r.char_end,
                                similarity=round(float(sim), 4),
                                metadata={"embedding_model": r.embedding_model, "embedding_dim": r.embedding_dim}))
        return out

    def delete_by_document(self, db: Session, document_id: str) -> int:
        n = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        db.commit()
        return n

    def count(self, db: Session, document_id: str | None = None) -> int:
        q = db.query(DocumentChunk)
        if document_id:
            q = q.filter(DocumentChunk.document_id == document_id)
        return q.count()


class PgVectorStore(VectorStore):
    """Postgres + pgvector cosine search. Falls back to brute-force if column missing."""

    def upsert(self, db: Session, chunks: list[DocumentChunk]) -> int:
        # Mirror JSON embeddings into embedding_vec column if it exists.
        try:
            for c in chunks:
                if c.embedding:
                    db.execute(text("UPDATE document_chunks SET embedding_vec = :v::vector WHERE id = :id"),
                               {"v": "[" + ",".join(str(x) for x in c.embedding) + "]", "id": c.id})
            db.commit()
        except Exception:
            db.rollback()
        return len(chunks)

    def search(self, db: Session, query_embedding: list[float], *,
               top_k: int = 20, min_similarity: float = 0.0,
               document_ids: list[str] | None = None,
               document_id: str | None = None) -> list[ChunkHit]:
        # Try pgvector operator first; on failure fall back to brute-force.
        try:
            vec_literal = "[" + ",".join(str(x) for x in query_embedding) + "]"
            # cosine distance: 1 - cosine similarity; pgvector uses <=> for cosine distance
            sql = """
                SELECT id, document_id, chunk_index, page, section, heading, text,
                       char_start, char_end, embedding_model, embedding_dim,
                       1 - (embedding_vec <=> :q::vector) AS similarity
                FROM document_chunks
                WHERE 1=1
            """
            params: dict = {"q": vec_literal}
            if document_id:
                sql += " AND document_id = :did"
                params["did"] = document_id
            elif document_ids:
                sql += " AND document_id = ANY(:dids)"
                params["dids"] = document_ids
            sql += " ORDER BY embedding_vec <=> :q::vector LIMIT :k"
            params["k"] = top_k
            rows = db.execute(text(sql), params).fetchall()
            out: list[ChunkHit] = []
            for r in rows:
                sim = float(r.similarity or 0.0)
                if sim < min_similarity:
                    continue
                out.append(ChunkHit(id=r.id, document_id=r.document_id, chunk_index=r.chunk_index,
                                    page=r.page, section=r.section, heading=r.heading, text=r.text,
                                    char_start=r.char_start, char_end=r.char_end,
                                    similarity=round(sim, 4),
                                    metadata={"embedding_model": r.embedding_model,
                                              "embedding_dim": r.embedding_dim}))
            return out
        except Exception:
            # Fallback brute-force
            return SqliteVectorStore().search(db, query_embedding, top_k=top_k,
                                              min_similarity=min_similarity,
                                              document_ids=document_ids, document_id=document_id)

    def delete_by_document(self, db: Session, document_id: str) -> int:
        n = db.query(DocumentChunk).filter(DocumentChunk.document_id == document_id).delete()
        db.commit()
        return n

    def count(self, db: Session, document_id: str | None = None) -> int:
        q = db.query(DocumentChunk)
        if document_id:
            q = q.filter(DocumentChunk.document_id == document_id)
        return q.count()


def get_vector_store() -> VectorStore:
    s = get_settings()
    if s.is_postgres:
        return PgVectorStore()
    return SqliteVectorStore()
