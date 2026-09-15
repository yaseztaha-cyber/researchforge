"""Document-library provider: searches previously uploaded/indexed chunks (RAG)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.db_models import SourceChunk
from app.services.embeddings.hash_embeddings import cosine
from app.services.embeddings.factory import get_embedding_provider
from app.services.retrieval.base import SearchHit, SearchProvider


class DocumentSearchProvider(SearchProvider):
    name = "documents"

    def __init__(self, db: Session, *, run_id: str | None = None):
        self.db = db
        self.run_id = run_id

    async def search(self, query: str, *, limit: int = 8) -> list[SearchHit]:
        emb = get_embedding_provider()
        qv = emb.embed(query)
        q = self.db.query(SourceChunk)
        if self.run_id:
            q = q.filter(SourceChunk.run_id == self.run_id)
        chunks = q.limit(500).all()
        scored = []
        for c in chunks:
            if not c.embedding:
                continue
            scored.append((cosine(qv, list(c.embedding)), c))
        scored.sort(key=lambda t: t[0], reverse=True)
        hits: list[SearchHit] = []
        for score, c in scored[:limit]:
            hits.append(SearchHit(title=f"Uploaded document chunk #{c.chunk_index}",
                                  url=None, snippet=c.text[:400], source_type="technical_documentation",
                                  content=c.text, raw_score=float(max(0.0, min(1.0, score)))))
        return hits
