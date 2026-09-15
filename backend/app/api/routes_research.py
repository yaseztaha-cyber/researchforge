"""Research REST API: create runs, poll progress, read sources/evidence/claims/report."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.agents.orchestrator import PROGRESS, run_research
from app.db.session import get_db
from app.models.db_models import Claim, Evidence, Report, ResearchQuestion, ResearchRun, Source
from app.schemas.research import ResearchCreate

router = APIRouter(prefix="/api/research", tags=["research"])


def _run_or_404(db: Session, run_id: str) -> ResearchRun:
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise HTTPException(404, f"Research run {run_id} not found")
    return run


@router.post("", status_code=202)
async def create_research(body: ResearchCreate, background: BackgroundTasks, db: Session = Depends(get_db)):
    run_id = str(uuid.uuid4())
    PROGRESS[run_id] = {"run_id": run_id, "stage": "queued", "progress": 0.0, "detail": "Queued"}

    def _runner() -> None:
        import asyncio
        from app.db.session import SessionLocal
        s = SessionLocal()
        try:
            asyncio.run(run_research(body.question, depth=body.depth,
                                     max_sources=body.max_sources, db=s, run_id=run_id))
        except Exception:
            pass
        finally:
            s.close()

    background.add_task(_runner)
    return {"run_id": run_id, "status": "queued"}


@router.get("/{run_id}")
def get_research(run_id: str, db: Session = Depends(get_db)):
    run = _run_or_404(db, run_id)
    q = db.get(ResearchQuestion, run.question_id)
    return {"run_id": run.id, "status": run.status, "stage": run.stage, "progress": run.progress,
            "question": q.question_text if q else None, "plan": run.plan,
            "num_sources": run.num_sources, "num_claims": run.num_claims,
            "error": run.error, "mock_mode": run.mock_mode,
            "duration_ms": run.duration_ms}


@router.get("/{run_id}/progress")
def get_progress(run_id: str, db: Session = Depends(get_db)):
    run = _run_or_404(db, run_id)
    mem = PROGRESS.get(run_id, {})
    return {"run_id": run_id, "stage": mem.get("stage", run.stage),
            "progress": mem.get("progress", run.progress), "status": run.status,
            "detail": mem.get("detail", ""), "mock_mode": run.mock_mode}


@router.get("/{run_id}/sources")
def get_sources(run_id: str, db: Session = Depends(get_db)):
    _run_or_404(db, run_id)
    rows = db.query(Source).filter(Source.run_id == run_id).all()
    return {"sources": [
        {"id": s.id, "title": s.title, "url": s.url, "author": s.author, "publisher": s.publisher,
         "published_at": s.published_at, "source_type": s.source_type, "domain": s.domain,
         "description": s.description, "relevance_score": s.relevance_score,
         "quality_score": s.quality_score, "score_breakdown": s.score_breakdown} for s in rows]}


@router.get("/{run_id}/evidence")
def get_evidence(run_id: str, db: Session = Depends(get_db)):
    _run_or_404(db, run_id)
    rows = db.query(Evidence).filter(Evidence.run_id == run_id).all()
    return {"evidence": [
        {"id": e.id, "claim": e.claim, "quote": e.quote, "source_id": e.source_id,
         "page": e.page, "section": e.section, "relevance_score": e.relevance_score,
         "confidence_score": e.confidence_score} for e in rows]}


@router.get("/{run_id}/claims")
def get_claims(run_id: str, db: Session = Depends(get_db)):
    _run_or_404(db, run_id)
    rows = db.query(Claim).filter(Claim.run_id == run_id).all()
    return {"claims": [
        {"id": c.id, "claim_text": c.claim_text, "claim_type": c.claim_type,
         "confidence": c.confidence, "supported": c.supported,
         "supporting_evidence_ids": c.supporting_evidence_ids,
         "contradicting_evidence_ids": c.contradicting_evidence_ids,
         "verification": c.verification, "confidence_breakdown": c.confidence_breakdown}
        for c in rows]}


@router.get("/{run_id}/report")
def get_report(run_id: str, db: Session = Depends(get_db)):
    run = _run_or_404(db, run_id)
    rep = db.query(Report).filter(Report.run_id == run_id).first()
    if rep is None:
        raise HTTPException(404, "Report not ready yet")
    return {"run_id": run_id, "question": rep.question, "executive_summary": rep.executive_summary,
            "findings": rep.findings, "conflicts": rep.conflicts,
            "uncertainties": rep.uncertainties, "limitations": rep.limitations,
            "conclusion": rep.conclusion, "confidence": rep.confidence,
            "citations": rep.citations, "mock_mode": rep.mock_mode,
            "status": run.status}


@router.get("")
def list_runs(limit: int = 20, db: Session = Depends(get_db)):
    if limit > 100:
        limit = 100
    runs = db.query(ResearchRun).order_by(ResearchRun.started_at.desc()).limit(limit).all()
    out = []
    for r in runs:
        q = db.get(ResearchQuestion, r.question_id)
        out.append({"run_id": r.id, "question": q.question_text[:140] if q else "",
                    "status": r.status, "stage": r.stage, "started_at": r.started_at.isoformat(),
                    "num_sources": r.num_sources, "num_claims": r.num_claims, "mock_mode": r.mock_mode})
    return {"runs": out}
