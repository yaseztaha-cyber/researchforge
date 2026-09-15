-- 002_pgvector.sql — run only on PostgreSQL with pgvector installed.
CREATE EXTENSION IF NOT EXISTS vector;
-- Vector column for semantic retrieval (384 dims to match hash-384 fallback).
ALTER TABLE source_chunks ADD COLUMN IF NOT EXISTS embedding_vec vector(384);
CREATE INDEX IF NOT EXISTS ix_chunks_vec ON source_chunks USING ivfflat (embedding_vec vector_cosine_ops);
