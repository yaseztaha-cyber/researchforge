# ResearchForge — RAG / Vector Architecture

## Pipeline
```
Document (PDF/MD/TXT)
→ parser (pypdf + text) → text normalization
→ chunking_v3 (heading → paragraph → sentence → word-window)
→ chunk metadata (document_id, page, section, heading, char offsets, hash)
→ embedding (hash-384, batch + cache)
→ DocumentChunk (JSON) + DocumentChunk.embedding_vec (pgvector on Postgres)
→ vector store → hybrid rerank → MMR diversity → evidence
```

## Chunking
- `chunk_document_v3` in `app/services/documents/chunking.py`.
- Priority: headings (markdown `#` / PDF page breaks) → paragraphs → sentence boundaries → fixed word window.
- Preserves `char_start/char_end` (searchable), `content_hash`, per-chunk `embedding_model/dim`.

## Embedding pipeline
- `HashEmbeddingProvider` (dim 384, L2-normalized) via `app/services/embeddings/`.
- `EmbeddingCache` (LRU, 2048 entries, hit/miss counters) avoids re-embedding identical chunks.
- `embed_many` for batching; provider dimension validated on reindex.
- Records `embedding_model`, `embedding_dim`, `created_at`, `content_hash` per chunk.

## Data model
- `documents` (version, first_seen/last_seen, embedding_model/dim) + `document_chunks` (new v0.3 table).
- Legacy `SourceChunk` retained for backward compat (old tests, old DBs).
- `vector_store`: `SqliteVectorStore` (brute-force cosine over JSON, dev <10k chunks) and `PgVectorStore` (pgvector `vector(384)` + `1 - (vec <=> query)` cosine).
- Index choice: migration `002_pgvector.sql` uses `ivfflat` (`vector_cosine_ops`) for <1M vectors; for larger corpora prefer `hnsw` (higher recall, higher memory). Documented here, not hard-coded.

## Search
- `VectorStore.search(query_embedding, top_k, min_similarity, document_ids)` → `ChunkHit`s with stored metadata.
- Metadata filters: `document_id`, `document_ids`, future `project_id`.

## Versioning / Reindexing
- `content_hash` deduplicates uploads; duplicate upload bumps `last_seen` but does not duplicate vectors.
- `POST /api/documents/{id}/reindex` and `scripts/reindex.py --document <id>` regenerate embeddings for one document only; validate dim compatibility; never touch unrelated vectors.

## Hybrid retrieval
Fused in `app/services/hybrid_retrieval.py`:
```
final = w_sem·cosine + w_lex·lexical + w_cov·coverage + w_qual·quality
weights: semantic 0.45, lexical 0.20, coverage 0.15, quality 0.20 (env-configurable)
```
Plus near-duplicate suppression (>0.92 cosine) and MMR diversity (λ=0.7, per-doc cap 3).
