# ResearchForge — API

Base URL: `http://localhost:8000`. All JSON unless noted.

- `GET /api/health` → `{status, version, mock_mode, llm_provider, search_provider}`
- `POST /api/research` `{question, depth?, mode? (web|private|hybrid), document_ids?, max_sources?, max_rounds?, strictness?}` → `202 {run_id, status}` (background run)
- `GET /api/research` → recent runs (with mode/confidence/stop_reason)
- `GET /api/research/{id}` → run summary incl. plan, counts, error, stop_reason, stage_ms, cost
- `GET /api/research/{id}/progress` → `{stage, progress, status, detail, mock_mode, mode, counts}`
- `GET /api/research/{id}/queries` → audited typed queries (query, type, reason, round, status)
- `GET /api/research/{id}/sources|/evidence|/claims` → lists (sources include origin/discovered_by/ranking_reasons)
- `GET /api/research/{id}/claims/{claim_id}/trace` → show-me-why trace (claim → evidence → source → ranking → verification)
- `GET /api/research/{id}/graph` → question→subquestion→claim→evidence→source graph
- `GET /api/research/{id}/timeline` → source chronology + claim/conflict timelines (dates never invented)
- `GET /api/research/{id}/report` → full report with findings, conflicts, citations, confidence, research_method, stop_reason, cost
- `GET /api/research/{id}/export.md` → Markdown (`text/markdown`) incl. method/stop_reason
- `GET /api/research/{id}/export.json` → structured `{question, subquestions, queries, sources (with provenance), evidence, claims, conflicts, verification, citations, report, confidence, metrics, metadata}`
- `POST /api/documents/upload?run_id=` (multipart `file`: pdf/txt/md) → `{document_id, num_chunks, duplicate, version}`
- `POST /api/documents/{id}/index` → indexed chunk count (v03 DocumentChunk + legacy)
- `POST /api/documents/{id}/reindex` → safe reindex for one document (dim validation)
- `GET /api/documents?limit=` → list documents (version/embedding_model)
- `GET /api/sources/{id}` → source + extracted evidence
- `GET /api/eval/dashboard` → aggregate metrics (confidence distribution, cost, diversity, benchmark versions)

Errors: `4xx` with plain message (no secrets); research failures surface as `status: failed` + `error` on the run.
