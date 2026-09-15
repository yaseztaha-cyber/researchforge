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
    sources = [{"relevance_score": s.relevance_score} for s in db.query(Source).filter(Source.run_id == run_id)]
    evidence = db.query(Evidence).filter(Evidence.run_id == run_id).all()
    claims = [{"supported": c.supported} for c in db.query(Claim).filter(Claim.run_id == run_id)]
    rep = db.query(Report).filter(Report.run_id == run_id).first()
    ev_ids = {e.id for e in evidence}
    return {
        "question": question,
        "latency_ms": round(lat, 1),
        "num_sources": len(sources),
        "num_evidence": len(evidence),
        "citation_correctness": citation_correctness({"citations": rep.citations}, ev_ids) if rep else 0.0,
        "citation_completeness": citation_completeness(rep.findings, rep.citations) if rep else 0.0,
        "unsupported_claim_rate": unsupported_claim_rate(claims),
        "retrieval_precision": retrieval_precision(sources),
    }


async def main() -> None:
    init_db()
    rows = [json.loads(l) for l in open("evaluation/dataset/questions.jsonl") if l.strip()]
    db = SessionLocal()
    results = []
    try:
        for r in rows:
            results.append(await _one(db, r["question"]))
    finally:
        db.close()
    agg = {k: round(sum(x[k] for x in results) / max(1, len(results)), 3)
           for k in ("citation_correctness", "citation_completeness",
                     "unsupported_claim_rate", "retrieval_precision")}
    print(json.dumps({"runs": results, "aggregate": agg}, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
