"""Source detail + evaluation dashboard APIs."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.db_models import Claim, Evidence, Report, ResearchRun, Source

sources_router = APIRouter(tags=["sources"])
eval_router = APIRouter(prefix="/api/eval", tags=["evaluation"])


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
