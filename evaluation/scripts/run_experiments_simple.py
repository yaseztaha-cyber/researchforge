"""Lightweight experiment runner for v0.5: 3 configs on 5 questions, cross-domain.

Configs:
- vector_only (semantic 1.0)
- hybrid_baseline (0.45/0.20/0.15/0.20)
- high_lexical (0.35/0.30/0.15/0.20)

Stores under evaluation/reports/experiments/ with hypothesis/decision.
"""
import json, time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.config import get_settings

configs = [
    {"name": "vector_only", "hypothesis": "Pure semantic may miss keyword-specific relevance", "weights": {"HYBRID_SEMANTIC_WEIGHT":1.0,"HYBRID_LEXICAL_WEIGHT":0.0,"HYBRID_COVERAGE_WEIGHT":0.0,"HYBRID_QUALITY_WEIGHT":0.0}},
    {"name": "hybrid_baseline", "hypothesis": "Balanced hybrid is optimal default", "weights": {"HYBRID_SEMANTIC_WEIGHT":0.45,"HYBRID_LEXICAL_WEIGHT":0.20,"HYBRID_COVERAGE_WEIGHT":0.15,"HYBRID_QUALITY_WEIGHT":0.20}},
    {"name": "high_lexical", "hypothesis": "Higher lexical weight may help technical queries", "weights": {"HYBRID_SEMANTIC_WEIGHT":0.35,"HYBRID_LEXICAL_WEIGHT":0.30,"HYBRID_COVERAGE_WEIGHT":0.15,"HYBRID_QUALITY_WEIGHT":0.20}},
]

def run_one(name, weights, limit=5):
    s = get_settings()
    orig = {k: getattr(s,k) for k in weights}
    for k,v in weights.items():
        setattr(s,k,v)
    try:
        from evaluation.scripts.run_evaluation import _one as eval_one  # not used
        # Instead run full evaluation via subprocess-like direct call
        from app.db.session import SessionLocal, init_db
        from evaluation.scripts.metrics import retrieval_precision, retrieval_recall
        import asyncio, json as _j
        from app.agents.orchestrator import run_research
        from app.models.db_models import Source
        init_db()
        db = SessionLocal()
        dpath = Path(__file__).resolve().parents[2] / "evaluation" / "dataset" / "questions_v03.jsonl"
        questions = [ _j.loads(l) for l in open(dpath) if l.strip()][:limit]
        results=[]
        for q in questions:
            import time as _t
            t0=_t.time()
            run_id = asyncio.run(run_research(q["question"], db=db))
            lat=(_t.time()-t0)*1000
            srcs=[{"relevance_score":r.relevance_score,"domain":r.domain} for r in db.query(Source).filter(Source.run_id==run_id).all()]
            prec = retrieval_precision(srcs)
            rec = retrieval_recall(srcs, 2)
            results.append({"question":q["question"][:40], "precision":prec, "recall":rec, "latency":round(lat,1)})
        agg_prec = round(sum(r["precision"] for r in results)/len(results),3) if results else 0
        agg_rec = round(sum(r["recall"] for r in results)/len(results),3) if results else 0
        db.close()
        return {"precision":agg_prec, "recall":agg_rec, "runs":results}
    finally:
        for k,v in orig.items():
            setattr(s,k,v)

if __name__=="__main__":
    out_dir = Path(__file__).resolve().parents[2] / "evaluation" / "reports" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    summary=[]
    for cfg in configs:
        print(f"Running {cfg['name']}...")
        res = run_one(cfg["name"], cfg["weights"])
        exp = {"experiment_id": cfg["name"]+"-v05", "name": cfg["name"], "hypothesis": cfg["hypothesis"], "config": cfg["weights"], "dataset": "questions_v03.jsonl (limit 5)", "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "precision": res["precision"], "recall_proxy": res["recall"], "runs": res["runs"], "decision": "pending cross-domain analysis"}
        (out_dir / f"{exp['experiment_id']}.json").write_text(json.dumps(exp, indent=2))
        summary.append(exp)
        print(json.dumps(exp, indent=2))
    # Simple regression guard: precision may not regress >0.05 vs baseline
    baseline = next((x for x in summary if x["name"]=="hybrid_baseline"), None)
    for exp in summary:
        guard = "PASS" if baseline is None or exp["precision"] >= baseline["precision"]-0.05 else "REGRESSION"
        exp["regression_guard"] = guard
    Path(out_dir / "summary.json").write_text(json.dumps({"suite":"v0.5 lightweight","timestamp":time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),"experiments":summary}, indent=2))
    print(f"Wrote {out_dir}/summary.json")
