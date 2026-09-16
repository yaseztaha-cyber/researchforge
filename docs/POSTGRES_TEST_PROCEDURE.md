# PostgreSQL + pgvector Live Test Procedure

## Goal
Validate ResearchForge against real PostgreSQL + pgvector infrastructure.

## Prerequisites

1. **PostgreSQL 16+** with **pgvector 0.7+**
2. **Docker** (optional, for local dev) or native PostgreSQL installation
3. Environment variables configured

## Quick Start (Docker)

```bash
# Start PostgreSQL with pgvector
docker run --name rf-pgvector \
  -e POSTGRES_USER=researchforge \
  -e POSTGRES_PASSWORD=changeme \
  -e POSTGRES_DB=researchforge \
  -p 5432:5432 \
  -v pgdata:/var/lib/postgresql/data \
  -d pgvector/pgvector:pg16

# Verify connection
docker exec -it rf-pgvector psql -U researchforge -d researchforge -c "SELECT version();"
docker exec -it rf-pgvector psql -U researchforge -d researchforge -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Native PostgreSQL (No Docker)

```bash
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y postgresql-16 postgresql-16-pgvector

# macOS (Homebrew)
brew install postgresql@16 pgvector

# Configure
sudo systemctl start postgresql
sudo -u postgres psql -c "CREATE USER researchforge WITH PASSWORD 'changeme';"
sudo -u postgres psql -c "CREATE DATABASE researchforge OWNER researchforge;"
sudo -u postgres psql -d researchforge -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

## Configure ResearchForge

```bash
# backend/.env
DATABASE_URL=postgresql+psycopg://researchforge:changeme@localhost:5432/researchforge
```

## Run Migrations

```bash
cd backend
python -c "
from app.db.session import init_db
init_db()
print('Migrations applied')
"
```

## Verification Checklist

Run each step and record PASS/FAIL with output:

| Step | Command | Expected | PASS/FAIL | Notes |
|------|---------|----------|-----------|-------|
| 1. Connect | `python -c "from app.db.session import engine; print(engine.connect().execute(text('SELECT 1')).scalar())"` | `1` | | |
| 2. pgvector ext | `python -c "from app.db.session import engine; from sqlalchemy import text; print(engine.connect().execute(text('SELECT extname FROM pg_extension WHERE extname=vector')).fetchone())"` | `('vector',)` | | |
| 3. Migrations | `python -c "from app.db.session import init_db; init_db(); print('OK')` | `OK` | | |
| 4. Tables exist | `python -c "from app.db.session import engine; from sqlalchemy import inspect; insp=inspect(engine); print([t for t in insp.get_table_names() if t.startswith('document')])"` | `['documents', 'document_chunks']` | | |
| 5. Vector column | `python -c "from app.db.session import engine; from sqlalchemy import text; print(engine.connect().execute(text(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name='document_chunks' AND column_name='embedding_vec'\")).fetchone())"` | `('embedding_vec', 'USER-DEFINED')` | | |
| 6. Insert chunk | `python -c "from app.db.session import SessionLocal; from app.models.db_models import Document, DocumentChunk; from app.services.embeddings.factory import get_embedding_provider; db=SessionLocal(); emb=get_embedding_provider(); doc=Document(filename='test.pdf', content_hash='test123', num_chunks=1); db.add(doc); db.flush(); db.add(DocumentChunk(document_id=doc.id, chunk_index=0, text='test content', embedding=emb.embed('test content'), embedding_model=emb.name, embedding_dim=emb.dim)); db.commit(); print('inserted', doc.id)"` | `inserted <uuid>` | | |
| 7. Vector search | `python -c "from app.services.vector_store import get_vector_store; from app.services.embeddings.factory import get_embedding_provider; from app.db.session import SessionLocal; db=SessionLocal(); vs=get_vector_store(); emb=get_embedding_provider(); qv=emb.embed('test'); hits=vs.search(db, qv, top_k=5); print(f'found {len(hits)} hits, top sim={hits[0].similarity:.3f}')" | `found N hits, top sim=X.XXX` | | |
| 8. Metadata filter | `python -c "from app.services.vector_store import get_vector_store; from app.services.embeddings.factory import get_embedding_provider; from app.db.session import SessionLocal; db=SessionLocal(); vs=get_vector_store(); emb=get_embedding_provider(); qv=emb.embed('test'); hits=vs.search(db, qv, top_k=5, document_id='<uuid-from-step-6>'); print(f'filtered hits: {len(hits)}')" | `filtered hits: 1` | | |
| 9. Delete by doc | `python -c "from app.services.vector_store import get_vector_store; from app.db.session import SessionLocal; db=SessionLocal(); vs=get_vector_store(); n=vs.delete_by_document(db, '<uuid-from-step-6>'); print(f'deleted {n}')" | `deleted 1` | | |
| 10. Reindex | `python scripts/reindex.py --document <uuid-from-step-6>` | `Reindexed 1 DocumentChunk rows...` | | |
| 11. Duplicate upload | Upload same file twice via `/api/documents/upload` | `duplicate: true` on second | | |
| 12. Dim validation | Change embedding model → reindex → expect HTTP 400 | HTTP 400 | | |
| 12. Hybrid search | `python -c "from app.services.hybrid_retrieval import score_chunk, rerank_and_diversify; from app.services.vector_store import ChunkHit; from app.services.embeddings.factory import get_embedding_provider; q='test'; emb=get_embedding_provider(); qv=emb.embed(q); from app.services.vector_store import get_vector_store; from app.db.session import SessionLocal; db=SessionLocal(); vs=get_vector_store(); hits=vs.search(db, qv, top_k=10); cands=[__import__('app.services.hybrid_retrieval', fromlist=['score_chunk']).score_chunk('test', h, query_embedding=qv) for h in hits]; sel, _ = __import__('app.services.hybrid_retrieval', fromlist=['rerank_and_diversify']).rerank_and_diversify('test', cands, top_k=3); print(f'selected {len(sel)}')" | `selected N` | | |

## Record Results

Save results to `evaluation/reports/postgres_validation_<timestamp>.json`:

```json
{
  "timestamp": "2026-09-XX...",
  "environment": "docker|native|ci",
  "postgres_version": "16.x",
  "pgvector_version": "0.7.x",
  "checks": [
    {"step": 1, "name": "connect", "pass": true, "output": "1"},
    ...
  ],
  "all_passed": true
}
```

## If PostgreSQL Unavailable

Document exactly why:

```json
{
  "postgres_available": false,
  "reason": "No Docker daemon / no native PostgreSQL installation / no network access to managed Postgres",
  "reproducible_procedure": "See docs/POSTGRES_TEST_PROCEDURE.md",
  "fallback": "SQLite brute-force vector store remains default for development; pgvector path code-reviewed and documented in docs/rag.md"
}
```

Save as `evaluation/reports/postgres_unavailable_<timestamp>.json`.

## Next Steps After PASS

1. Seed real corpus (500–2000 chunks) → `evaluation/scripts/seed_corpus.py`
2. Run SQLite vs pgvector benchmark → `evaluation/scripts/sqlite_vs_pgvector.py`
3. Run index benchmark (IVFFlat vs HNSW) if corpus > 10k chunks
4. Run full evaluation benchmark against pgvector
4. Proceed to retrieval error analysis with real vector store