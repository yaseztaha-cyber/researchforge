"""Research orchestrator: the full pipeline with progress, stopping criteria, persistence.

Question -> plan -> search -> rank/filter -> chunk -> evidence -> claims ->
conflicts -> synthesis -> verification -> confidence -> report.
"""

from __future__ import annotations

import datetime as dt
import time
import uuid

from sqlalchemy.orm import Session

from app.agents import conflict_detector, extractor, planner, synthesizer, verifier
from app.agents.researcher import run_retrieval
from app.core.config import get_settings
from app.core.logging import log_event
from app.models.db_models import Claim, Evidence, Report, ResearchQuestion, ResearchRun, Source, SourceChunk
from app.schemas.research import EvidenceItem
from app.services.confidence import compute_confidence
from app.services.embeddings.factory import get_embedding_provider
from app.services.llm.factory import get_llm_provider, is_mock_llm
from app.services.retrieval.factory import is_mock_search

STAGES = ["planning", "searching", "filtering", "extracting", "analyzing",
          "synthesizing", "verifying", "done"]

# In-memory progress for polling (backed by DB row as source of truth on restart).
PROGRESS: dict[str, dict] = {}


def _emit(run_id: str, stage: str, progress: float, detail: str = "") -> None:
    PROGRESS[run_id] = {"run_id": run_id, "stage": stage, "progress": progress, "detail": detail}
    log_event("progress", run_id=run_id, stage=stage, status="info", progress=progress, detail=detail)


def _guess_section(content: str) -> str | None:
    low = content.lower()
    for key in ("energy", "brine", "marine", "mitigat", "method", "result", "conclusion"):
        if key in low[:2000]:
            return key.capitalize()
    return None


async def run_research(question_text: str, *, depth: str = "standard",
                       max_sources: int | None = None, db: Session,
                       run_id: str | None = None) -> str:
    settings = get_settings()
    t0 = time.time()
    run_id = run_id or str(uuid.uuid4())
    mock_mode = is_mock_llm() or is_mock_search() or settings.MOCK_MODE

    question = ResearchQuestion(question_text=question_text, depth=depth)
    db.add(question)
    db.flush()
    run = ResearchRun(id=run_id, question_id=question.id, status="running",
                      stage="planning", progress=0.02, mock_mode=mock_mode)
    db.add(run)
    db.commit()
    _emit(run_id, "planning", 0.05, "Analyzing research question")
    log_event("run_started", run_id=run_id, stage="planning", status="running",
              depth=depth, mock_mode=mock_mode)

    try:
        # 1. Plan
        llm = get_llm_provider()
        plan = await planner.plan_research(question_text, llm)
        run.plan = plan.model_dump()
        run.stage = "searching"
        db.commit()
        _emit(run_id, "searching", 0.15, f"Plan ready: {len(plan.sub_questions)} sub-questions")

        # 2. Retrieve (+ agentic follow-up round on gaps)
        queries = plan.search_queries
        if depth == "deep":
            queries = queries + [f"{sq} site:.gov OR site:.edu" for sq in plan.sub_questions[:2]]
        sources, retrieval_meta = await run_retrieval(queries, max_sources=max_sources,
                                                      max_relevant=settings.MAX_RELEVANT_SOURCES)
        _emit(run_id, "filtering", 0.35, f"Discovered {len(sources)} sources")
        log_event("retrieval_done", run_id=run_id, stage="searching", status="ok",
                  num_sources=len(sources), meta=retrieval_meta)

        # Follow-up round if evidence looks thin (agentic iteration, bounded).
        if len(sources) < 3 and settings.MAX_SEARCH_ROUNDS >= 2:
            extra_q = [f"{question_text} review evidence", f"{question_text} impacts study"]
            more, _ = await run_retrieval(extra_q, max_sources=max_sources)
            have = {s.content_hash for s in sources}
            for m in more:
                if m.content_hash not in have:
                    sources.append(m)
            log_event("followup_round", run_id=run_id, stage="searching", status="ok",
                      added=len(sources))

        # 3. Persist sources + chunks + embeddings
        embedder = get_embedding_provider()
        db_sources: list[Source] = []
        for rs in sources[: (max_sources or settings.MAX_SOURCES)]:
            srow = Source(run_id=run_id, title=rs.title, url=rs.url, author=rs.author,
                          publisher=rs.publisher, published_at=rs.published_at,
                          source_type=rs.source_type, domain=rs.domain,
                          description=rs.description, content=rs.content,
                          content_hash=rs.content_hash, relevance_score=rs.relevance,
                          quality_score=rs.quality, score_breakdown=rs.breakdown)
            db.add(srow)
            db.flush()
            # naive paragraph chunking with section heuristic
            paras = [p.strip() for p in (rs.content or "").split("\n\n") if len(p.strip()) > 60][:6]
            for idx, para in enumerate(paras or [rs.description or rs.title]):
                db.add(SourceChunk(source_id=srow.id, run_id=run_id, chunk_index=idx,
                                   section=_guess_section(para), text=para[:3000],
                                   embedding=embedder.embed(para[:2000])))
            db_sources.append(srow)
        db.commit()
        run.num_sources = len(db_sources)
        run.stage = "extracting"
        db.commit()
        _emit(run_id, "extracting", 0.55, f"Extracting evidence from {len(db_sources)} sources")

        # 4. Evidence extraction (extractive)
        evidence_rows: list[Evidence] = []
        evidence_items: list[EvidenceItem] = []
        for srow in db_sources:
            items = extractor.extract_evidence(question_text, srow.id, srow.content or srow.description or "",
                                               section=_guess_section(srow.content or ""))
            for it in items:
                erow = Evidence(run_id=run_id, source_id=srow.id, claim=it.claim, quote=it.quote,
                                page=it.page, section=it.section or _guess_section(it.quote),
                                relevance_score=it.relevance_score, confidence_score=it.confidence_score)
                db.add(erow)
                db.flush()
                # rebind item source to row id already; keep mapping for synthesis
                evidence_items.append(it)
                evidence_rows.append(erow)
        db.commit()
        _emit(run_id, "analyzing", 0.68, f"Extracted {len(evidence_rows)} evidence passages")
        log_event("extraction_done", run_id=run_id, stage="extracting", status="ok",
                  num_evidence=len(evidence_rows))

        # 5. Claims (one per evidence cluster lead + finding-level), then conflicts
        claims: list[Claim] = []
        for erow in evidence_rows[:12]:
            v = verifier.verify_claim(erow.claim, [EvidenceItem(
                claim=erow.claim, quote=erow.quote, source_id=erow.source_id,
                page=erow.page, section=erow.section,
                relevance_score=erow.relevance_score, confidence_score=erow.confidence_score)])
            ctype = "statistical" if any(ch.isdigit() for ch in erow.claim) else "factual"
            if any(w in erow.claim.lower() for w in ("cause", "leads to", "increases", "reduces")):
                ctype = "causal"
            claims.append(Claim(run_id=run_id, claim_text=erow.claim[:800], claim_type=ctype,
                                confidence=v.confidence, supported=v.supported,
                                supporting_evidence_ids=[erow.id] if v.supported else [],
                                contradicting_evidence_ids=[],
                                confidence_breakdown={"verifier_confidence": v.confidence,
                                                      "issues": v.issues}))
        for c in claims:
            db.add(c)
        db.commit()

        conflicts = conflict_detector.detect_conflicts(evidence_items)
        _emit(run_id, "synthesizing", 0.8, "Cross-checking claims and writing report")

        # 6. Synthesis from evidence
        titles = {s.id: s.title for s in db_sources}
        synth = synthesizer.synthesize(question_text, evidence_items,
                                       {e.source_id: e for e in evidence_items}, titles)
        # Map finding evidence refs to DB ids + numbered citations
        citations: list[dict] = []
        for i, erow in enumerate(evidence_rows, start=1):
            s = next((x for x in db_sources if x.id == erow.source_id), None)
            citations.append({"index": i, "evidence_id": erow.id, "source_id": erow.source_id,
                              "source_title": s.title if s else "Unknown",
                              "url": s.url if s else None, "page": erow.page,
                              "section": erow.section, "quote": erow.quote[:500]})
        ev_by_source: dict[str, list[Evidence]] = {}
        for erow in evidence_rows:
            ev_by_source.setdefault(erow.source_id, []).append(erow)
        findings = []
        for f in synth["findings"]:
            findings.append({"title": f["title"], "text": f["text"],
                             "citation_ids": [c["index"] for c in citations
                                              if any(c["evidence_id"] == e.id for e in evidence_rows)][:3]})

        avg_q = sum(s.quality_score for s in db_sources) / max(1, len(db_sources))
        supported = sum(1 for c in claims if c.supported)
        confidence = compute_confidence(evidence=evidence_items,
                                        num_subquestions=len(plan.sub_questions),
                                        avg_quality=avg_q, conflicts=conflicts,
                                        claims_supported=supported,
                                        claims_total=max(1, len(claims)))

        # 7. Verification pass: drop findings with zero citations -> uncertainties
        _emit(run_id, "verifying", 0.92, "Verifying citations")
        verified_findings = []
        extra_uncertainties = list(synth["uncertainties"])
        for f in findings:
            if f["citation_ids"]:
                verified_findings.append(f)
            else:
                extra_uncertainties.append(f"Insufficient evidence for: {f['title']}")

        report = Report(run_id=run_id, question=question_text,
                        executive_summary=synth["executive_summary"],
                        findings=verified_findings,
                        conflicts=[c.model_dump() for c in conflicts],
                        uncertainties=extra_uncertainties,
                        limitations=synth["limitations"], conclusion=synth["conclusion"],
                        confidence=confidence.model_dump(), citations=citations,
                        mock_mode=mock_mode)
        db.add(report)
        run.stage = "done"
        run.status = "completed" if evidence_rows else "partial"
        run.progress = 1.0
        run.num_claims = len(claims)
        run.finished_at = dt.datetime.now(dt.timezone.utc)
        run.duration_ms = int((time.time() - t0) * 1000)
        if not evidence_rows:
            run.error = "No relevant evidence retrieved."
        db.commit()
        _emit(run_id, "done", 1.0, f"Completed with {len(evidence_rows)} evidence items")
        log_event("run_finished", run_id=run_id, stage="done", status=run.status,
                  num_sources=len(db_sources), num_claims=len(claims),
                  duration_ms=run.duration_ms)
        return run_id
    except Exception as e:  # graceful failure, never a silent hang
        db.rollback()
        run = db.get(ResearchRun, run_id)
        if run is not None:
            run.status = "failed"
            run.stage = "failed"
            run.error = f"{type(e).__name__}: {e}"[:2000]
            run.finished_at = dt.datetime.now(dt.timezone.utc)
            run.duration_ms = int((time.time() - t0) * 1000)
            db.commit()
        log_event("run_failed", run_id=run_id, stage="failed", status="error", error=str(e)[:500])
        _emit(run_id, "failed", 1.0, str(e)[:300])
        raise
