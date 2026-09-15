"""Pydantic schemas: every structured LLM output is validated here before touching the DB."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, field_validator

SourceType = Literal[
    "government", "academic", "scientific", "university", "institutional",
    "technical_documentation", "news", "blog", "unknown",
]
ClaimType = Literal["factual", "statistical", "causal", "comparative", "interpretation", "uncertainty"]


class QuerySpec(BaseModel):
    """One auditable search query: what to run, what kind, and why."""
    query: str = Field(min_length=3, max_length=300)
    query_type: Literal["broad", "scientific", "mechanism", "consequence", "recent",
                        "mitigation", "controversy", "followup"] = "broad"
    reason: str = Field(default="", max_length=500)


class ResearchPlan(BaseModel):
    original_question: str = Field(min_length=5, max_length=2000)
    sub_questions: list[str] = Field(min_length=1, max_length=8)
    search_queries: list[QuerySpec] = Field(min_length=1, max_length=12)
    search_strategy: str = Field(min_length=10, max_length=2000)
    expected_evidence_types: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)

    @field_validator("sub_questions")
    @classmethod
    def _nonempty(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if s and s.strip()]
        if not cleaned:
            raise ValueError("must contain at least one non-empty string")
        return cleaned


class SourceCandidate(BaseModel):
    title: str = Field(min_length=3, max_length=800)
    url: str | None = None
    author: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    source_type: SourceType = "unknown"
    domain: str | None = None
    description: str | None = None
    content: str = Field(default="", max_length=200_000)


class EvidenceItem(BaseModel):
    claim: str = Field(min_length=5, max_length=1000)
    quote: str = Field(min_length=10, max_length=5000, description="Verbatim passage from the source")
    source_id: str = Field(min_length=1)
    page: int | None = None
    section: str | None = None
    relevance_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)


class ClaimItem(BaseModel):
    claim_text: str = Field(min_length=5, max_length=1000)
    claim_type: ClaimType = "factual"
    confidence: float = Field(ge=0.0, le=1.0)
    supported: bool = False
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)


class ConflictItem(BaseModel):
    topic: str
    position_a: str
    source_a: str
    position_b: str
    source_b: str
    possible_reason: str = "reason unclear"
    classification: Literal["direct_contradiction", "methodological", "population",
                            "time_period", "measurement", "definition", "scope",
                            "insufficient_evidence", "unclear"] = "unclear"


class AgreementSummary(BaseModel):
    supporting: int = 0
    contradicting: int = 0
    neutral: int = 0
    support_ratio: float = 0.0
    source_diversity: float = 0.0  # distinct source-type count / sources
    note: str = "Source count alone does not establish truth."


class VerificationResult(BaseModel):
    claim: str
    supported: bool
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class ConfidenceBreakdown(BaseModel):
    overall: float = Field(ge=0.0, le=1.0)
    label: Literal["Low", "Medium", "High"]
    evidence_coverage: float = Field(ge=0.0, le=1.0)
    source_agreement: float = Field(ge=0.0, le=1.0)
    source_quality: float = Field(ge=0.0, le=1.0)
    contradiction_level: Literal["Low", "Medium", "High"]
    citation_completeness: float = Field(ge=0.0, le=1.0)
    claim_specificity: float = Field(ge=0.0, le=1.0, default=0.5)
    contradiction_penalty: float = Field(ge=0.0, le=1.0, default=0.0)
    method: str = ("0.25*coverage + 0.20*quality + 0.15*agreement + 0.20*citation_completeness "
                   "+ 0.10*specificity - 0.10*contradiction_penalty; heuristic, not a probability.")


class FindingItem(BaseModel):
    title: str
    text: str
    citation_ids: list[str] = Field(default_factory=list)


# --- API contracts ---

class ResearchCreate(BaseModel):
    question: str = Field(min_length=5, max_length=2000)
    depth: Literal["standard", "deep"] = "standard"
    mode: Literal["web", "private", "hybrid"] = "web"
    document_ids: list[str] = Field(default_factory=list, max_length=10)
    max_sources: int | None = Field(default=None, ge=1, le=30)
    max_rounds: int | None = Field(default=None, ge=1, le=5)
    strictness: Literal["lenient", "standard", "strict"] | None = None


class CitationOut(BaseModel):
    index: int
    evidence_id: str
    source_id: str
    source_title: str
    url: str | None = None
