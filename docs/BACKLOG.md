# BluePrintReboot Backlog

Last synced: 2026-07-21

## Implemented foundations

- [x] v1.0.26 Streamlit finalization, frozen read models, lifecycle safety, and restore-readiness boundary.
- [x] v1.1.0-v1.1.2 GET-only FastAPI foundation and rich local metadata.
- [x] v1.2.0 desktop TypeScript shell, typed client, and same-origin read-only bridge.
- [x] v1.2.1 portable-Node-aware full local validation gate and separate Python/frontend workflow jobs.
- [x] v1.2.2 local runtime and release-evidence closure.
- [x] v1.3.0 safe read-only Reader/PDF vertical slice.

## v1.3.1 release-state convergence and repository hygiene

- [x] Remove the tracked root console-output artifact `tatus --short` without reading or changing ignored user-data directories.
- [x] Reconcile PR #2 commit, push, pull request, merge, hosted-CI, Streamlit regression, restore, tag, and publication state across current documents.
- [x] Record PR #2 hosted run `29641757582` independently from post-merge `main` run `29641792069`.
- [x] Replace the hard-coded provisional CI assertion with conditional state invariants and contradiction tests.
- [x] Add tracked-entry-only repository hygiene validation and integrate it into smoke and hosted CI.
- [x] Add a versioned `R-001`-`R-025` external-tracker mapping and deterministic standard-library CSV export.
- [x] Record final v1.3.1 focused tests 40 passed, smoke 94/0/0, pytest 524 passed, `npm ci`, lint, production build, and 14 Node tests passed; final diff/status results are recorded after documentation reconciliation.
- [ ] Perform a genuinely clean-PC restore rehearsal.
- [ ] Create a v1.3.x tag only after explicit approval.
- [ ] Publish a v1.3.x GitHub release only after explicit approval.

## v1.3.0 read-only Reader/PDF vertical slice

- [x] Add `GET /papers/{paper_id}/pdf` with managed-root containment, explicit failure states, inline delivery, streaming, and browser byte-range support.
- [x] Extend the same-origin bridge for only the exact PDF GET route, including binary streaming, Range forwarding, and safe response-header preservation.
- [x] Add `/papers/{paper_id}/reader`, explicit metadata/PDF/offline/native-viewer states, and stable-identity navigation from Paper Detail.
- [x] Keep notes, metadata changes, PDF maintenance, and every other write workflow in Streamlit.
- [x] Record the full local baseline: smoke 90/0/0, pytest 496 passed, lint passed, build passed, and 14 Node tests passed.
- [x] Complete disposable and user-performed Reader/PDF validation without retaining private identity or path evidence.
- [x] Complete the separate user-performed Streamlit regression without a mutation action.
- [x] Commit and push the v1.3.0 change, create PR #2, and merge PR #2 into `main`.
- [x] Verify PR #2 hosted CI run `29641757582` and both required jobs.
- [x] Verify post-merge `main` hosted CI run `29641792069` and both required jobs.
- [ ] Complete the user-performed clean-PC restore rehearsal.
- [ ] Create a v1.3.x tag only after explicit approval.
- [ ] Publish a v1.3.x GitHub release only after explicit approval.

## Historical v1.2.2 evidence closure

- [x] Local setup, launch diagnostics, full local validation, manual runtime checks, and separate Streamlit checks were completed.
- [x] PR #1 hosted CI run `29639358889` succeeded for Python and frontend.
- [x] Commit, push, PR #1, merge, and the v1.2.2 tag are present in repository history.
- [ ] A clean-PC restore rehearsal remains unperformed.
- [ ] A published GitHub release for v1.2.2 is not asserted without separate evidence.

## Next: measured Reader hardening

- [ ] Measure native Reader request count and index-read latency with disposable data before adding caching or endpoints.
- [ ] Evaluate PDF.js only as a separately scoped, dependency-reviewed response to observed limitations.
- [ ] Preserve native-viewer fallback, managed-root containment, Range delivery, and the existing safe PDF-serving contract.
- [ ] Preserve Streamlit as the write/note workflow until a separately approved command boundary exists.

## Deferred product work

Write APIs; project/tag APIs; OpenAPI-generated TypeScript types; UI redesign; database or user-data migration; installer/packaging; automated restore; cloud sync; background services; OCR; semantic/LLM tagging; multi-user support; knowledge graphs; automatic duplicate operations; and `paper_id` redesign.

## Tracker handoff

- [x] `docs/tracker_sync_status.json` is the canonical versioned repository handoff for the external roadmap tracker.
- [x] `scripts/export_tracker_status.py` emits deterministic UTF-8 CSV under ignored `artifacts/` by default or at an explicit output path.
- [ ] Import or apply the generated CSV to the external tracker outside repository code; no Drive API, OAuth flow, or sync client is added.
