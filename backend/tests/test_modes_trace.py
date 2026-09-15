"""v0.2 integration: modes, stop_reason, cost/latency trace, queries audit, hybrid."""

from app.agents.orchestrator import run_research
from app.models.db_models import Claim, Evidence, Report, ResearchQuery, ResearchRun, Source


async def test_hybrid_mode_merges_uploads(db):
    from app.models.db_models import Document, SourceChunk
    from app.services.embeddings.factory import get_embedding_provider
    emb = get_embedding_provider()
    doc = Document(filename="paper.pdf", content_hash="abc123", num_chunks=1)
    db.add(doc)
    db.flush()
    db.add(SourceChunk(source_id=doc.id, run_id=doc.id, chunk_index=0, page=14,
                       section="Methods", text="Desalination brine discharge increases local salinity near outfalls.",
                       embedding=emb.embed("Desalination brine discharge increases local salinity near outfalls.")))
    db.commit()
    run_id = await run_research("How does brine discharge affect marine life?",
                                db=db, mode="hybrid", document_ids=[doc.id])
    run = db.get(ResearchRun, run_id)
    assert run.mode == "hybrid"
    assert run.stop_reason
    assert run.stage_ms and "planning" in run.stage_ms
    origins = {s.origin for s in db.query(Source).filter(Source.run_id == run_id)}
    assert "uploaded" in origins and "web" in origins


async def test_private_mode_uses_only_uploads(db):
    from app.models.db_models import Document, SourceChunk
    from app.services.embeddings.factory import get_embedding_provider
    emb = get_embedding_provider()
    doc = Document(filename="notes.md", content_hash="def456", num_chunks=1)
    db.add(doc)
    db.flush()
    db.add(SourceChunk(source_id=doc.id, run_id=doc.id, chunk_index=0,
                       text="Reverse osmosis needs substantial energy input per cubic meter.",
                       embedding=emb.embed("Reverse osmosis needs substantial energy input per cubic meter.")))
    db.commit()
    run_id = await run_research("What needs energy in desalination?", db=db,
                                mode="private", document_ids=[doc.id])
    sources = db.query(Source).filter(Source.run_id == run_id).all()
    assert sources and all(s.origin == "uploaded" for s in sources)


async def test_queries_audited_and_claims_linked(db):
    run_id = await run_research("What are the energy requirements of desalination?", db=db)
    queries = db.query(ResearchQuery).filter(ResearchQuery.run_id == run_id).all()
    assert queries
    assert {q.query_type for q in queries}  # typed
    claims = db.query(Claim).filter(Claim.run_id == run_id).all()
    assert claims and all(c.agreement for c in claims)
    rep = db.query(Report).filter(Report.run_id == run_id).first()
    assert rep.research_method and "Stop reason" in rep.research_method


async def test_trace_and_graph_endpoints(db):
    from fastapi.testclient import TestClient
    from app.db.session import get_db as _get_db
    from app.main import create_app
    run_id = await run_research("What are the environmental impacts of desalination?", db=db)
    app = create_app()
    app.dependency_overrides[_get_db] = lambda: db
    client = TestClient(app)
    claims = client.get(f"/api/research/{run_id}/claims").json()["claims"]
    assert claims
    trace = client.get(f"/api/research/{run_id}/claims/{claims[0]['id']}/trace").json()
    assert trace["claim"] and trace["verification"]
    graph = client.get(f"/api/research/{run_id}/graph").json()
    types = {n["type"] for n in graph["nodes"]}
    assert {"question", "claim", "evidence", "source"} <= types
    assert graph["edges"]
    # rate limit still allows normal use; invalid mode combo rejected
    bad = client.post("/api/research", json={"question": "Is this ok for testing?", "mode": "private"})
    assert bad.status_code == 400
