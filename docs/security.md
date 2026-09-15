# ResearchForge — Security

Implemented and tested (see `backend/tests/test_v2_features.py`,
`test_api.py`, manual checks below):

- **Upload validation**: extension allowlist (`.pdf/.txt/.md`), size cap
  (`MAX_UPLOAD_MB`), path-traversal rejection, **magic-byte sniffing**
  (`sniff_content` rejects MZ/ELF/PK headers and non-PDF content with a
  `.pdf` name). Verified: renamed `.exe` → HTTP 400.
- **URL retrieval**: scheme allowlist (http/https), blocked loopback/private
  hosts and private-IP DNS resolution (`validate_url`, SSRF guard).
- **API validation**: all inputs via Pydantic (`ResearchCreate` bounds
  question length, `max_sources ≤ 30`, `max_rounds ≤ 5`, ≤10 documents).
- **Rate limiting**: in-memory sliding window on `POST /api/research`
  (`RATE_LIMIT_PER_MINUTE`, default 20/min/IP) → HTTP 429.
- **Secrets**: env-only, `.env.example` contains placeholders, `.gitignore`
  excludes `.env`; structured logs strip key/secret fields.
- **Uploads never executed**: parsed as data only (pypdf/text decode);
  parser failures return HTTP 400, never a stack trace with internals.

Manual validation checklist (run before releases):
1. `curl -F file=@evil.exe` → 400. 2. Fake-PDF header → 400.
3. `POST /api/research` with 5-char question → 422. 4. 21 rapid POSTs → 429.
5. Private-mode POST without `document_ids` → 400.
