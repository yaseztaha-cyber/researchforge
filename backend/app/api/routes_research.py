"""Research REST API: create runs, poll progress, read sources/evidence/claims/report."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.agents.orchestrator import PROGRESS, run_research
from app.core.config import get_settings
from app.db.session import get_db
from app.models.db_models import Claim, Evidence, Report, ResearchQuery, ResearchQuestion, ResearchRun, Source
from app.schemas.research import ResearchCreate

router = APIRouter(prefix="/api/research", tags=["research"])

# --- Minimal in-memory sliding-window rate limiter for expensive endpoints ---
_HITS: dict[str, list[float]] = defaultdict(list)


def rate_limit(request: Request) -> None:
    settings = get_settings()
    if settings.RATE_LIMIT_PER_MINUTE <= 0:
        return
    key = request.client.host if request.client else "unknown"
    now = time.time()
    window = [t for t in _HITS[key] if now - t < 60]
    _HITS[key] = window
    if len(window) >= settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(429, "Rate limit exceeded for research creation; try again shortly.")
    window.append(now)


def _run_or_404(db: Session, run_id: str) -> ResearchRun:
    run = db.get(ResearchRun, run_id)
    if run is None:
        raise HTTPException(404, f"Research run {run_id} not found")
    return run


def _cost(run: ResearchRun) -> dict:
    return {"llm_calls": run.llm_calls, "input_tokens": run.input_tokens,
            "output_tokens": run.output_tokens, "embedding_calls": run.embedding_calls,
            "search_calls": run.search_calls, "estimated_cost_usd": run.estimated_cost_usd}


@router.post("", status_code=202)
async def create_research(body: ResearchCreate, background: BackgroundTasks,
                          request: Request, db: Session = Depends(get_db),
                          _: None = Depends(rate_limit)):
    if body.mode in ("private", "hybrid") and not body.document_ids:
        raise HTTPException(400, "mode 'private'/'hybrid' requires at least one uploaded document_id.")
    run_id = str(uuid.uuid4())
    PROGRESS[run_id] = {"run_id": run_id, "stage": "queued", "progress": 0.0,
                        "detail": "Queued", "counts": {}}

    def _runner() -> None:
        import asyncio
        from app.db.session import SessionLocal
        s = SessionLocal()
        try:
            asyncio.run(run_research(body.question, depth=body.depth,
                                     max_sources=body.max_sources, db=s, run_id=run_id,
                                     mode=body.mode, document_ids=body.document_ids,
                                     max_rounds=body.max_rounds, strictness=body.strictness))
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
            "error": run.error, "mock_mode": run.mock_mode, "mode": run.mode,
            "stop_reason": run.stop_reason, "stage_ms": run.stage_ms,
            "cost": _cost(run), "duration_ms": run.duration_ms}


@router.get("/{run_id}/progress")
def get_progress(run_id: str, db: Session = Depends(get_db)):
    run = _run_or_404(db, run_id)
    mem = PROGRESS.get(run_id, {})
    return {"run_id": run_id, "stage": mem.get("stage", run.stage),
            "progress": mem.get("progress", run.progress), "status": run.status,
            "detail": mem.get("detail", ""), "mock_mode": run.mock_mode,
            "mode": run.mode, "counts": mem.get("counts", {}),
            "num_sources": run.num_sources, "num_claims": run.num_claims}


@router.get("/{run_id}/queries")
def get_queries(run_id: str, db: Session = Depends(get_db)):
    _run_or_404(db, run_id)
    rows = db.query(ResearchQuery).filter(ResearchQuery.run_id == run_id).order_by(
        ResearchQuery.round_number, ResearchQuery.created_at).all()
    return {"queries": [{"query": r.query, "query_type": r.query_type, "reason": r.reason,
                         "round_number": r.round_number, "status": r.status, "hits": r.hits}
                        for r in rows]}


@router.get("/{run_id}/sources")
def get_sources(run_id: str, db: Session = Depends(get_db)):
    _run_or_404(db, run_id)
    rows = db.query(Source).filter(Source.run_id == run_id).all()
    return {"sources": [
        {"id": s.id, "title": s.title, "url": s.url, "author": s.author, "publisher": s.publisher,
         "published_at": s.published_at, "source_type": s.source_type, "domain": s.domain,
         "description": s.description, "relevance_score": s.relevance_score,
         "quality_score": s.quality_score, "score_breakdown": s.score_breakdown,
         "origin": s.origin, "discovered_by": s.discovered_by or [],
         "ranking_reasons": s.ranking_reasons or []} for s in rows]}


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
         "verification": c.verification, "confidence_breakdown": c.confidence_breakdown,
         "sub_question": c.sub_question, "agreement": c.agreement}
        for c in rows]}


@router.get("/{run_id}/claims/{claim_id}/trace")
def get_claim_trace(run_id: str, claim_id: str, db: Session = Depends(get_db)):
    """Show-me-why: full traceability for one claim (no chain-of-thought, only metadata)."""
    _run_or_404(db, run_id)
    claim = db.get(Claim, claim_id)
    if claim is None or claim.run_id != run_id:
        raise HTTPException(404, "Claim not found for this run")
    ev_rows = db.query(Evidence).filter(Evidence.run_id == run_id).all()
    src_rows = {s.id: s for s in db.query(Source).filter(Source.run_id == run_id).all()}
    by_id = {e.id: e for e in ev_rows}

    def _ev(eid: str) -> dict | None:
        e = by_id.get(eid)
        if e is None:
            return None
        s = src_rows.get(e.source_id)
        return {"evidence_id": e.id, "claim": e.claim, "quote": e.quote, "page": e.page,
                "section": e.section, "relevance_score": e.relevance_score,
                "confidence_score": e.confidence_score,
                "source": {"id": s.id, "title": s.title, "url": s.url, "publisher": s.publisher,
                           "published_at": s.published_at, "source_type": s.source_type,
                           "domain": s.domain, "origin": s.origin,
                           "relevance_score": s.relevance_score, "quality_score": s.quality_score,
                           "score_breakdown": s.score_breakdown,
                           "ranking_reasons": s.ranking_reasons or []} if s else None}

    supporting = [x for x in (_ev(i) for i in (claim.supporting_evidence_ids or [])) if x]
    # contradicting: conflicts touching the claim's sources
    rep = db.query(Report).filter(Report.run_id == run_id).first()
    claim_srcs = {e["source"]["id"] for e in supporting if e.get("source")}
    related_conflicts = [c for c in (rep.conflicts if rep else [])
                         if c.get("source_a") in claim_srcs or c.get("source_b") in claim_srcs]
    issues = (claim.confidence_breakdown or {}).get("issues", []) if isinstance(
        claim.confidence_breakdown, dict) else []
    return {"claim": {"id": claim.id, "claim_text": claim.claim_text,
                      "claim_type": claim.claim_type, "confidence": claim.confidence,
                      "supported": claim.supported, "sub_question": claim.sub_question},
            "supporting": supporting,
            "related_conflicts": related_conflicts,
            "agreement": claim.agreement,
            "verification": {"supported": claim.supported, "citation_valid": bool(supporting),
                             "potential_overstatement": any(
                                 "strong wording" in i or "overstat" in i.lower() for i in issues),
                             "issues": issues}}


@router.get("/{run_id}/graph")
def get_graph(run_id: str, db: Session = Depends(get_db)):
    """Question -> sub-questions -> claims -> evidence -> sources graph data."""
    run = _run_or_404(db, run_id)
    q = db.get(ResearchQuestion, run.question_id)
    claims = db.query(Claim).filter(Claim.run_id == run_id).all()
    ev_rows = db.query(Evidence).filter(Evidence.run_id == run_id).all()
    sources = db.query(Source).filter(Source.run_id == run_id).all()
    nodes: list[dict] = [{"id": f"q:{run_id}", "type": "question",
                          "label": (q.question_text[:90] + "…") if q and len(q.question_text) > 90 else (q.question_text if q else "")}]
    edges: list[dict] = []
    subs = sorted({c.sub_question for c in claims if c.sub_question})
    for i, sq in enumerate(subs):
        sid = f"sq:{i}"
        nodes.append({"id": sid, "type": "subquestion", "label": sq[:90]})
        edges.append({"from": f"q:{run_id}", "to": sid, "label": "decomposes"})
    for c in claims:
        cid = f"c:{c.id}"
        nodes.append({"id": cid, "type": "claim", "label": c.claim_text[:90],
                      "supported": c.supported, "claim_id": c.id})
        if c.sub_question and c.sub_question in subs:
            edges.append({"from": f"sq:{subs.index(c.sub_question)}", "to": cid, "label": "yields"})
        else:
            edges.append({"from": f"q:{run_id}", "to": cid, "label": "yields"})
        for eid in (c.supporting_evidence_ids or []):
            edges.append({"from": cid, "to": f"e:{eid}", "label": "supported-by"})
    for e in ev_rows:
        nodes.append({"id": f"e:{e.id}", "type": "evidence", "label": e.quote[:90],
                      "evidence_id": e.id, "source_id": e.source_id})
        edges.append({"from": f"e:{e.id}", "to": f"s:{e.source_id}", "label": "from"})
    for s in sources:
        nodes.append({"id": f"s:{s.id}", "type": "source",
                      "label": s.title[:90], "source_id": s.id,
                      "source_type": s.source_type, "origin": s.origin})
    return {"nodes": nodes, "edges": edges}


@router.get("/{run_id}/timeline")
def get_timeline(run_id: str, db: Session = Depends(get_db)):
    """Evidence timeline: source chronology + claim-anchored events. Dates never invented."""
    _run_or_404(db, run_id)
    sources = db.query(Source).filter(Source.run_id == run_id).all()
    ev_rows = db.query(Evidence).filter(Evidence.run_id == run_id).all()
    claims = db.query(Claim).filter(Claim.run_id == run_id).all()
    report = db.query(Report).filter(Report.run_id == run_id).first()
    # Build source timeline: parse published_at if present, else fallback to accessed_at
    import re
    from datetime import datetime, timezone

    def _parse_date(s: str | None) -> tuple[datetime | None, str | None]:
        if not s:
            return None, None
        # Try ISO or YYYY-MM-DD or YYYY
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m", "%Y"):
            try:
                dt = datetime.strptime(s.strip(), fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt, s.strip()
            except Exception:
                continue
        m = re.search(r"(19|20)\d{2}", s)
        if m:
            try:
                dt = datetime(int(m.group(0)), 1, 1, tzinfo=timezone.utc)
                return dt, s.strip()
            except Exception:
                pass
        return None, s.strip()

    src_events = []
    for so in sources:
        dt_parsed, raw = _parse_date(so.published_at)
        # Never invent: if no parse, use accessed_at but mark as approximate
        is_approx = dt_parsed is None
        if is_approx:
            fallback = so.accessed_at or so.created_at
            dt_parsed = fallback.replace(tzinfo=timezone.utc) if fallback and fallback.tzinfo is None else fallback
        src_events.append({
            "source_id": so.id, "title": so.title, "url": so.url, "publisher": so.publisher,
            "source_type": so.source_type, "domain": so.domain, "origin": so.origin,
            "published_at": so.published_at, "parsed_date": dt_parsed.isoformat() if dt_parsed else None,
            "is_approximate": is_approx,
            "relevance_score": so.relevance_score, "quality_score": so.quality_score,
        })
    # Sort undated last; dated chronologically
    src_events.sort(key=lambda x: (x["parsed_date"] is None, x["parsed_date"] or ""))
    # Claim-anchored chronology: group evidence per claim by source date
    ev_by_id = {e.id: e for e in ev_rows}
    src_by_id = {s.id: s for s in sources}
    claim_timeline = []
    for cl in claims[:20]:
        # Supporting evidence sorted by source date
        sup = [ev_by_id[eid] for eid in (cl.supporting_evidence_ids or []) if eid in ev_by_id]
        def _ev_date(ev):
            so = src_by_id.get(ev.source_id)
            dt_parsed, _ = _parse_date(so.published_at if so else None)
            return dt_parsed.isoformat() if dt_parsed else "undated"
        sup_sorted = sorted(sup, key=lambda e: _ev_date(e))
        claim_timeline.append({
            "claim_id": cl.id, "claim_text": cl.claim_text, "claim_type": cl.claim_type,
            "supported": cl.supported, "sub_question": cl.sub_question,
            "first_evidence": {"evidence_id": sup_sorted[0].id, "quote": sup_sorted[0].quote[:400], "source_id": sup_sorted[0].source_id} if sup_sorted else None,
            "latest_evidence": {"evidence_id": sup_sorted[-1].id, "quote": sup_sorted[-1].quote[:400], "source_id": sup_sorted[-1].source_id} if sup_sorted else None,
            "supporting_count": len(sup_sorted),
        })
    # Conflict timeline: when disagreement appeared (earliest of each conflict's two sides)
    conflicts = report.conflicts if report and report.conflicts else []
    conflict_events = []
    for cf in conflicts[:20]:
        # Find source dates for both sides
        a_src = src_by_id.get(cf.get("source_a"))
        b_src = src_by_id.get(cf.get("source_b"))
        a_dt, _ = _parse_date(a_src.published_at if a_src else None)
        b_dt, _ = _parse_date(b_src.published_at if b_src else None)
        conflict_events.append({
            "topic": cf.get("topic"), "classification": cf.get("classification"),
            "position_a": cf.get("position_a", "")[:200], "source_a": cf.get("source_a"),
            "source_a_date": a_dt.isoformat() if a_dt else None,
            "position_b": cf.get("position_b", "")[:200], "source_b": cf.get("source_b"),
            "source_b_date": b_dt.isoformat() if b_dt else None,
            "possible_reason": cf.get("possible_reason"),
        })
    # Sort conflicts by earliest date where available
    conflict_events.sort(key=lambda x: x.get("source_a_date") or x.get("source_b_date") or "9999")
    return {
        "sources": src_events,
        "claim_timeline": claim_timeline,
        "conflict_timeline": conflict_events,
        "note": "Dates are from source metadata only; undated sources are shown as approximate access time and never invented.",
    }


@router.get("/{run_id}/report")
def get_report(run_id: str, db: Session = Depends(get_db)):
    run = _run_or_404(db, run_id)
    rep = db.query(Report).filter(Report.run_id == run_id).first()
    if rep is None:
        raise HTTPException(404, "Report not ready yet")
    return {"run_id": run_id, "question": rep.question, "executive_summary": rep.executive_summary,
            "research_method": rep.research_method, "findings": rep.findings, "conflicts": rep.conflicts,
            "uncertainties": rep.uncertainties, "limitations": rep.limitations,
            "conclusion": rep.conclusion, "confidence": rep.confidence,
            "citations": rep.citations, "mock_mode": rep.mock_mode,
            "mode": run.mode, "stop_reason": run.stop_reason,
            "stage_ms": run.stage_ms, "cost": _cost(run), "status": run.status}


@router.get("")
def list_runs(limit: int = 20, db: Session = Depends(get_db)):
    if limit > 100:
        limit = 100
    runs = db.query(ResearchRun).order_by(ResearchRun.started_at.desc()).limit(limit).all()
    out = []
    for r in runs:
        q = db.get(ResearchQuestion, r.question_id)
        rep = db.query(Report).filter(Report.run_id == r.id).first()
        out.append({"run_id": r.id, "question": q.question_text[:140] if q else "",
                    "status": r.status, "stage": r.stage, "started_at": r.started_at.isoformat(),
                    "num_sources": r.num_sources, "num_claims": r.num_claims,
                    "mock_mode": r.mock_mode, "mode": r.mode,
                    "confidence": (rep.confidence or {}).get("label") if rep and rep.confidence else None,
                    "stop_reason": r.stop_reason})
    return {"runs": out}
