# Screenshot checklist (capture from the REAL running app — no mockups)

Prerequisites: `python -m uvicorn app.main:app` (backend) + `npm run dev`
(frontend); run one web, one hybrid, and one conflicting-evidence research first.

1. [ ] Landing/research screen (`/`) with mode selector + advanced settings
2. [ ] Live research progress with real counts (sources/evidence/claims)
3. [ ] Final report with method section + confidence breakdown
4. [ ] "Show me why" claim inspector open on a finding
5. [ ] Source "Why this source ranked here" expanded
6. [ ] Conflict side-by-side comparison with classification badge
7. [ ] Research graph (SVG) + list-view fallback
8. [ ] Evaluation dashboard with versioned benchmark table
9. [ ] Document upload + hybrid-mode origin badges
10. [ ] Mobile layout (≤480px, collapsible panels)

Save captures under `docs/screenshots/` as `01-landing.png`, … and reference
them from README. Do not commit placeholder or AI-generated images.
