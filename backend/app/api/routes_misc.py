"""Source detail + evaluation dashboard + retrieval error APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.db_models import Claim, Evidence, Report, ResearchRun, RetrievalError, Source

sources_router = APIRouter(tags=["sources"])
eval_router = APIRouter(prefix="/api/eval", tags=["evaluation"])
error_router = APIRouter(prefix="/api/eval/errors", tags=["evaluation-errors"])


class CreateErrorRequest(BaseModel):
    run_id: str
    question_id: str
    query: str
    error_type: str
    source_id: str | None = None
    chunk_id: str | None = None
    expected: str | None = None
    actual: str | None = None
    severity: str = "medium"
    notes: str | None = None

    @field_validator("error_type")
    @classmethod
    def check_error_type(cls, v: str) -> str:
        valid = {"wrong_domain", "wrong_source", "right_source_wrong_chunk", "right_chunk_wrong_rank",
                 "missing_source", "duplicate_source", "query_decomposition_failure",
                 "evidence_extraction_failure", "source_metadata_failure", "conflict_misclassification"}
        if v not in valid:
            raise ValueError(f"Invalid error_type. Must be one of: {sorted(valid)}")
        return v

    @field_validator("severity")
    @classmethod
    def check_severity(cls, v: str) -> str:
        if v not in ("low", "medium", "high", "critical"):
            raise ValueError("severity must be low|medium|high|critical")
        return v


@sources_router.get("/api/sources/{source_id}")
def get_source(source_id: str, db: Session = Depends(get_db)):
    s = db.get(Source, source_id)
    if s is None:
        raise HTTPException(404, "Source not found")
    ev = db.query(Evidence).filter(Evidence.source_id == source_id).all()
    return {"id": s.id, "title": s.title, "url": s.url, "author": s.author,
            "publisher": s.publisher, "published_at": s.published_at,
            "source_type": s.source_type, "domain": s.domain, "description": s.description,
            "content": (s.content or "")[:8000], "relevance_score": s.relevance_score,
            "quality_score": s.quality_score, "score_breakdown": s.score_breakdown,
            "evidence": [{"id": e.id, "claim": e.claim, "quote": e.quote, "page": e.page,
                          "section": e.section} for e in ev]}


@eval_router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    from pathlib import Path
    runs = db.query(ResearchRun).all()
    n = len(runs) or 1
    avg_lat = sum(r.duration_ms or 0 for r in runs) / n
    claims = db.query(Claim).all()
    supported = sum(1 for c in claims if c.supported)
    reports = db.query(Report).all()
    cited = sum(len(r.citations or []) for r in reports)
    conf_dist: dict[str, int] = {"High": 0, "Medium": 0, "Low": 0}
    qualities: list[float] = []
    for r in reports:
        conf = r.confidence or {}
        if conf.get("label") in conf_dist:
            conf_dist[conf["label"]] += 1
        if isinstance(conf.get("source_quality"), (int, float)):
            qualities.append(conf["source_quality"])
    latencies = sorted(r.duration_ms or 0 for r in runs)
    cost = sum(r.estimated_cost_usd or 0 for r in runs)
    # versioned benchmark reports on disk (evaluation/reports/*.json)
    rep_dir = Path("evaluation/reports")
    versions = []
    if rep_dir.exists():
        for f in sorted(rep_dir.glob("*.json")):
            try:
                import json as _json
                data = _json.loads(f.read_text()[:20000])
                versions.append({"file": f.name, "aggregate": data.get("aggregate", {}),
                                 "version": data.get("version"), "n": len(data.get("runs", []))})
            except Exception:
                continue
    return {
        "runs": len(runs),
        "avg_latency_ms": round(avg_lat, 1),
        "median_latency_ms": latencies[len(latencies) // 2] if latencies else 0,
        "avg_sources_per_run": round(sum(r.num_sources for r in runs) / n, 2),
        "avg_claims_per_run": round(sum(r.num_claims for r in runs) / n, 2),
        "supported_claim_rate": round(supported / max(1, len(claims)), 3),
        "total_citations": cited,
        "unsupported_claim_rate": round(1 - supported / max(1, len(claims)), 3),
        "avg_source_quality": round(sum(qualities) / len(qualities), 3) if qualities else 0.0,
        "confidence_distribution": conf_dist,
        "total_estimated_cost_usd": round(cost, 4),
        "avg_search_calls": round(sum(r.search_calls or 0 for r in runs) / n, 2),
        "by_status": {k: sum(1 for r in runs if r.status == k) for k in
                      ("queued", "running", "completed", "partial", "failed")},
        "by_mode": {k: sum(1 for r in runs if (r.mode or "web") == k) for k in
                    ("web", "private", "hybrid")},
        "benchmark_versions": versions,
    }


@eval_router.get("/runs")
def eval_runs(db: Session = Depends(get_db)):
    rows = db.query(ResearchRun).order_by(ResearchRun.started_at.desc()).limit(50).all()
    return {"runs": [{"run_id": r.id, "status": r.status, "duration_ms": r.duration_ms,
                       "num_sources": r.num_sources, "num_claims": r.num_claims} for r in rows]}


@error_router.get("/")
def list_errors(
    run_id: str | None = None,
    error_type: str | None = None,
    severity: str | None = None,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(RetrievalError)
    if run_id:
        q = q.filter(RetrievalError.run_id == run_id)
    if error_type:
        q = q.filter(RetrievalError.error_type == error_type)
    if severity:
        q = q.filter(RetrievalError.severity == severity)
    total = q.count()
    rows = q.order_by(RetrievalError.created_at.desc()).offset(offset).limit(limit).all()
    return {"errors": [
        {"id": e.id, "run_id": e.run_id, "question_id": e.question_id,
         "query": e.query, "error_type": e.error_type, "source_id": e.source_id,
         "chunk_id": e.chunk_id, "expected": e.expected, "actual": e.actual,
         "severity": e.severity, "notes": e.notes, "created_at": e.created_at.isoformat()}
        for e in rows], "total": total, "limit": limit, "offset": offset}


@error_router.get("/summary")
def error_summary(run_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(RetrievalError)
    if run_id:
        q = q.filter(RetrievalError.run_id == run_id)
    total = q.count()
    by_type = db.query(RetrievalError.error_type, func.count(RetrievalError.id)).filter(
        RetrievalError.run_id == run_id if run_id else True).group_by(RetrievalError.error_type).all()
    by_severity = db.query(RetrievalError.severity, func.count(RetrievalError.id)).filter(
        RetrievalError.run_id == run_id if run_id else True).group_by(RetrievalError.severity).all()
    return {"total": total, "by_type": dict(by_type), "by_severity": dict(by_severity)}


@error_router.post("/")
def create_error(req: CreateErrorRequest, db: Session = Depends(get_db)):
    valid_types = {"wrong_domain", "wrong_source", "right_source_wrong_chunk", "right_chunk_wrong_rank",
                   "missing_source", "duplicate_source", "query_decomposition_failure",
                   "evidence_extraction_failure", "source_metadata_failure", "conflict_misclassification"}
    if req.error_type not in valid_types:
        raise HTTPException(400, f"Invalid error_type. Must be one of: {sorted(valid_types)}")
    if req.severity not in ("low", "medium", "high", "critical"):
        raise HTTPException(400, "severity must be low|medium|high|critical")
    e = RetrievalError(run_id=req.run_id, question_id=req.question_id, query=req.query,
                       error_type=req.error_type, source_id=req.source_id, chunk_id=req.chunk_id,
                       expected=req.expected, actual=req.actual, severity=req.severity, notes=req.notes)
    db.add(e)
    db.commit()
    return {"id": e.id, "created_at": e.created_at.isoformat()}
