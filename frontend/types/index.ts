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
  classification?: string;
}

export interface ReportData {
  run_id: string;
  question: string;
  executive_summary: string;
  research_method: string;
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
    claim_specificity?: number;
    contradiction_penalty?: number;
    method?: string;
  } | null;
  citations: Citation[];
  mock_mode: boolean;
  mode: string;
  stop_reason: string | null;
  stage_ms: Record<string, number> | null;
  cost: Record<string, number>;
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
  origin: string;
  discovered_by: string[];
  ranking_reasons: string[];
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
  sub_question: string | null;
  agreement: {
    supporting: number;
    contradicting: number;
    neutral: number;
    support_ratio: number;
    source_diversity: number;
    note: string;
  } | null;
}

export interface ClaimTrace {
  claim: { id: string; claim_text: string; claim_type: string; confidence: number; supported: boolean; sub_question: string | null };
  supporting: {
    evidence_id: string; claim: string; quote: string; page: number | null; section: string | null;
    relevance_score: number; confidence_score: number;
    source: {
      id: string; title: string; url: string | null; publisher: string | null; published_at: string | null;
      source_type: string; domain: string | null; origin: string;
      relevance_score: number; quality_score: number;
      score_breakdown: Record<string, unknown> | null; ranking_reasons: string[];
    } | null;
  }[];
  related_conflicts: Conflict[];
  agreement: ClaimItem["agreement"];
  verification: { supported: boolean; citation_valid: boolean; potential_overstatement: boolean; strings?: string[]; issues: string[] };
}

export interface GraphData {
  nodes: { id: string; type: string; label: string; supported?: boolean; claim_id?: string; evidence_id?: string; source_id?: string; source_type?: string; origin?: string }[];
  edges: { from: string; to: string; label: string }[];
}
