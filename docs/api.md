# ResearchForge — API

Base URL: `http://localhost:8000`. All JSON unless noted.

- `GET /api/health` → `{status, version, mock_mode, llm_provider, search_provider}`
- `POST /api/research` `{question, depth?, max_sources?}` → `202 {run_id, status}` (background run)
- `GET /api/research` → recent runs
- `GET /api/research/{id}` → run summary incl. plan, counts, error
- `GET /api/research/{id}/progress` → `{stage, progress, status, detail, mock_mode}` (poll every ~1.5s)
- `GET /api/research/{id}/sources|/evidence|/claims` → lists
- `GET /api/research/{id}/report` → full report with findings, conflicts, citations, confidence
- `GET /api/research/{id}/export.md` → Markdown (`text/markdown`)
- `GET /api/research/{id}/export.json` → structured `{question, plan, sources, evidence, claims, citations, report, confidence, metadata}`
- `POST /api/documents/upload?run_id=` (multipart `file`: pdf/txt/md) → `{document_id, num_chunks, duplicate}`
- `POST /api/documents/{id}/index` → indexed chunk count
- `GET /api/sources/{id}` → source + extracted evidence
- `GET /api/eval/dashboard` → aggregate engineering metrics

Errors: `4xx` with plain message (no secrets); research failures surface as `status: failed` + `error` on the run.
