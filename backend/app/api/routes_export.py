"""Export: Markdown / JSON (PDF via print stylesheet on the frontend)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.db_models import Claim, Evidence, Report, ResearchRun, Source

router = APIRouter(prefix="/api/research", tags=["export"])


def _report_md(run: ResearchRun, rep: Report, sources: list[Source]) -> str:
    lines = [f"# Research Report", "", f"**Question:** {rep.question}", "",
             f"_Status: {run.status} · Mock mode: {rep.mock_mode}_", "",
             "## Executive Summary", "", rep.executive_summary, "", "## Key Findings", ""]
    for i, f in enumerate(rep.findings or [], 1):
        cites = " ".join(f"[{c}]" for c in (f.get("citation_ids") or []))
        lines += [f"### {i}. {f.get('title', '')}", "", f"{f.get('text', '')} {cites}", ""]
    if rep.conflicts:
        lines += ["## Conflicting Evidence", ""]
        for c in rep.conflicts:
            lines += [f"- **{c.get('topic', '')}**: {c.get('position_a', '')[:200]} vs. "
                      f"{c.get('position_b', '')[:200]} (Possible reason: {c.get('possible_reason', '')})"]
        lines.append("")
    lines += ["## Uncertainties", ""]
    for u in rep.uncertainties or []:
        lines.append(f"- {u}")
    lines += ["", "## Conclusion", "", rep.conclusion, "", "## Sources", ""]
    for c in rep.citations or []:
        lines.append(f"[{c['index']}] {c['source_title']} — {c.get('url') or 'no URL'}")
    return "\n".join(lines)


@router.get("/{run_id}/export.md")
def export_md(run_id: str, db: Session = Depends(get_db)):
    run = db.get(ResearchRun, run_id)
    rep = db.query(Report).filter(Report.run_id == run_id).first()
    if run is None or rep is None:
        raise HTTPException(404, "Report not ready")
    sources = db.query(Source).filter(Source.run_id == run_id).all()
    return Response(_report_md(run, rep, sources), media_type="text/markdown")


@router.get("/{run_id}/export.json")
def export_json(run_id: str, db: Session = Depends(get_db)):
    run = db.get(ResearchRun, run_id)
    rep = db.query(Report).filter(Report.run_id == run_id).first()
    if run is None or rep is None:
        raise HTTPException(404, "Report not ready")
    sources = db.query(Source).filter(Source.run_id == run_id).all()
    evidence = db.query(Evidence).filter(Evidence.run_id == run_id).all()
    claims = db.query(Claim).filter(Claim.run_id == run_id).all()
    return {"question": rep.question, "plan": run.plan,
            "sources": [{"id": s.id, "title": s.title, "url": s.url, "source_type": s.source_type,
                         "relevance_score": s.relevance_score, "quality_score": s.quality_score} for s in sources],
            "evidence": [{"id": e.id, "claim": e.claim, "quote": e.quote, "source_id": e.source_id} for e in evidence],
            "claims": [{"id": c.id, "claim_text": c.claim_text, "supported": c.supported,
                        "confidence": c.confidence} for c in claims],
            "citations": rep.citations, "report": {"executive_summary": rep.executive_summary,
                                                  "findings": rep.findings, "conflicts": rep.conflicts,
                                                  "uncertainties": rep.uncertainties,
                                                  "conclusion": rep.conclusion},
            "confidence": rep.confidence,
            "metadata": {"run_id": run_id, "status": run.status, "mock_mode": run.mock_mode,
                         "duration_ms": run.duration_ms}}
