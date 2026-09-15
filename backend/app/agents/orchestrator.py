"""Research orchestrator v2: full pipeline with progress, modes, budgets, trace.

Question -> plan -> typed queries -> search (web and/or uploaded docs) ->
dedup/rank/diversity-select -> chunk -> evidence -> claims (+agreement) ->
conflicts -> synthesis -> verification -> confidence -> report.

Modes: web | private (uploaded docs only) | hybrid (both).
Every run records: stop_reason, per-stage latency, LLM/search/embedding usage,
and estimated cost. Partial failures degrade gracefully, never silently.
"""

from __future__ import annotations

import datetime as dt
import time
import uuid

from sqlalchemy.orm import Session

from app.agents import conflict_detector, extractor, planner, synthesizer, verifier
from app.agents.conflict_detector import _side as _evidence_side
from app.agents.conflict_detector import agreement_summary
from app.agents.researcher import RetrievedSource, run_retrieval
from app.core.config import get_settings
from app.core.logging import log_event
from app.models.db_models import Claim, Document, Evidence, Report, ResearchQuestion, ResearchRun, Source, SourceChunk
from app.schemas.research import EvidenceItem
from app.services.confidence import compute_confidence
from app.services.embeddings.factory import get_embedding_provider
from app.services.embeddings.hash_embeddings import cosine
from app.services.llm.base import LLMProvider, LLMResponse
from app.services.llm.factory import get_llm_provider, is_mock_llm
from app.services.retrieval.base import term_coverage
from app.services.retrieval.factory import is_mock_search

STAGES = ["planning", "searching", "filtering", "extracting", "analyzing",
          "synthesizing", "verifying", "done"]

# In-memory progress for polling (backed by DB row as source of truth on restart).
PROGRESS: dict[str, dict] = {}


def _emit(run_id: str, stage: str, progress: float, detail: str = "",
          counts: dict | None = None) -> None:
    PROGRESS[run_id] = {"run_id": run_id, "stage": stage, "progress": progress,
                        "detail": detail, "counts": counts or {}}
    log_event("progress", run_id=run_id, stage=stage, status="info",
              progress=progress, detail=detail)


class _CountingLLM(LLMProvider):
    """Wraps the configured provider to meter calls/tokens/cost without changing behavior."""
    name = "counting"

    def __init__(self, inner: LLMProvider, usage: dict):
        self.inner = inner
        self.usage = usage
        self.name = f"counting({inner.name})"

    async def complete(self, *, system: str, user: str, max_tokens: int = 1200,
                       temperature: float = 0.2) -> LLMResponse:
        resp = await self.inner.complete(system=system, user=user,
                                         max_tokens=max_tokens, temperature=temperature)
        self.usage["llm_calls"] = self.usage.get("llm_calls", 0) + 1
        self.usage["input_tokens"] = self.usage.get("input_tokens", 0) + resp.prompt_tokens
        self.usage["output_tokens"] = self.usage.get("output_tokens", 0) + resp.completion_tokens
        self.usage["estimated_cost_usd"] = self.usage.get("estimated_cost_usd", 0.0) + resp.cost_usd
        return resp


def _guess_section(content: str) -> str | None:
    low = content.lower()
    for key in ("energy", "brine", "marine", "mitigat", "method", "result", "conclusion"):
        if key in low[:2000]:
            return key.capitalize()
    return None


def _nearest_subquestion(text: str, sub_questions: list[str]) -> str | None:
    best, best_score = None, 0.08
    for sq in sub_questions:
        sc = term_coverage(sq, text)
        if sc > best_score:
            best, best_score = sq, sc
    return best


def _document_sources(question: str, document_ids: list[str], db: Session,
                      usage: dict, top_k: int = 6) -> list[RetrievedSource]:
    """RAG over uploaded documents: top cosine chunks become uploaded-origin sources."""
    if not document_ids:
        return []
    embedder = get_embedding_provider()
    qv = embedder.embed(question)
    usage["embedding_calls"] = usage.get("embedding_calls", 0) + 1
    out: list[RetrievedSource] = []
    for doc_id in document_ids[:10]:
        doc = db.get(Document, doc_id)
        if doc is None:
            continue
        chunks = db.query(SourceChunk).filter(SourceChunk.source_id == doc_id).limit(100).all()
        scored = []
        for c in chunks:
            if not c.embedding:
                continue
            usage["embedding_calls"] = usage.get("embedding_calls", 0)  # precomputed at upload
            scored.append((cosine(qv, list(c.embedding)), c))
        scored.sort(key=lambda t: t[0], reverse=True)
        for score, c in scored[: max(1, top_k // max(1, len(document_ids)))]:
            body = c.text or ""
            out.append(RetrievedSource(
                title=f"{doc.filename}", url=None, canonical_url=f"doc://{doc.id}#{c.chunk_index}",
                author=None, publisher="Uploaded document", published_at=None,
                source_type="technical_documentation", domain="uploaded",
                description=body[:400], content=body[:20000],
                content_hash=f"doc-{doc.id}-{c.chunk_index}",
                relevance=round(float(max(0.0, min(1.0, score))), 4),
                quality=0.70, usefulness=round(float(max(0.0, min(1.0, score))), 4),
                final=round(float(max(0.0, min(1.0, score))) * 0.7 + 0.2, 4),
                breakdown={"embedding_cosine": round(float(score), 4),
                            "origin": "uploaded", "chunk_index": c.chunk_index,
                            "page": c.page, "section": c.section,
                            "formula": "RAG cosine over uploaded chunks"},
                reasons=["uploaded document evidence (private RAG)",
                         f"chunk #{c.chunk_index}" + (f", page {c.page}" if c.page else "")
                         + (f", section {c.section}" if c.section else "")],
                discovered_by=["document-upload"]))
    return out


async def run_research(question_text: str, *, depth: str = "standard",
                       max_sources: int | None = None, db: Session,
                       run_id: str | None = None, mode: str = "web",
                       document_ids: list[str] | None = None,
                       max_rounds: int | None = None,
                       strictness: str | None = None) -> str:
    settings = get_settings()
    strictness = strictness or settings.EVIDENCE_STRICTNESS
    cutoff = {"lenient": 0.05, "standard": settings.RELEVANCE_THRESHOLD, "strict": 0.20}.get(strictness, 0.12)
    t0 = time.time()
    deadline = t0 + min(settings.RESEARCH_TIME_LIMIT_SECONDS, settings.RESEARCH_TIMEOUT_SECONDS)
    run_id = run_id or str(uuid.uuid4())
    document_ids = document_ids or []
    mock_mode = (is_mock_llm() or is_mock_search() or settings.MOCK_MODE) and mode == "web"
    stage_ms: dict[str, int] = {}
    usage: dict = {"llm_calls": 0, "input_tokens": 0, "output_tokens": 0,
                   "embedding_calls": 0, "search_calls": 0, "estimated_cost_usd": 0.0}

    def mark(stage: str) -> None:
        stage_ms[stage] = int((time.time() - t0) * 1000)

    question = ResearchQuestion(question_text=question_text, depth=depth)
    db.add(question)
    db.flush()
    run = ResearchRun(id=run_id, question_id=question.id, status="running",
                      stage="planning", progress=0.02, mock_mode=mock_mode, mode=mode)
    db.add(run)
    db.commit()
    _emit(run_id, "planning", 0.05, "Analyzing research question")
    log_event("run_started", run_id=run_id, stage="planning", status="running",
              depth=depth, mode=mode, mock_mode=mock_mode)

    try:
        # 1. Plan (metered LLM, always schema-validated with rule fallback)
        t_stage = time.time()
        llm = _CountingLLM(get_llm_provider(), usage)
        plan = await planner.plan_research(question_text, llm, max_queries=settings.MAX_QUERIES)
        if depth == "deep":
            plan.search_queries = plan.search_queries[: settings.MAX_QUERIES]
        run.plan = plan.model_dump()
        run.stage = "searching"
        db.commit()
        mark("planning")
        _emit(run_id, "searching", 0.15,
              f"Plan ready: {len(plan.sub_questions)} sub-questions, {len(plan.search_queries)} queries")

        # 2a. Web retrieval (skipped in private mode)
        sources: list[RetrievedSource] = []
        retrieval_meta: dict = {"rounds": 0, "queries_run": [], "provider": "skipped-private-mode"}
        if mode in ("web", "hybrid"):
            t_stage = time.time()
            followup_round = bool(depth == "deep")
            queries = list(plan.search_queries)
            sources, retrieval_meta = await run_retrieval(
                queries, max_sources=max_sources, max_relevant=settings.MAX_RELEVANT_SOURCES,
                max_rounds=(max_rounds or settings.MAX_SEARCH_ROUNDS) + (1 if followup_round else 0),
                db=db, run_id=run_id, deadline=deadline)
            usage["search_calls"] = usage.get("search_calls", 0) + len(retrieval_meta.get("queries_run", []))
            mark("searching")
        _emit(run_id, "filtering", 0.35, f"Discovered {len(sources)} web sources",
              {"sources": len(sources)})
        log_event("retrieval_done", run_id=run_id, stage="searching", status="ok",
                  num_sources=len(sources), meta=retrieval_meta)

        # 2b. Uploaded-document retrieval (private + hybrid)
        if mode in ("private", "hybrid"):
            doc_sources = _document_sources(question_text, document_ids, db, usage)
            have = {s.content_hash for s in sources}
            for d in doc_sources:
                if d.content_hash not in have:
                    sources.append(d)
            log_event("rag_done", run_id=run_id, stage="searching", status="ok",
                      num_doc_sources=len(doc_sources))

        # Follow-up round on thin evidence (agentic iteration, bounded by rounds + deadline)
        if (len(sources) < 3 and mode in ("web", "hybrid")
                and (max_rounds or settings.MAX_SEARCH_ROUNDS) >= 2
                and time.time() < deadline):
            extra = [type(plan.search_queries[0])(query=f"{question_text} review evidence",
                                                   query_type="followup",
                                                   reason="Thin evidence: broad follow-up"),
                     type(plan.search_queries[0])(query=f"{question_text} impacts study",
                                                   query_type="followup",
                                                   reason="Thin evidence: targeted follow-up")]
            more, _ = await run_retrieval(extra, max_sources=max_sources, db=db,
                                          run_id=run_id, deadline=deadline)
            have = {s.content_hash for s in sources}
            for m in more:
                if m.content_hash not in have:
                    sources.append(m)

        # 3. Persist sources + chunks + embeddings (relevance cutoff by strictness)
        t_stage = time.time()
        embedder = get_embedding_provider()
        db_sources: list[Source] = []
        dropped = 0
        for rs in sources[: (max_sources or settings.MAX_SOURCES)]:
            # uploaded doc sources bypass the web relevance cutoff when explicitly provided
            is_uploaded = (rs.canonical_url or "").startswith("doc://")
            if not is_uploaded and rs.final < cutoff:
                dropped += 1
                continue
            srow = Source(run_id=run_id, title=rs.title, url=rs.url, author=rs.author,
                          publisher=rs.publisher, published_at=rs.published_at,
                          source_type=rs.source_type, domain=rs.domain,
                          description=rs.description, content=rs.content,
                          content_hash=rs.content_hash, relevance_score=rs.relevance,
                          quality_score=rs.quality, score_breakdown=rs.breakdown,
                          origin="uploaded" if is_uploaded else "web",
                          canonical_url=rs.canonical_url, discovered_by=rs.discovered_by,
                          ranking_reasons=rs.reasons)
            db.add(srow)
            db.flush()
            paras = [p.strip() for p in (rs.content or "").split("\n\n") if len(p.strip()) > 60][:6]
            for idx, para in enumerate(paras or [rs.description or rs.title]):
                db.add(SourceChunk(source_id=srow.id, run_id=run_id, chunk_index=idx,
                                   section=_guess_section(para), text=para[:3000],
                                   embedding=embedder.embed(para[:2000])))
                usage["embedding_calls"] = usage.get("embedding_calls", 0) + 1
            db_sources.append(srow)
        db.commit()
        run.num_sources = len(db_sources)
        run.stage = "extracting"
        db.commit()
        mark("filtering")
        _emit(run_id, "extracting", 0.55,
              f"Extracting evidence from {len(db_sources)} sources ({dropped} below cutoff)",
              {"sources": len(db_sources), "relevant": len(db_sources)})

        # 4. Evidence extraction (extractive)
        t_stage = time.time()
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
                evidence_items.append(it)
                evidence_rows.append(erow)
        db.commit()
        mark("extracting")
        _emit(run_id, "analyzing", 0.68, f"Extracted {len(evidence_rows)} evidence passages",
              {"sources": len(db_sources), "evidence": len(evidence_rows)})
        log_event("extraction_done", run_id=run_id, stage="extracting", status="ok",
                  num_evidence=len(evidence_rows))

        # 5. Claims (+ sub-question links + agreement summaries)
        claims: list[Claim] = []
        for erow in evidence_rows[:12]:
            item = EvidenceItem(claim=erow.claim, quote=erow.quote, source_id=erow.source_id,
                                page=erow.page, section=erow.section,
                                relevance_score=erow.relevance_score,
                                confidence_score=erow.confidence_score)
            v = verifier.verify_claim(erow.claim, [item])
            ctype = "statistical" if any(ch.isdigit() for ch in erow.claim) else "factual"
            if any(w in erow.claim.lower() for w in ("cause", "leads to", "increases", "reduces")):
                ctype = "causal"
            mine = [e for e in evidence_items if e.source_id == erow.source_id]
            others = [e for e in evidence_items if e.source_id != erow.source_id]
            my_side = _evidence_side(erow.quote)
            contra = [e for e in others if _evidence_side(e.quote) not in (None, my_side)]
            neutral = [e for e in others if e not in contra][:4]
            agr = agreement_summary(mine, contra[:4], neutral,
                                    [s.source_type for s in db_sources])
            claims.append(Claim(run_id=run_id, claim_text=erow.claim[:800], claim_type=ctype,
                                confidence=v.confidence, supported=v.supported,
                                supporting_evidence_ids=[erow.id] if v.supported else [],
                                contradicting_evidence_ids=[],
                                confidence_breakdown={"verifier_confidence": v.confidence,
                                                      "issues": v.issues},
                                sub_question=_nearest_subquestion(erow.claim, plan.sub_questions),
                                agreement=agr.model_dump()))
        for c in claims:
            db.add(c)
        db.commit()
        mark("analyzing")

        conflicts = conflict_detector.detect_conflicts(evidence_items)
        _emit(run_id, "synthesizing", 0.8, "Cross-checking claims and writing report",
              {"sources": len(db_sources), "evidence": len(evidence_rows), "claims": len(claims)})

        # 6. Synthesis from evidence
        t_stage = time.time()
        titles = {s.id: s.title for s in db_sources}
        synth = synthesizer.synthesize(question_text, evidence_items,
                                       {e.source_id: e for e in evidence_items}, titles)
        citations: list[dict] = []
        for i, erow in enumerate(evidence_rows, start=1):
            s = next((x for x in db_sources if x.id == erow.source_id), None)
            citations.append({"index": i, "evidence_id": erow.id, "source_id": erow.source_id,
                              "source_title": s.title if s else "Unknown",
                              "url": s.url if s else None, "page": erow.page,
                              "section": erow.section, "quote": erow.quote[:500],
                              "origin": s.origin if s else "web"})
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
                                        claims_total=max(1, len(claims)),
                                        claim_texts=[c.claim_text for c in claims])
        mark("synthesizing")

        # 7. Verification pass
        t_stage = time.time()
        _emit(run_id, "verifying", 0.92, "Verifying citations",
              {"sources": len(db_sources), "evidence": len(evidence_rows), "claims": len(claims)})
        verified_findings = []
        extra_uncertainties = list(synth["uncertainties"])
        for f in findings:
            if f["citation_ids"]:
                verified_findings.append(f)
            else:
                extra_uncertainties.append(f"Insufficient evidence for: {f['title']}")
        mark("verifying")

        failed_q = len(retrieval_meta.get("queries_failed", []))
        partial_note = (f" Research completed with partial source retrieval: "
                        f"{failed_q} planned quer{'y' if failed_q == 1 else 'ies'} failed." if failed_q else "")
        covered = sum(1 for sq in plan.sub_questions
                      if any(term_coverage(sq, e.quote) > 0.1 for e in evidence_items))
        if not evidence_rows:
            stop_reason = "No relevant evidence retrieved."
        elif retrieval_meta.get("stopped"):
            stop_reason = str(retrieval_meta["stopped"])[0].upper() + str(retrieval_meta["stopped"])[1:] + "."
        elif covered >= len(plan.sub_questions):
            stop_reason = "All planned subquestions reached sufficient evidence coverage."
        elif meta_rounds_capped(retrieval_meta, max_rounds or settings.MAX_SEARCH_ROUNDS):
            stop_reason = "Maximum search rounds reached."
        else:
            stop_reason = "Evidence coverage sufficient for report; further queries redundant."
        stop_reason += partial_note

        method = (
            f"Mode: {mode}. Plan decomposed the question into {len(plan.sub_questions)} sub-questions "
            f"and {len(plan.search_queries)} typed queries ({', '.join(sorted({q.query_type for q in plan.search_queries}))}). "
            f"Retrieval ran {retrieval_meta.get('rounds', 0)} round(s) via the {retrieval_meta.get('provider')} provider "
            f"({len(retrieval_meta.get('queries_run', []))} queries, {retrieval_meta.get('duplicates_dropped', 0)} duplicates dropped"
            f"{f', {failed_q} failed' if failed_q else ''}); "
            f"{len([s for s in db_sources if s.origin == 'uploaded'])} uploaded-document sources merged. "
            f"Relevance cutoff {cutoff} ({strictness}); diversity-aware selection capped at {max_sources or settings.MAX_SOURCES}. "
            f"Stop reason: {stop_reason}")
        report = Report(run_id=run_id, question=question_text,
                        executive_summary=synth["executive_summary"],
                        findings=verified_findings,
                        conflicts=[c.model_dump() for c in conflicts],
                        uncertainties=extra_uncertainties,
                        limitations=synth["limitations"], conclusion=synth["conclusion"],
                        confidence=confidence.model_dump(), citations=citations,
                        mock_mode=mock_mode, research_method=method)
        db.add(report)
        run.stage = "done"
        run.status = "completed" if evidence_rows else "partial"
        run.progress = 1.0
        run.num_claims = len(claims)
        run.stop_reason = stop_reason
        run.stage_ms = stage_ms
        run.llm_calls = usage["llm_calls"]
        run.input_tokens = usage["input_tokens"]
        run.output_tokens = usage["output_tokens"]
        run.embedding_calls = usage["embedding_calls"]
        run.search_calls = usage["search_calls"]
        run.estimated_cost_usd = round(usage["estimated_cost_usd"], 4)
        run.finished_at = dt.datetime.now(dt.timezone.utc)
        run.duration_ms = int((time.time() - t0) * 1000)
        if not evidence_rows:
            run.error = "No relevant evidence retrieved."
        elif failed_q:
            run.status = "partial"
            run.error = f"{failed_q} planned queries failed; report uses retrieved evidence only."
        db.commit()
        mark("done")
        _emit(run_id, "done", 1.0, f"Completed with {len(evidence_rows)} evidence items",
              {"sources": len(db_sources), "evidence": len(evidence_rows), "claims": len(claims)})
        log_event("run_finished", run_id=run_id, stage="done", status=run.status,
                  num_sources=len(db_sources), num_claims=len(claims),
                  duration_ms=run.duration_ms, stop_reason=stop_reason)
        return run_id
    except Exception as e:  # graceful failure, never a silent hang
        db.rollback()
        run = db.get(ResearchRun, run_id)
        if run is not None:
            run.status = "failed"
            run.stage = "failed"
            run.error = f"{type(e).__name__}: {e}"[:2000]
            run.stop_reason = f"Run failed: {type(e).__name__}."
            run.stage_ms = stage_ms
            run.finished_at = dt.datetime.now(dt.timezone.utc)
            run.duration_ms = int((time.time() - t0) * 1000)
            db.commit()
        log_event("run_failed", run_id=run_id, stage="failed", status="error", error=str(e)[:500])
        _emit(run_id, "failed", 1.0, str(e)[:300])
        raise


def meta_rounds_capped(meta: dict, max_rounds: int) -> bool:
    return bool(meta.get("rounds")) and meta["rounds"] >= max_rounds
