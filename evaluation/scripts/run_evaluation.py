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
from evaluation.scripts.metrics import (citation_completeness, citation_correctness, evidence_relevance,
                                         overstatement_rate, retrieval_precision, retrieval_recall,
                                         source_diversity, unsupported_claim_rate)


async def _one(db, entry: dict) -> dict:
    question = entry["question"]
    expected_min = entry.get("min_sources") or entry.get("evaluation_notes") and 2 or 2
    # v03 schema uses min_sources or relevant_source_types; fallback to 2
    if "min_sources" not in entry:
        expected_min = 2
    else:
        expected_min = entry["min_sources"]
    t0 = time.time()
    run_id = await run_research(question, db=db)
    lat = (time.time() - t0) * 1000
    run = db.get(ResearchRun, run_id)
    raw_sources = db.query(Source).filter(Source.run_id == run_id).all()
    sources = [{"relevance_score": s.relevance_score, "domain": s.domain, "publisher": s.publisher} for s in raw_sources]
    evidence_rows = db.query(Evidence).filter(Evidence.run_id == run_id).all()
    evidence = [{"relevance_score": e.relevance_score, "quote": e.quote, "id": e.id, "source_id": e.source_id} for e in evidence_rows]
    sources_full = [{"id": s.id, "domain": s.domain, "publisher": s.publisher, "relevance_score": s.relevance_score,
                     "content": s.content, "description": s.description} for s in raw_sources]
    claims_rows = db.query(Claim).filter(Claim.run_id == run_id).all()
    claims = [{"supported": c.supported, "confidence_breakdown": c.confidence_breakdown,
               "supporting_evidence_ids": c.supporting_evidence_ids} for c in claims_rows]
    rep = db.query(Report).filter(Report.run_id == run_id).first()
    ev_ids = {e["id"] for e in evidence}
    div = source_diversity(sources)
    return {
        "id": entry.get("id"),
        "category": entry.get("category") or entry.get("domain"),
        "question": question,
        "run_id": run_id,
        "status": run.status if run else "?",
        "stop_reason": run.stop_reason if run else None,
        "latency_ms": round(lat, 1),
        "stage_ms": run.stage_ms if run else None,
        "num_sources": len(sources),
        "num_evidence": len(evidence),
        "num_claims": len(claims),
        "search_calls": run.search_calls if run else 0,
        "llm_calls": run.llm_calls if run else 0,
        "estimated_cost_usd": run.estimated_cost_usd if run else 0.0,
        "citation_correctness": citation_correctness({"citations": rep.citations}, ev_ids) if rep else 0.0,
        "citation_completeness": citation_completeness(rep.findings, rep.citations) if rep else 0.0,
        "unsupported_claim_rate": unsupported_claim_rate(claims),
        "overstatement_rate": overstatement_rate(claims),
        "retrieval_precision": retrieval_precision(sources),
        "retrieval_recall_proxy": retrieval_recall(sources, expected_min),
        "source_diversity": div,
        "evidence_relevance": evidence_relevance(evidence),
    }


async def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="evaluation/dataset/questions_v03.jsonl", help="Dataset path")
    ap.add_argument("--out", default=None, help="Write machine-readable JSON report here")
    ap.add_argument("--limit", type=int, default=0, help="Only run first N questions")
    ap.add_argument("--version", default="0.3.0")
    args = ap.parse_args()
    init_db()
    # Fallback to legacy dataset if v03 not found
    dataset = args.dataset if Path(args.dataset).exists() else "evaluation/dataset/questions.jsonl"
    rows = [json.loads(l) for l in open(dataset) if l.strip()]
    if args.limit:
        rows = rows[: args.limit]
    db = SessionLocal()
    results = []
    try:
        for r in rows:
            results.append(await _one(db, r))
    finally:
        db.close()
    keys = ("citation_correctness", "citation_completeness", "unsupported_claim_rate", "overstatement_rate",
            "retrieval_precision", "retrieval_recall_proxy", "evidence_relevance", "latency_ms", "num_sources", "num_claims")
    agg = {k: round(sum(x[k] for x in results) / max(1, len(results)), 3) for k in keys}
    # Also aggregate diversity
    avg_domains = round(sum(r["source_diversity"]["source_domains"] for r in results) / max(1, len(results)), 2)
    report = {"version": args.version, "dataset": dataset, "n": len(results),
              "mock_mode": True, "runs": results, "aggregate": {**agg, "avg_source_domains": avg_domains}}
    out = json.dumps(report, indent=2)
    print(out)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(out)
        print(f"Wrote {args.out}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
