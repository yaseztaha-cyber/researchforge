"""Database models. Portable across SQLite (dev) and PostgreSQL+pgvector (prod)."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.session import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


JSONType = JSON().with_variant(JSONB(), "postgresql")


class ResearchProject(Base):
    __tablename__ = "research_projects"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ResearchQuestion(Base):
    __tablename__ = "research_questions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("research_projects.id"), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    depth: Mapped[str] = mapped_column(String(20), default="standard")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ResearchRun(Base):
    __tablename__ = "research_runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_questions.id"))
    status: Mapped[str] = mapped_column(String(30), default="queued")  # queued|running|completed|partial|failed
    stage: Mapped[str] = mapped_column(String(60), default="queued")
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    plan: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    mock_mode: Mapped[bool] = mapped_column(default=True)
    # v0.2: mode, stop reason, trace, cost/latency
    mode: Mapped[str] = mapped_column(String(20), default="web")  # web|private|hybrid
    stop_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    stage_ms: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    llm_calls: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    embedding_calls: Mapped[int] = mapped_column(Integer, default=0)
    search_calls: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_sources: Mapped[int] = mapped_column(Integer, default=0)
    num_claims: Mapped[int] = mapped_column(Integer, default=0)


class ResearchQuery(Base):
    """Auditable record of every search query: what ran, what kind, why, when."""
    __tablename__ = "research_queries"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_runs.id"), index=True)
    query: Mapped[str] = mapped_column(String(300), nullable=False)
    query_type: Mapped[str] = mapped_column(String(30), default="broad")
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    round_number: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok|failed
    hits: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Source(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_runs.id"), index=True)
    title: Mapped[str] = mapped_column(String(800), nullable=False)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    author: Mapped[str | None] = mapped_column(String(400), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(400), nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    accessed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    source_type: Mapped[str] = mapped_column(String(40), default="unknown")
    domain: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    score_breakdown: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    # v0.2: origin + dedup provenance
    origin: Mapped[str] = mapped_column(String(20), default="web")  # web|uploaded
    canonical_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_by: Mapped[list] = mapped_column(JSONType, default=list)  # queries that found it
    ranking_reasons: Mapped[list] = mapped_column(JSONType, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chunks: Mapped[list["SourceChunk"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="source", cascade="all, delete-orphan")


class SourceChunk(Base):
    __tablename__ = "source_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id"), index=True)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_runs.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(400), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    source: Mapped[Source] = relationship(back_populates="chunks")


class Evidence(Base):
    __tablename__ = "evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_runs.id"), index=True)
    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id"), index=True)
    claim: Mapped[str] = mapped_column(Text, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)  # verbatim passage
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(400), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    source: Mapped[Source] = relationship(back_populates="evidence_items")


class Claim(Base):
    __tablename__ = "claims"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_runs.id"), index=True)
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(30), default="factual")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_breakdown: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    supported: Mapped[bool] = mapped_column(default=False)
    supporting_evidence_ids: Mapped[list] = mapped_column(JSONType, default=list)
    contradicting_evidence_ids: Mapped[list] = mapped_column(JSONType, default=list)
    verification: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    sub_question: Mapped[str | None] = mapped_column(Text, nullable=True)  # v0.2 graph link
    agreement: Mapped[dict | None] = mapped_column(JSONType, nullable=True)  # v0.2 AgreementSummary
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("research_runs.id"), unique=True, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, default="")
    findings: Mapped[list] = mapped_column(JSONType, default=list)
    conflicts: Mapped[list] = mapped_column(JSONType, default=list)
    uncertainties: Mapped[list] = mapped_column(JSONType, default=list)
    limitations: Mapped[str] = mapped_column(Text, default="")
    conclusion: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    citations: Mapped[list] = mapped_column(JSONType, default=list)
    mock_mode: Mapped[bool] = mapped_column(default=True)
    research_method: Mapped[str] = mapped_column(Text, default="")  # v0.2 auditable method
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    num_chunks: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    first_seen: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    chunks_v3: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """v0.3 production chunk table with pgvector support and full metadata."""
    __tablename__ = "document_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(String(36), ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(400), nullable=True)
    heading: Mapped[str | None] = mapped_column(String(400), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    embedding: Mapped[list | None] = mapped_column(JSONType, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_dim: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)

    document: Mapped[Document] = relationship(back_populates="chunks_v3")


Index("ix_evidence_run", Evidence.run_id)
Index("ix_claims_run", Claim.run_id)
