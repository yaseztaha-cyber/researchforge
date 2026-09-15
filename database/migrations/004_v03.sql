-- 004_v03.sql — pgvector RAG + document versioning for v0.3
-- SQLite dev DBs upgrade automatically at startup.

-- Document versioning columns for existing table (also handled by _ensure_v02_columns)
ALTER TABLE documents ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS first_seen TIMESTAMPTZ DEFAULT now();
ALTER TABLE documents ADD COLUMN IF NOT EXISTS last_seen TIMESTAMPTZ DEFAULT now();
ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_model TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS embedding_dim INTEGER;

-- Production chunk table with pgvector support
CREATE TABLE IF NOT EXISTS document_chunks (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INTEGER DEFAULT 0,
  page INTEGER,
  section TEXT,
  heading TEXT,
  text TEXT NOT NULL,
  char_start INTEGER,
  char_end INTEGER,
  content_hash TEXT,
  embedding JSONB,
  embedding_model TEXT,
  embedding_dim INTEGER,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_docchunks_doc ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS ix_docchunks_hash ON document_chunks(content_hash);

-- pgvector column (PostgreSQL only; SQLite ignores this migration)
-- The Python model stores vectors in JSON for SQLite and in embedding_vec for Postgres.
-- Index choice: ivfflat with cosine ops for datasets <1M vectors; for larger
-- corpora prefer hnsw (higher recall, higher memory). Documented in docs/rag.md.
-- ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector(384);
-- CREATE INDEX IF NOT EXISTS ix_docchunks_vec ON document_chunks USING ivfflat (embedding_vec vector_cosine_ops);
