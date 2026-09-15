# ResearchForge — Methodology

1. **Planning**: LLM proposes sub-questions/queries as strict JSON validated by `ResearchPlan`;
   any malformed output falls back to a deterministic rule-based decomposition.
2. **Retrieval**: 1–2 bounded rounds over `SearchProvider`s; dedup by content hash; rank by
   `0.65*relevance + 0.35*quality` where relevance = token-overlap blend and quality =
   source-type weight + trusted-domain bonus (breakdown stored per source).
3. **Extraction**: extractive only — sentences scored by query overlap; `quote` must be a
   verbatim substring of source content.
4. **Claims**: one claim row per evidence lead, typed (factual/statistical/causal/…),
   linked to the nearest sub-question and carrying an **agreement summary**
   (supporting/contradicting/neutral counts + source diversity; count ≠ truth).
5. **Conflicts (v2)**: opposing-signal phrases paired only when they share topic
   tokens, then **conservatively classified** (direct_contradiction only with
   explicit negation of the same proposition; methodological/population/
   time_period/measurement/definition/scope only with textual cues on both
   sides; otherwise "unclear" with "Reason … could not be established…").
6. **Synthesis**: findings assembled from evidence clusters; uncited content becomes uncertainties.
7. **Verification**: per-claim checks (support present? wording overstated? causation-vs-correlation?
   keyword drift?) downgrade confidence or mark unsupported; dangling `[n]` markers flagged.
8. **Confidence (v2)**: `0.25·coverage + 0.20·quality + 0.15·agreement + 0.20·citation
   + 0.10·specificity − 0.10·contradiction_penalty`, labeled Low/Medium/High with
   components exposed. A documented heuristic — never presented as probability.
   Calibration (Brier/ECE) is implemented but reports "unavailable" without labels.
9. **Stopping + cost**: max rounds/sources/queries, coverage thresholds, diminishing
   returns, time (`RESEARCH_TIME_LIMIT`) and cost budgets. `stop_reason`, per-stage
   latency, and LLM/search/embedding usage are stored per run and shown in the report.
