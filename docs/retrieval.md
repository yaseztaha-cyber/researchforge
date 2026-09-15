# ResearchForge — Retrieval

Pipeline: typed queries → parallel provider search → canonical+hash dedup →
component scoring → MMR diversity selection → relevance cutoff → evidence.

## Query generation
The planner emits 4–7 **typed** queries (`broad, scientific, mechanism,
consequence, recent, mitigation, controversy`), each with a `reason`. Every
executed query is audited in `research_queries` (query, type, reason, round,
status, hits). Failed queries degrade gracefully and are counted in the
report ("N planned queries failed").

## Deduplication
- `canonicalize_url`: lowercase host, strip `www.`/`m.`, drop tracking params
  (`utm_*`, `gclid`, …), fragments, trailing slashes.
- `content_hash`: SHA-256 over title + content head.
- Title-similarity fallback for same-domain reprints.
- Provenance: `discovered_by` lists every query that surfaced the source.

## Quality model v2
Per-source components (all stored in `score_breakdown`):

| component | meaning |
|---|---|
| `semantic_relevance` | embedding cosine(query, title+snippet+content) |
| `query_coverage` | fraction of query terms present |
| `source_quality` | 0.60·type weight + 0.25·domain signal + 0.15·recency(neutral 0.5 if unknown) |
| `content_usefulness` | 0.7·coverage + 0.3·substantive-length factor |

`final = 0.50·relevance + 0.30·quality + 0.20·usefulness`,
`relevance = 0.55·cosine + 0.25·coverage + 0.15·title + 0.05·provider_raw`.

Human-readable `ranking_reasons` accompany every source ("Why did this source
rank here?"). Source type is a signal with recorded reasons, never a verdict:
government/academic sources can still rank low on relevance, and unknown
sources can rank high on coverage.

## Diversity
`select_diverse` applies MMR (λ=0.7): relevance minus embedding-redundancy
penalty, plus a source-type novelty bonus and a per-domain cap (2). This keeps
ten near-identical pages from crowding out a primary paper + government
report + independent review.

## Stopping criteria
Coverage of all sub-questions → diminishing returns (mostly duplicates) →
max rounds/sources → time budget (`RESEARCH_TIME_LIMIT`) → cost budget.
The winning condition is stored as `stop_reason` on every run and quoted in
the report method section.

## Modes
- `web`: provider search only.
- `private`: uploaded-document RAG only (cosine over stored chunk embeddings).
- `hybrid`: both merged through the same claim/evidence pipeline; `origin`
  (`web`/`uploaded`) is preserved per source, citation, and UI badge.
