"""Source detail + evaluation dashboard + retrieval error APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.db_models import Claim, EvaluationLabel, Evidence, Report, ResearchRun, RetrievalError, Source

sources_router = APIRouter(tags=["sources"])
eval_router = APIRouter(prefix="/api/eval", tags=["evaluation"])
error_router = APIRouter(prefix="/api/eval/errors", tags=["evaluation-errors"])
human_router = APIRouter(prefix="/api/eval/human", tags=["human-eval"])


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
    e = RetrievalError(run_id=req.run_id, question_id=req.question_id, query=req.query,
                       error_type=req.error_type, source_id=req.source_id, chunk_id=req.chunk_id,
                       expected=req.expected, actual=req.actual, severity=req.severity, notes=req.notes)
    db.add(e)
    db.commit()
    return {"id": e.id, "created_at": e.created_at.isoformat()}


class CreateLabelRequest(BaseModel):
    run_id: str | None = None
    question_id: str | None = None
    claim_id: str | None = None
    source_id: str | None = None
    evidence_id: str | None = None
    label: str
    notes: str | None = None
    evaluator_id: str | None = None

    @field_validator("label")
    @classmethod
    def check_label(cls, v: str) -> str:
        valid = {"supported", "partially_supported", "unsupported", "contradicted"}
        if v not in valid:
            raise ValueError(f"label must be one of {sorted(valid)}")
        return v


@human_router.get("/tasks")
def get_human_tasks(limit: int = Query(10, le=50), offset: int = Query(0, ge=0), run_id: str | None = None, db: Session = Depends(get_db)):
    """Blind tasks: claim+evidence without system confidence. Evaluator labels after."""
    q = db.query(Claim).join(ResearchRun, Claim.run_id == ResearchRun.id)
    if run_id:
        q = q.filter(Claim.run_id == run_id)
    claims = q.order_by(Claim.created_at.desc()).offset(offset).limit(limit).all()
    out = []
    for c in claims:
        # Fetch evidence for blind display
        sup_ids = c.supporting_evidence_ids or []
        evs = []
        if sup_ids:
            from app.models.db_models import Evidence, Source
            ev_rows = db.query(Evidence).filter(Evidence.id.in_(sup_ids[:2])).all()
            for ev in ev_rows:
                src = db.get(Source, ev.source_id)
                evs.append({"evidence_id": ev.id, "quote": ev.quote[:600], "source_title": src.title if src else "Unknown", "source_type": src.source_type if src else "unknown"})
        # Do NOT expose system confidence here for blindness (separate endpoint reveals it)
        out.append({"claim_id": c.id, "claim_text": c.claim_text, "claim_type": c.claim_type, "run_id": c.run_id, "evidence": evs})
    return {"tasks": out, "limit": limit, "offset": offset}


@human_router.post("/labels")
def create_label(req: CreateLabelRequest, db: Session = Depends(get_db)):
    lab = EvaluationLabel(run_id=req.run_id, question_id=req.question_id, claim_id=req.claim_id,
                          source_id=req.source_id, evidence_id=req.evidence_id,
                          label=req.label, notes=req.notes, evaluator_id=req.evaluator_id or "anonymous")
    db.add(lab)
    db.commit()
    return {"id": lab.id, "created_at": lab.created_at.isoformat()}


@human_router.get("/labels")
def list_labels(run_id: str | None = None, claim_id: str | None = None, limit: int = Query(50, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    q = db.query(EvaluationLabel)
    if run_id:
        q = q.filter(EvaluationLabel.run_id == run_id)
    if claim_id:
        q = q.filter(EvaluationLabel.claim_id == claim_id)
    total = q.count()
    rows = q.order_by(EvaluationLabel.created_at.desc()).offset(offset).limit(limit).all()
    return {"labels": [{"id": r.id, "claim_id": r.claim_id, "run_id": r.run_id, "label": r.label, "notes": r.notes, "evaluator_id": r.evaluator_id, "created_at": r.created_at.isoformat(), "evaluation_version": r.evaluation_version} for r in rows], "total": total}


@human_router.get("/summary")
def human_summary(run_id: str | None = None, db: Session = Depends(get_db)):
    q = db.query(EvaluationLabel)
    if run_id:
        q = q.filter(EvaluationLabel.run_id == run_id)
    total = q.count()
    by_label = db.query(EvaluationLabel.label, func.count(EvaluationLabel.id)).filter(EvaluationLabel.run_id == run_id if run_id else True).group_by(EvaluationLabel.label).all()
    # Agreement: if multiple labels per claim, compute simple agreement
    from collections import defaultdict
    by_claim: dict[str, list[str]] = defaultdict(list)
    for r in q.all():
        if r.claim_id:
            by_claim[r.claim_id].append(r.label)
    agreed = sum(1 for vals in by_claim.values() if len(vals) > 1 and len(set(vals)) == 1)
    multi = sum(1 for vals in by_claim.values() if len(vals) > 1)
    return {"total": total, "by_label": dict(by_label), "agreement": {"multi_labeled_claims": multi, "agreed": agreed, "agreement_rate": round(agreed / multi, 3) if multi else None}}


@human_router.get("/calibration")
def calibration_report(run_id: str | None = None, db: Session = Depends(get_db)):
    """Brier + ECE when labels exist, else unavailable."""
    labels = db.query(EvaluationLabel).filter(EvaluationLabel.run_id == run_id if run_id else True).all()
    if len(labels) < 5:
        return {"status": "unavailable", "reason": "Calibration not available: insufficient labeled data (need >=5 labels)", "total_labels": len(labels)}
    # Map label to binary supported (supported/partially -> 1, unsupported/contradicted -> 0) for Brier; also keep 4-class for ECE
    # Need predicted confidence per claim
    claim_ids = [l.claim_id for l in labels if l.claim_id]
    claims = {c.id: c for c in db.query(Claim).filter(Claim.id.in_(claim_ids)).all()} if claim_ids else {}
    preds = []
    outcomes = []
    for lab in labels:
        cl = claims.get(lab.claim_id) if lab.claim_id else None
        if not cl:
            continue
        preds.append(float(cl.confidence or 0.5))
        outcomes.append(1 if lab.label in ("supported", "partially_supported") else 0)
    if len(preds) < 5:
        return {"status": "unavailable", "reason": "Insufficient labels with claim confidence", "total_labels": len(labels)}
    from evaluation.scripts.calibration import brier_score, expected_calibration_error
    try:
        brier = brier_score(preds, outcomes)
        ece = expected_calibration_error(preds, outcomes)
    except Exception as e:
        return {"status": "error", "reason": str(e)[:300]}
    return {"status": "available", "total_labels": len(labels), "brier_score": round(brier, 4), "expected_calibration_error": round(ece, 4), "note": "Heuristic confidence vs human label; not a probability"}
