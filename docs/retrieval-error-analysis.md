# Retrieval Error Taxonomy

## Error Categories

### 1. WRONG_DOMAIN
**Definition:** Retrieved content is about a different topic/domain than the query.

**Indicators:**
- Query terms absent from retrieved text
- Source domain unrelated to query domain
- Semantic similarity low despite lexical overlap

**Example:**
- Query: "desalination brine effects on marine life"
- Retrieved: "battery brine in lithium-ion electrolytes"
- Classification: WRONG_DOMAIN

### 2. WRONG_SOURCE
**Definition:** Source is related to query domain but lacks authority/relevance for the specific question.

**Indicators:**
- Source type inappropriate (blog for scientific question)
- Publisher not authoritative for topic
- Publication date too old for current question

**Example:**
- Query: "latest IPCC 2023 sea level rise projections"
- Retrieved: 2010 blog post about sea levels
- Classification: WRONG_SOURCE

### 3. RIGHT_SOURCE_WRONG_CHUNK
**Definition:** Correct document retrieved, but wrong chunk selected from it.

**Indicators:**
- Source document is relevant/authoritative
- Retrieved chunk doesn't contain answer
- Better chunk exists in same document

**Example:**
- Document: "Desalination Environmental Impact Assessment 2023" (relevant)
- Retrieved chunk: "Executive summary mentions brine" (too vague)
- Better chunk: "Section 4.2: Brine discharge increases salinity by 15-20% within 100m of outfall"
- Classification: RIGHT_SOURCE_WRONG_CHUNK

### 4. RIGHT_CHUNK_WRONG_RANK
**Definition:** Relevant evidence exists in retrieved set but ranked too low to be used.

**Indicators:**
- Relevant chunk appears in candidates (top_k × 3) but not in final selected
- Semantic similarity high but hybrid score penalized
- MMR diversity pushed it out

**Example:**
- Relevant chunk at position 12 of 20 candidates
- Final selection top 8 excludes it
- Classification: RIGHT_CHUNK_WRONG_RANK

### 5. MISSING_SOURCE
**Definition:** Retrieval system never discovers a relevant source that exists in corpus/web.

**Indicators:**
- Known relevant document not in candidates
- Query terms present in missing doc but not retrieved
- Embedding similarity too low or query expansion failed

**Example:**
- Known EPA report on desalination exists in corpus
- Query "desalination environmental impacts" returns 0 EPA sources
- Classification: MISSING_SOURCE

### 6. DUPLICATE_SOURCE
**Definition:** Multiple retrieved results are effectively the same content from different URLs/sources.

**Indicators:**
- Content hash match or >0.92 cosine similarity
- Different URLs, same content
- Same publisher, mirrored content

**Example:**
- Source A: EPA.gov/report.pdf
- Source B: mirror.site.gov/epa/report.pdf
- Same content, different URLs
- Classification: DUPLICATE_SOURCE

### 7. QUERY_DECOMPOSITION_FAILURE
**Definition:** Research planner failed to generate useful search queries.

**Indicators:**
- Generated queries too broad/narrow
- Missing key subtopics
- Queries redundant (same intent paraphrased)

**Example:**
- Question: "How does desalination affect marine ecosystems?"
- Generated queries: ["desalination", "desalination effects", "marine effects"] (missing "brine", "salinity", "intake")
- Classification: QUERY_DECOMPOSITION_FAILURE

### 8. EVIDENCE_EXTRACTION_FAILURE
**Definition:** Correct source/chunk retrieved but evidence extraction fails.

**Indicators:**
- Evidence quote doesn't support claim
- Quote truncated/misaligned
- Extracted claim not in source text

**Example:**
- Chunk contains: "Brine discharge CAN increase salinity..."
- Extracted claim: "Brine discharge increases salinity"
- Missing hedge "can" → overstatement
- Classification: EVIDENCE_EXTRACTION_FAILURE (overstatement subtype)

### 9. SOURCE_METADATA_FAILURE
**Definition:** Useful source penalized because metadata missing/wrong.

**Indicators:**
- Missing publication date → recency penalty
- Wrong source_type → quality penalty
- Missing domain → domain bonus lost

**Example:**
- Authoritative EPA report missing `published_at`
- Scored lower than blog with date
- Classification: SOURCE_METADATA_FAILURE

### 10. CONFLICT_MISCLASSIFICATION
**Definition:** Relevant disagreement exists but conflict classification wrong.

**Indicators:**
- Two sources disagree on same proposition
- Classification says "unclear" with evidence for specific type
- Or classifies as "direct_contradiction" when actually methodological difference

**Example:**
- Source A: "Brine increases salinity 20% within 100m"
- Source B: "Salinity returns to baseline within 500m"
- Classified as "unclear" but actually SCOPE difference (near-field vs far-field)
- Classification: CONFLICT_MISCLASSIFICATION (should be SCOPE)

---

## Error Schema (Database)

```sql
CREATE TABLE retrieval_error (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    research_run_id UUID NOT NULL REFERENCES research_runs(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES research_questions(id) ON DELETE CASCADE,
    query TEXT NOT NULL,
    error_type TEXT NOT NULL,  -- one of the 10 categories above
    source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
    chunk_id UUID REFERENCES document_chunks(id) ON DELETE SET NULL,
    expected TEXT,  -- what should have happened
    actual TEXT,    -- what actually happened
    severity TEXT DEFAULT 'medium',  -- low|medium|high|critical
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX ix_retrieval_error_run ON retrieval_error(research_run_id);
CREATE INDEX ix_retrieval_error_type ON retrieval_error(error_type);
```

---

## Error Annotation Workflow

1. **Automatic classification** during evaluation:
   - If `retrieval_precision < threshold` → auto-suggest categories
   - If `missing_source` detected (gold source not in candidates) → flag
   - If `duplicates > threshold` → flag DUPLICATE_SOURCE

2. **Human review** via evaluation UI:
   - Show query, retrieved candidates, expected vs actual
   - Select error category from dropdown
   - Add notes

3. **Aggregation** for dashboard:
   - Count per category per run
   - Trend over time
   - Per-category precision/recall

---

## Classification Guidelines

| Category | Auto-detectable? | Human review needed? |
|----------|------------------|---------------------|
| WRONG_DOMAIN | Yes (semantic sim + domain mismatch) | Sometimes |
| WRONG_SOURCE | Partially (source_type check) | Often |
| RIGHT_SOURCE_WRONG_CHUNK | Hard | Usually |
| RIGHT_CHUNK_WRONG_RANK | Yes (rank comparison) | Sometimes |
| MISSING_SOURCE | Yes (gold source check) | Yes |
| DUPLICATE_SOURCE | Yes (content_hash/cosine) | Rarely |
| QUERY_DECOMPOSITION_FAILURE | Partially (query diversity) | Often |
| EVIDENCE_EXTRACTION_FAILURE | Partially (verifier flags) | Often |
| SOURCE_METADATA_FAILURE | Yes (metadata completeness) | Rarely |
| CONFLICT_MISCLASSIFICATION | Hard | Usually |

---

## Severity Guidelines

| Severity | Definition |
|----------|------------|
| low | Minor ranking issue; relevant evidence still found |
| medium | Relevant evidence missed or ranked low; impacts claim support |
| high | Critical evidence missing; unsupported claims or wrong conclusions |
| critical | Systematic failure; entire category of queries affected |

---

## Examples from v0.3 Fixtures

| Question | Error Type | Details |
|----------|------------|---------|
| "What policies reduced urban air pollution?" | MISSING_SOURCE | EPA 2023 report not in fixtures |
| "How does deforestation affect rainfall?" | WRONG_DOMAIN | Retrieved CS papers on random forests |
| "CRISPR off-target effects" | RIGHT_SOURCE_WRONG_CHUNK | Correct paper, chunk about delivery not off-target |
| "LLM agent failures" | QUERY_DECOMPOSITION_FAILURE | Queries too broad: "AI agents", "LLM problems" |
| "Antibiotic resistance drivers" | CONFLICT_MISCLASSIFICATION | Classified "unclear" but actually POPULATION diff (hospital vs community) |

---

## Implementation Notes

- Error records created during `run_evaluation.py` when `precision < 0.5` or `recall_proxy < 0.5`
- Human annotator UI at `/evaluation/errors` (new page)
- Aggregated in `/api/eval/errors/summary` for dashboard
- Never fabricate errors — only record from actual failures