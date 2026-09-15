-- 001_init.sql — portable schema (PostgreSQL). SQLite is auto-created via SQLAlchemy.
CREATE TABLE IF NOT EXISTS research_projects (
  id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research_questions (
  id TEXT PRIMARY KEY, project_id TEXT REFERENCES research_projects(id),
  question_text TEXT NOT NULL, depth TEXT DEFAULT 'standard', created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS research_runs (
  id TEXT PRIMARY KEY, question_id TEXT NOT NULL REFERENCES research_questions(id),
  status TEXT DEFAULT 'queued', stage TEXT DEFAULT 'queued', progress DOUBLE PRECISION DEFAULT 0,
  plan JSONB, error TEXT, mock_mode BOOLEAN DEFAULT TRUE,
  started_at TIMESTAMPTZ DEFAULT now(), finished_at TIMESTAMPTZ,
  duration_ms INTEGER, num_sources INTEGER DEFAULT 0, num_claims INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS sources (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
  title TEXT NOT NULL, url TEXT, author TEXT, publisher TEXT, published_at TEXT,
  accessed_at TIMESTAMPTZ DEFAULT now(), source_type TEXT DEFAULT 'unknown', domain TEXT,
  description TEXT, content TEXT, content_hash TEXT,
  relevance_score DOUBLE PRECISION DEFAULT 0, quality_score DOUBLE PRECISION DEFAULT 0,
  score_breakdown JSONB, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_sources_run ON sources(run_id);
CREATE TABLE IF NOT EXISTS source_chunks (
  id TEXT PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  run_id TEXT NOT NULL, chunk_index INTEGER DEFAULT 0, page INTEGER, section TEXT,
  text TEXT NOT NULL, embedding JSONB, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS evidence (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
  claim TEXT NOT NULL, quote TEXT NOT NULL, page INTEGER, section TEXT,
  relevance_score DOUBLE PRECISION DEFAULT 0, confidence_score DOUBLE PRECISION DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS claims (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, claim_text TEXT NOT NULL, claim_type TEXT DEFAULT 'factual',
  confidence DOUBLE PRECISION DEFAULT 0, confidence_breakdown JSONB, supported BOOLEAN DEFAULT FALSE,
  supporting_evidence_ids JSONB DEFAULT '[]', contradicting_evidence_ids JSONB DEFAULT '[]',
  verification JSONB, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL UNIQUE, question TEXT NOT NULL,
  executive_summary TEXT DEFAULT '', findings JSONB DEFAULT '[]', conflicts JSONB DEFAULT '[]',
  uncertainties JSONB DEFAULT '[]', limitations TEXT DEFAULT '', conclusion TEXT DEFAULT '',
  confidence JSONB, citations JSONB DEFAULT '[]', mock_mode BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, filename TEXT NOT NULL, content_hash TEXT, num_chunks INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now()
);
