export interface Citation {
  index: number;
  evidence_id: string;
  source_id: string;
  source_title: string;
  url: string | null;
  page?: number | null;
  section?: string | null;
  quote?: string;
}

export interface Finding {
  title: string;
  text: string;
  citation_ids: number[];
}

export interface Conflict {
  topic: string;
  position_a: string;
  source_a: string;
  position_b: string;
  source_b: string;
  possible_reason: string;
}

export interface ReportData {
  run_id: string;
  question: string;
  executive_summary: string;
  findings: Finding[];
  conflicts: Conflict[];
  uncertainties: string[];
  limitations: string;
  conclusion: string;
  confidence: {
    overall: number;
    label: string;
    evidence_coverage: number;
    source_agreement: number;
    source_quality: number;
    contradiction_level: string;
    citation_completeness: number;
  } | null;
  citations: Citation[];
  mock_mode: boolean;
  status: string;
}

export interface SourceItem {
  id: string;
  title: string;
  url: string | null;
  author: string | null;
  publisher: string | null;
  published_at: string | null;
  source_type: string;
  domain: string | null;
  description: string | null;
  relevance_score: number;
  quality_score: number;
  score_breakdown: Record<string, unknown> | null;
}

export interface EvidenceItem {
  id: string;
  claim: string;
  quote: string;
  source_id: string;
  page: number | null;
  section: string | null;
  relevance_score: number;
  confidence_score: number;
}

export interface ClaimItem {
  id: string;
  claim_text: string;
  claim_type: string;
  confidence: number;
  supported: boolean;
  supporting_evidence_ids: string[];
  contradicting_evidence_ids: string[];
}
