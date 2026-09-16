"""Retrieval Experiment Framework.

Controlled experiments for retrieval strategy comparison.
Each experiment produces machine-readable results for reproducibility.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.db_models import ResearchRun
from app.services.hybrid_retrieval import rerank_and_diversify, score_chunk
from app.services.vector_store import get_vector_store
from app.services.embeddings.factory import get_embedding_provider
from app.agents.orchestrator import run_research


@dataclass
class ExperimentConfig:
    """Configuration for a retrieval experiment."""
    name: str
    description: str
    # Retrieval strategy parameters
    use_vector: bool = True
    use_lexical: bool = True
    use_coverage: bool = True
    use_quality: bool = True
    mmr_lambda: float = 0.7
    per_doc_cap: int = 3
    # Weights (must sum to ~1.0 for meaningful comparison)
    semantic_weight: float = 0.45
    lexical_weight: float = 0.20
    coverage_weight: float = 0.15
    quality_weight: float = 0.20
    # Other params
    vector_top_k: int = 20
    final_top_k: int = 8
    min_similarity: float = 0.05
    # Query expansion
    expand_queries: bool = False
    synonym_expansion: bool = False
    # Metadata
    hypothesis: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class ExperimentResult:
    """Result of a single experiment run on a dataset."""
    experiment_id: str
    config: ExperimentConfig
    dataset: str
    started_at: str
    finished_at: str
    # Aggregate metrics
    precision: float
    recall_proxy: float
    source_diversity: float
    redundancy_rate: float
    evidence_relevance: float
    latency_ms: float
    # Per-category breakdown
    by_category: dict = field(default_factory=dict)
    # Per-run details (optional, can be large)
    runs: list[dict] = field(default_factory=list)


DEFAULT_EXPERIMENTS = [
    ExperimentConfig(
        name="vector_only",
        description="Pure vector similarity search",
        use_vector=True, use_lexical=False, use_coverage=False, use_quality=False,
        semantic_weight=1.0, lexical_weight=0.0, coverage_weight=0.0, quality_weight=0.0,
        hypothesis="Pure semantic similarity may miss keyword-specific relevance",
        tags=["baseline", "vector-only"]
    ),
    ExperimentConfig(
        name="lexical_only",
        description="Pure lexical/keyword search",
        use_vector=False, use_lexical=True, use_coverage=False, use_quality=False,
        semantic_weight=0.0, lexical_weight=1.0, coverage_weight=0.0, quality_weight=0.0,
        hypothesis="Lexical matching may help with specific terminology",
        tags=["baseline", "lexical-only"]
    ),
    ExperimentConfig(
        name="hybrid_baseline",
        description="Current default hybrid (0.45/0.20/0.15/0.20)",
        use_vector=True, use_lexical=True, use_coverage=True, use_quality=True,
        semantic_weight=0.45, lexical_weight=0.20, coverage_weight=0.15, quality_weight=0.20,
        hypothesis="Balanced hybrid is optimal default",
        tags=["baseline", "current-default"]
    ),
    ExperimentConfig(
        name="hybrid_no_quality",
        description="Hybrid without source quality component",
        use_vector=True, use_lexical=True, use_coverage=True, use_quality=False,
        semantic_weight=0.50, lexical_weight=0.25, coverage_weight=0.25, quality_weight=0.0,
        hypothesis="Quality weight may over-penalize relevant but lower-authority sources",
        tags=["ablation"]
    ),
    ExperimentConfig(
        name="hybrid_high_quality",
        description="Increased quality weight (0.20 -> 0.25)",
        use_vector=True, use_lexical=True, use_coverage=True, use_quality=True,
        semantic_weight=0.40, lexical_weight=0.20, coverage_weight=0.15, quality_weight=0.25,
        hypothesis="Higher quality weight may improve authority but reduce recall",
        tags=["weight-tuning"]
    ),
    ExperimentConfig(
        name="hybrid_high_lexical",
        description="Increased lexical weight (0.20 -> 0.30)",
        use_vector=True, use_lexical=True, use_coverage=True, use_quality=True,
        semantic_weight=0.35, lexical_weight=0.30, coverage_weight=0.15, quality_weight=0.20,
        hypothesis="Higher lexical weight may help technical/specific queries",
        tags=["weight-tuning"]
    ),
    ExperimentConfig(
        name="hybrid_high_coverage",
        description="Increased coverage weight (0.15 -> 0.25)",
        use_vector=True, use_lexical=True, use_coverage=True, use_quality=True,
        semantic_weight=0.35, lexical_weight=0.20, coverage_weight=0.25, quality_weight=0.20,
        hypothesis="Higher coverage may improve recall for broad queries",
        tags=["weight-tuning"]
    ),
    ExperimentConfig(
        name="hybrid_no_mmr",
        description="Hybrid without MMR diversity selection",
        use_vector=True, use_lexical=True, use_coverage=True, use_quality=True,
        semantic_weight=0.45, lexical_weight=0.20, coverage_weight=0.15, quality_weight=0.20,
        mmr_lambda=1.0,  # No diversity penalty
        hypothesis="MMR may over-suppress relevant results from same source",
        tags=["diversity"]
    ),
    ExperimentConfig(
        name="hybrid_strict_mmr",
        description="Stronger MMR diversity (lambda=0.5)",
        use_vector=True, use_lexical=True, use_coverage=True, use_quality=True,
        semantic_weight=0.45, lexical_weight=0.20, coverage_weight=0.15, quality_weight=0.20,
        mmr_lambda=0.5, per_doc_cap=2,
        hypothesis="Stronger diversity may improve source variety",
        tags=["diversity"]
    ),
    ExperimentConfig(
        name="hybrid_no_coverage",
        description="Hybrid without query coverage component",
        use_vector=True, use_lexical=True, use_coverage=False, use_quality=True,
        semantic_weight=0.50, lexical_weight=0.25, coverage_weight=0.0, quality_weight=0.25,
        hypothesis="Coverage may over-weight keyword matching vs semantic relevance",
        tags=["ablation"]
    ),
    ExperimentConfig(
        name="hybrid_synonym_expansion",
        description="Hybrid with query synonym expansion",
        use_vector=True, use_lexical=True, use_coverage=True, use_quality=True,
        semantic_weight=0.45, lexical_weight=0.20, coverage_weight=0.15, quality_weight=0.20,
        expand_queries=True, synonym_expansion=True,
        hypothesis="Synonym expansion may improve recall for technical terms",
        tags=["query-expansion"]
    ),
]


def run_single_experiment(
    config: ExperimentConfig,
    questions: list[dict],
    db: Session,
    base_settings: dict | None = None,
) -> ExperimentResult:
    """Run a single experiment configuration against a question set."""
    import time
    import asyncio

    exp_id = str(uuid.uuid4())[:8]
    started_at = datetime.now().isoformat()

    # Backup original settings
    original_settings = {}
    if base_settings is None:
        base_settings = {}
    s = get_settings()
    for key in ["HYBRID_SEMANTIC_WEIGHT", "HYBRID_LEXICAL_WEIGHT",
                "HYBRID_COVERAGE_WEIGHT", "HYBRID_QUALITY_WEIGHT",
                "VECTOR_TOP_K", "VECTOR_MIN_SIMILARITY"]:
        original_settings[key] = getattr(s, key)
        if hasattr(config, key.lower().replace("hybrid_", "").replace("vector_", "")):
            setattr(s, key, getattr(config, key.lower().replace("hybrid_", "").replace("vector_", "")))

    # Apply config weights to settings
    s.HYBRID_SEMANTIC_WEIGHT = config.semantic_weight
    s.HYBRID_LEXICAL_WEIGHT = config.lexical_weight
    s.HYBRID_COVERAGE_WEIGHT = config.coverage_weight
    s.HYBRID_QUALITY_WEIGHT = config.quality_weight
    s.VECTOR_TOP_K = config.vector_top_k
    s.VECTOR_MIN_SIMILARITY = config.min_similarity

    runs = []
    try:
        for q in questions:
            t0 = time.time()
            run_id = asyncio.run(run_research(
                q["question"], db=db, mode="web", depth="standard",
                max_sources=12, max_rounds=2, strictness="standard"
            ))
            lat = (time.time() - t0) * 1000
            from app.db.session import SessionLocal
            sdb = SessionLocal()
            try:
                run = sdb.get(ResearchRun, run_id)
                sources = sdb.query(RetrievalError).filter(RetrievalError.run_id == run_id).all()  # placeholder
                # Use existing metrics function
                from evaluation.scripts.run_evaluation import _one as eval_one
                # Reuse _one logic but we need to avoid re-running
                # For now, collect basic run data
                r = {"question_id": q.get("id"), "run_id": run_id, "latency_ms": round(lat, 1)}
                runs.append(r)
            finally:
                sdb.close()
    finally:
        # Restore settings
        for key, val in original_settings.items():
            setattr(s, key, val)

    # Compute aggregates (placeholder - real metrics need full evaluation run)
    agg = {
        "precision": 0.0, "recall_proxy": 0.0, "source_diversity": 0.0,
        "redundancy_rate": 0.0, "evidence_relevance": 0.0, "latency_ms": 0.0
    }

    finished_at = datetime.now().isoformat()
    return ExperimentResult(
        experiment_id=exp_id,
        config=config,
        dataset="questions_v03",
        started_at=started_at,
        finished_at=finished_at,
        **agg,
        by_category={},
        runs=runs,
    )


async def run_experiment_suite(
    configs: list[ExperimentConfig] | None = None,
    dataset_path: str = "evaluation/dataset/questions_v03.jsonl",
    limit: int = 0,
    out_dir: str = "evaluation/reports/experiments",
) -> list[ExperimentResult]:
    """Run a suite of experiments and save results."""
    import time
    import json

    configs = configs or DEFAULT_EXPERIMENTS
    questions = [json.loads(l) for l in open(dataset_path) if l.strip()]
    if limit:
        questions = questions[:limit]

    db = SessionLocal()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for config in configs:
        print(f"Running experiment: {config.name}")
        result = run_single_experiment(config, questions, db)
        results.append(result)
        # Save individual result
        (Path(out_dir) / f"{result.experiment_id}_{result.config.name}.json").write_text(
            json.dumps(result.__dict__, indent=2, default=str)
        )
        time.sleep(0.5)  # Brief pause between experiments

    # Save summary
    summary = {
        "suite": "retrieval_experiments",
        "timestamp": datetime.now().isoformat(),
        "dataset": dataset_path,
        "experiments": [r.__dict__ for r in results],
    }
    (Path(out_dir) / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"Saved {len(results)} experiments to {out_dir}")
    return results


if __name__ == "__main__":
    import asyncio
    from app.db.session import SessionLocal, init_db
    init_db()
    asyncio.run(run_experiment_suite())