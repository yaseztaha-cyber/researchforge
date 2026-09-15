-- 003_v02.sql — v0.2 additions (PostgreSQL). SQLite dev DBs upgrade automatically at startup.
CREATE TABLE IF NOT EXISTS research_queries (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
  query TEXT NOT NULL,
  query_type TEXT DEFAULT 'broad',
  reason TEXT,
  round_number INTEGER DEFAULT 1,
  status TEXT DEFAULT 'ok',
  hits INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_queries_run ON research_queries(run_id);

ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS mode TEXT DEFAULT 'web';
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS stop_reason TEXT;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS stage_ms JSONB;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS llm_calls INTEGER DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS input_tokens INTEGER DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS output_tokens INTEGER DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS embedding_calls INTEGER DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS search_calls INTEGER DEFAULT 0;
ALTER TABLE research_runs ADD COLUMN IF NOT EXISTS estimated_cost_usd DOUBLE PRECISION DEFAULT 0;

ALTER TABLE sources ADD COLUMN IF NOT EXISTS origin TEXT DEFAULT 'web';
ALTER TABLE sources ADD COLUMN IF NOT EXISTS canonical_url TEXT;
ALTER TABLE sources ADD COLUMN IF NOT EXISTS discovered_by JSONB DEFAULT '[]';
ALTER TABLE sources ADD COLUMN IF NOT EXISTS ranking_reasons JSONB DEFAULT '[]';

ALTER TABLE claims ADD COLUMN IF NOT EXISTS sub_question TEXT;
ALTER TABLE claims ADD COLUMN IF NOT EXISTS agreement JSONB;

ALTER TABLE reports ADD COLUMN IF NOT EXISTS research_method TEXT DEFAULT '';
