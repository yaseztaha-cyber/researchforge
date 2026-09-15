# ResearchForge — Methodology

1. **Planning**: LLM proposes sub-questions/queries as strict JSON validated by `ResearchPlan`;
   any malformed output falls back to a deterministic rule-based decomposition.
2. **Retrieval**: 1–2 bounded rounds over `SearchProvider`s; dedup by content hash; rank by
   `0.65*relevance + 0.35*quality` where relevance = token-overlap blend and quality =
   source-type weight + trusted-domain bonus (breakdown stored per source).
3. **Extraction**: extractive only — sentences scored by query overlap; `quote` must be a
   verbatim substring of source content.
4. **Claims**: one claim row per evidence lead, typed (factual/statistical/causal/…).
5. **Conflicts**: opposing-signal phrases (concern vs limited-effect) paired into `ConflictItem`s
   with "reason unclear" default instead of invented explanations.
6. **Synthesis**: findings assembled from evidence clusters; uncited content becomes uncertainties.
7. **Verification**: per-claim checks (support present? wording overstated? causation-vs-correlation?
   keyword drift?) downgrade confidence or mark unsupported; dangling `[n]` markers flagged.
8. **Confidence**: `0.30*coverage + 0.25*quality + 0.20*agreement + 0.25*citation_completeness`,
   labeled Low/Medium/High with components exposed.
9. **Stopping**: max rounds/sources, coverage thresholds, diminishing returns, cost budget.
