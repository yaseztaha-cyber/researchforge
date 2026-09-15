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
Upload → parse → chunk (page/section metadata) → hash-384 embeddings (offline) →
semantic retrieval filtered by run/source/type.

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
RELEVANCE_THRESHOLD, RATE_LIMIT_PER_MINUTE`.

## Local Development
Default is **mock mode** (deterministic fixtures, clearly labeled in UI). Set real keys
+ `*_PROVIDER` to non-mock values for live research. CLI: `cd backend && python research.py "question"`.

## API
`POST /api/research · GET /api/research/{id}[ /progress|/sources|/evidence|/claims|/report|/export.md|/export.json] · POST /api/documents/upload · GET /api/sources/{id} · GET /api/eval/dashboard`. See `docs/api.md`.

## Evaluation
```bash
python evaluation/scripts/run_evaluation.py --out evaluation/reports/v0.2_mock.json  # 24-question benchmark
python evaluation/scripts/metrics.py <export.json>
```
Metrics: citation correctness/completeness, unsupported-claim rate, retrieval precision,
latency. Dashboard at `/evaluation` (live DB metrics + versioned benchmark reports).
Latest honest numbers (mock fixtures, desalination subset): correctness 1.0,
completeness 1.0, unsupported 0.0, precision 0.69. Full 24-question set scores lower
on precision (0.35) because fixtures only cover desalination — documented, not hidden.

## Performance
Extractive-first pipeline minimizes LLM calls; embeddings/content cached by content hash;
research runs as background tasks with polling (no blocked UI).

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

## Future Work
Calibrated confidence, human-feedback loop, deeper academic APIs (Crossref/OpenAlex).

## License
MIT.
