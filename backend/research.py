"""CLI vertical slice: python research.py "What are the environmental impacts of desalination?\""""

from __future__ import annotations

import asyncio
import sys

sys.path.insert(0, ".")

from app.agents.orchestrator import run_research  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.models.db_models import Evidence, Report, ResearchRun, Source  # noqa: E402


def _ascii(s: str) -> str:
    return s.replace("\u201c", '"').replace("\u201d", '"').replace("\u2014", "-").replace("\u2013", "-")


async def _run(question: str, depth: str = "standard") -> None:
    init_db()
    db = SessionLocal()
    try:
        run_id = await run_research(question, depth=depth, db=db)
        run = db.get(ResearchRun, run_id)
        rep = db.query(Report).filter(Report.run_id == run_id).first()
        n_sources = db.query(Source).filter(Source.run_id == run_id).count()
        n_rel = db.query(Source).filter(Source.run_id == run_id, Source.relevance_score > 0.1).count()
        n_claims = db.query(Evidence).filter(Evidence.run_id == run_id).count()
        print("Research completed.\n")
        print(f"Sources discovered: {n_sources}")
        print(f"Relevant sources: {n_rel}")
        print(f"Claims extracted: {n_claims}")
        if run is not None and run.mock_mode:
            print("(mock/dev mode: fixture sources — configure SEARCH_API_KEY for live research)")
        print("\n-----------------------------")
        print(f"Research Question\n{question}\n")
        if rep is None:
            print("No report produced.")
            return
        print(f"Executive Summary\n{_ascii(rep.executive_summary)}\n")
        print("Key Findings")
        for i, f in enumerate(rep.findings or [], 1):
            print(f"\n{i}. {_ascii(f.get('title', ''))}\n   {_ascii(f.get('text', ''))[:400]}")
        if rep.conflicts:
            print("\nConflicting Evidence")
            for c in rep.conflicts:
                print(f"- {_ascii(str(c.get('topic')))}: {_ascii(str(c.get('position_a')))[:150]} ... VS ... {_ascii(str(c.get('position_b')))[:150]}")
        print("\nUncertainties")
        for u in rep.uncertainties or []:
            print(f"- {_ascii(u)}")
        print(f"\nConclusion\n{_ascii(rep.conclusion)}\n")
        print("Sources")
        for c in rep.citations or []:
            print(f"[{c['index']}] {_ascii(c['source_title'])} — {c.get('url')}")
    finally:
        db.close()


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]).strip() or "What are the environmental impacts of desalination?"
    depth = "standard"
    asyncio.run(_run(q, depth))
