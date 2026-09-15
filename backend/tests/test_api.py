"""Integration: full pipeline question -> report -> citation verification (mock providers)."""

from app.agents.orchestrator import run_research
from app.models.db_models import Claim, Evidence, Report, ResearchRun, Source


async def test_end_to_end_mock_pipeline(db):
    run_id = await run_research("What are the environmental impacts of desalination?", db=db)
    run = db.get(ResearchRun, run_id)
    assert run is not None and run.status in ("completed", "partial")
    sources = db.query(Source).filter(Source.run_id == run_id).all()
    evidence = db.query(Evidence).filter(Evidence.run_id == run_id).all()
    claims = db.query(Claim).filter(Claim.run_id == run_id).all()
    rep = db.query(Report).filter(Report.run_id == run_id).first()
    assert sources and evidence and rep is not None
    # Every citation must resolve to real evidence + source (no fabricated citations).
    ev_ids = {e.id for e in evidence}
    src_ids = {s.id for s in sources}
    for c in rep.citations:
        assert c["evidence_id"] in ev_ids
        assert c["source_id"] in src_ids
    # Every quote must be a substring of its source content.
    by_source = {s.id: (s.content or "") for s in sources}
    for e in evidence:
        assert e.quote in by_source[e.source_id]
    assert run.mock_mode is True


async def test_api_endpoints(db):
    from fastapi.testclient import TestClient
    from app.db.session import get_db as _get_db
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[_get_db] = lambda: db
    client = TestClient(app)
    assert client.get("/api/health").status_code == 200
    r = client.post("/api/research", json={"question": "What causes ocean salinity?", "depth": "standard"})
    assert r.status_code == 202
