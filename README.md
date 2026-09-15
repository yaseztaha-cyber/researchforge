# ResearchForge

### Research with evidence, not guesses.

```
Question
↓
Planning (typed, auditable queries)
↓
Retrieval (web and/or uploaded documents, deduplicated, diversity-ranked)
↓
Evidence (verbatim passages)
↓
Claims + conflicts + verification
↓
Report (every finding cited, every claim inspectable)
```

## Overview
ResearchForge is a **source-grounded AI research agent**. Given a research question it plans,
retrieves sources, extracts verbatim evidence, maps claims to evidence, detects conflicts,
synthesizes a cited report, and verifies every citation. Clicking any finding opens a
"show me why" trace: claim → evidence → source → ranking reasons → verification. It answers
*"why did you conclude that?"* with traceable evidence — not a black-box chatbot reply.

## Problem
Generic LLM chatbots generate fluent answers with fabricated citations, hidden uncertainty,
and no way to audit which source supports which claim.

## Solution
A multi-stage pipeline (planner → retrieval → ranking → extraction → claims → conflicts →
synthesis → verification) where the final report is generated **from structured evidence**,
and a separate verifier downgrades anything unsupported.

## Architecture
```
Next.js frontend → FastAPI → Orchestrator → Agents (planner/researcher/extractor/
conflict_detector/synthesizer/verifier) → Retrieval (web/mock/documents) → Evidence DB
→ pgvector RAG → Report + citations
```
See `docs/architecture.md`.

## Features
- Research planning with validated JSON (Pydantic) + rule-based fallback; **typed queries
  (broad/scientific/mechanism/…), all audited with reasons**
- Provider abstractions: `LLMProvider`, `SearchProvider`, `EmbeddingProvider`, `DocumentParser`
- Transparent source ranking (**semantic + coverage + quality + usefulness, formula stored
  per source, "why ranked here" in UI**) with MMR diversity selection
- Canonical-URL + content-hash dedup with query provenance
- Extractive evidence (verbatim quotes only — quotes are substrings of sources)
- Claim ↔ evidence mapping, **classified** conflict detection, agreement summaries,
  citation verification, **per-claim "show me why" trace + research graph**
- Confidence model with explainable components (documented heuristic, never fake probability)
- **Modes: web / private-documents / hybrid**; PDF/TXT/MD upload → chunking → embeddings → RAG
- Stop reasons, per-stage latency, LLM/search/embedding usage + cost estimates on every run
- Progress streaming with live counts, report + evidence split view, history, Markdown/JSON export
- Evaluation framework with real computed metrics + versioned benchmark reports + dashboard

## Tech Stack
Frontend: Next.js 14, TypeScript (strict), React 18 · Backend: Python 3.11+, FastAPI,
Pydantic v2, SQLAlchemy 2 · DB: PostgreSQL + pgvector (SQLite fallback for local dev) ·
AI: provider abstraction (mock offline + OpenAI-compatible API).

## Research Pipeline
Question → plan → queries → search → dedup/rank → chunk/embed → extract → claims →
conflicts → synthesize → verify → confidence → report. Stopping criteria: coverage
thresholds, diminishing returns, max rounds, cost budget (`MAX_*` env vars).

## Database Schema
`research_projects, research_questions, research_runs, sources, source_chunks,
evidence, claims, reports, documents`. Migrations in `database/migrations/`.

## Evidence Model
`evidence(claim, quote VERBATIM, source_id, page, section, relevance, confidence)`;
`claims(claim_text, type, confidence+breakdown, supported, supporting/contradicting ids)`.

## Citation Verification
`Claim → Evidence → Source → URL/page`. Verifier flags overstatement (e.g. correlation
written as causation), missing support, keyword drift; dangling `[n]` markers are reported.

## RAG
Document → structure-aware chunking (heading → paragraph → sentence) with page/section/heading/char offsets → hash-384 embeddings (batch + LRU cache) → PostgreSQL + pgvector (`ivfflat` cosine, `hnsw` for larger corpora) / SQLite brute-force fallback → vector + hybrid retrieval → MMR diversity → evidence (see `docs/rag.md`). Document versioning via `content_hash`; `POST /api/documents/{id}/reindex` or `python scripts/reindex.py --document <id>`.

## Installation
```bash
# backend
cd backend && pip install -r requirements.txt && cp .env.example .env
uvicorn app.main:app --reload  # http://localhost:8000 (SQLite dev DB, no Docker needed)
# frontend
cd frontend && npm install && npm run dev  # http://localhost:3000
```

## Environment Variables
See `backend/.env.example`: `DATABASE_URL, LLM_PROVIDER, LLM_API_KEY, LLM_BASE_URL,
MODEL_NAME, EMBEDDING_MODEL, SEARCH_PROVIDER, SEARCH_API_KEY, MAX_SEARCH_ROUNDS,
MAX_QUERIES, MAX_RESULTS_PER_QUERY, MAX_SOURCES, MAX_RELEVANT_SOURCES,
MAX_COST_PER_RESEARCH, REQUEST_TIMEOUT, RESEARCH_TIME_LIMIT, EVIDENCE_STRICTNESS,
RELEVANCE_THRESHOLD, RATE_LIMIT_PER_MINUTE, VECTOR_TOP_K, HYBRID_*_WEIGHT,
VECTOR_MIN_SIMILARITY, CHUNK_TARGET_TOKENS, CHUNK_OVERLAP_TOKENS`.

## Local Development
Default is **mock mode** (deterministic fixtures, clearly labeled in UI). Set real keys
+ `*_PROVIDER` to non-mock values for live research. CLI: `cd backend && python research.py "question"`.

## API
`POST /api/research · GET /api/research/{id}[ /progress|/sources|/evidence|/claims|/report|/export.md|/export.json] · POST /api/documents/upload · GET /api/sources/{id} · GET /api/eval/dashboard`. See `docs/api.md`.

## Evaluation
```bash
python evaluation/scripts/run_evaluation.py --dataset evaluation/dataset/questions_v03.jsonl --out evaluation/reports/v0.3_mock.json  # 60-question multi-domain
python evaluation/scripts/run_evaluation.py --dataset evaluation/dataset/questions.jsonl --out evaluation/reports/v0.2_mock.json --limit 24
python evaluation/scripts/metrics.py <export.json>
python evaluation/scripts/calibration.py  # Brier/ECE when labels exist else "unavailable"
python evaluation/scripts/performance.py  # vector vs hybrid, cache, serial vs parallel (→ evaluation/reports/performance/latest.json)
```
Metrics: citation correctness/completeness, unsupported/overstatement rate, retrieval precision + recall (proxy), source diversity, redundancy, evidence relevance/alignment, latency & cost. Dashboard at `/evaluation` (live DB metrics + versioned benchmark reports + confidence distribution).

Latest honest numbers:
- **Controlled fixture benchmark (mock, desalination subset):** correctness 1.0, completeness 1.0, unsupported 0.0, precision **0.69** (v0.1 parity — preserved).
- **Controlled fixture benchmark (mock, full 24-question):** precision **0.35** — documented drop because fixtures cover desalination only, not hidden.
- **Multi-domain benchmark (mock, 60-question v0.3):** *run `python evaluation/scripts/run_evaluation.py` to reproduce* — scores are computed live, not hardcoded. No live-provider numbers claimed without live evaluation (labels: `mock`, `recorded`, `live`).
- **Live/recorded:** use `SEARCH_PROVIDER=replay` with sanitized fixtures under `evaluation/fixtures/providers/search/` (see `docs/benchmark.md`). No 95% claims without real evaluation.

## Performance
Extractive-first pipeline minimizes LLM calls; embeddings/content cached by content hash + LRU; hybrid RAG adds ~1 ms overhead (measured: vector 2.6 ms, hybrid 3.7 ms on SQLite fallback); research runs as background tasks with polling (no blocked UI). Budgets stop gracefully: `"Research stopped because ..."`, not fake completion. See `docs/performance.md` and `evaluation/reports/performance/latest.json`.

## Screenshots
Add `docs/screenshots/` captures of landing, progress, and report views.

## Demo
Run locally (above) or deploy frontend to Vercel + backend to any Python host with Postgres.

## Roadmap
Live-search provider hardening, user auth, scheduled re-verification, multilingual retrieval.

## Limitations
Mock fixtures are not real literature; live mode needs API keys; conflict detection is
heuristic; confidence is a transparent heuristic, not calibrated probability (calibration
tooling reports "unavailable" without labeled data); benchmark precision off-domain is low
because fixtures are desalination-only.

## Versions
- **v0.1.0** — verified core evidence-grounded pipeline (17 tests, CLI+HTTP working).
- **v0.2.0** — typed/audited queries, quality model v2 + diversity ranking, web/private/hybrid
  modes with RAG, show-me-why traces, research graph, classified conflicts, confidence v2,
  stop reasons, cost/latency tracing, 24-question benchmark, rate limiting, 38 tests.
- **v0.3.0** — structure-aware chunking + pgvector RAG (vector + hybrid + MMR), document versioning & reindex, web-provider hardening with retries, record/replay fixtures, 60-question multi-domain benchmark, evidence-quality metrics, evidence timeline, performance/cost benchmarking, calibration infra ("unavailable" without labels), 61+ tests.

## Future Work
Calibrated confidence, human-feedback loop, deeper academic APIs (Crossref/OpenAlex).

## License
MIT.
