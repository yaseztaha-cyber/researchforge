"""Runs the evaluation dataset against the local pipeline (mock providers) and prints metrics."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.agents.orchestrator import run_research
from app.db.session import SessionLocal, init_db
from app.models.db_models import Claim, Evidence, Report, ResearchRun, Source
from evaluation.scripts.metrics import (citation_completeness, citation_correctness, retrieval_precision,
                                        unsupported_claim_rate)


async def _one(db, question: str) -> dict:
    t0 = time.time()
    run_id = await run_research(question, db=db)
    lat = (time.time() - t0) * 1000
    run = db.get(ResearchRun, run_id)
    sources = [{"relevance_score": s.relevance_score} for s in db.query(Source).filter(Source.run_id == run_id)]
    evidence = db.query(Evidence).filter(Evidence.run_id == run_id).all()
    claims = [{"supported": c.supported} for c in db.query(Claim).filter(Claim.run_id == run_id)]
    rep = db.query(Report).filter(Report.run_id == run_id).first()
    ev_ids = {e.id for e in evidence}
    return {
        "question": question,
        "run_id": run_id,
        "status": run.status if run else "?",
        "stop_reason": run.stop_reason if run else None,
        "latency_ms": round(lat, 1),
        "num_sources": len(sources),
        "num_evidence": len(evidence),
        "num_claims": len(claims),
        "search_calls": run.search_calls if run else 0,
        "llm_calls": run.llm_calls if run else 0,
        "estimated_cost_usd": run.estimated_cost_usd if run else 0.0,
        "citation_correctness": citation_correctness({"citations": rep.citations}, ev_ids) if rep else 0.0,
        "citation_completeness": citation_completeness(rep.findings, rep.citations) if rep else 0.0,
        "unsupported_claim_rate": unsupported_claim_rate(claims),
        "retrieval_precision": retrieval_precision(sources),
    }


async def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="Write machine-readable JSON report here")
    ap.add_argument("--limit", type=int, default=0, help="Only run first N questions")
    ap.add_argument("--version", default="0.2.0")
    args = ap.parse_args()
    init_db()
    rows = [json.loads(l) for l in open("evaluation/dataset/questions.jsonl") if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    db = SessionLocal()
    results = []
    try:
        for r in rows:
            results.append(await _one(db, r["question"]))
    finally:
        db.close()
    keys = ("citation_correctness", "citation_completeness", "unsupported_claim_rate",
            "retrieval_precision", "latency_ms", "num_sources", "num_claims")
    agg = {k: round(sum(x[k] for x in results) / max(1, len(results)), 3) for k in keys}
    report = {"version": args.version, "n": len(results),
              "mock_mode": True, "runs": results, "aggregate": agg}
    out = json.dumps(report, indent=2)
    print(out)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(out)
        print(f"Wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
