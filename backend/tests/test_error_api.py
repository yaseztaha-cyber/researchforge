"""Tests for retrieval error API — direct DB + API function level."""

import pytest
from app.models.db_models import RetrievalError, ResearchQuestion, ResearchRun
from app.api.routes_misc import CreateErrorRequest

def test_create_and_list_errors_direct(db):
    q = ResearchQuestion(question_text="Test question for error API?")
    db.add(q)
    db.flush()
    run = ResearchRun(id="test-run-123", question_id=q.id, status="completed")
    db.add(run)
    db.commit()

    # Directly create via model (simulates API)
    from app.api.routes_misc import list_errors, error_summary
    # Use CreateErrorRequest to validate
    req = CreateErrorRequest(run_id=run.id, question_id=q.id, query="test query", error_type="wrong_domain", severity="medium", notes="test note")
    assert req.error_type == "wrong_domain"
    # Insert via ORM
    e = RetrievalError(run_id=req.run_id, question_id=req.question_id, query=req.query, error_type=req.error_type, severity=req.severity, notes=req.notes)
    db.add(e)
    db.commit()
    assert e.id

    # List via function (explicit limit/offset to avoid Query default)
    res = list_errors(run_id=run.id, limit=50, offset=0, db=db)
    assert res["total"] >= 1
    found = any(x["id"] == e.id for x in res["errors"])
    assert found

    # Summary
    summ = error_summary(run_id=run.id, db=db)
    assert summ["total"] >= 1
    assert "wrong_domain" in summ["by_type"]

def test_invalid_error_type_validation():
    with pytest.raises(Exception):
        CreateErrorRequest(run_id="a", question_id="b", query="q", error_type="invalid_type")

def test_error_type_set():
    valid = {"wrong_domain", "wrong_source", "right_source_wrong_chunk", "right_chunk_wrong_rank",
             "missing_source", "duplicate_source", "query_decomposition_failure",
             "evidence_extraction_failure", "source_metadata_failure", "conflict_misclassification"}
    for t in valid:
        r = CreateErrorRequest(run_id="r", question_id="q", query="qq", error_type=t)
        assert r.error_type == t
