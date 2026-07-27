# BluePrintReboot Backlog

Stable backlog last edited: 2026-07-27

Current release evidence and individually addressable pending checks live in the generated [Current Release Status](CURRENT_RELEASE_STATUS.md). This backlog does not duplicate mutable counts or verification state.

## Implemented foundations

- [x] v1.0.26 Streamlit finalization, frozen read models, lifecycle safety, and restore-readiness boundary.
- [x] v1.1.0-v1.1.2 GET-only FastAPI foundation and rich local metadata.
- [x] v1.2.0 desktop TypeScript shell, typed client, and same-origin read-only bridge.
- [x] v1.2.1 portable-Node-aware full local validation gate and separate Python/frontend workflow jobs.
- [x] v1.2.2 local runtime and release-evidence closure.
- [x] v1.3.0 safe read-only Reader/PDF vertical slice.
- [x] v1.3.1 release-state convergence, tracked-entry hygiene, and deterministic tracker export.
- [x] v1.5.0 read-only Reader Snapshot vertical slice implementation.
- [x] v1.5.1 bounded Reader write vertical slice implementation.
- [x] v1.5.2 Projects and Tags read parity implementation.

## v1.5.2 Projects and Tags read parity

- [x] Add strict paginated `GET /projects` and bounded `GET /projects/{project_id}` contracts through read-model and adapter boundaries.
- [x] Expose allowlisted Project status, priority, tags, description, timestamps, stored link types, and linked-paper summaries.
- [x] Keep missing linked papers as explicit orphan states; return controlled 404/422/503 responses without paths or internal exception details.
- [x] Add strict paginated `GET /tags` and fixed `GET /tags/summary` contracts backed by the Tag Book and real candidate evidence.
- [x] Preserve primary, empty, and legacy Tag Book reads while excluding `source_paths`, configuration locations, raw records, and write internals.
- [x] Replace the Projects and Tags placeholders with real list/detail/table views and shared loading, empty, offline, read-model error, not-found, and retry behavior.
- [x] Keep the same-origin bridge path allowlist exact and preserve PDF Range plus Reader command behavior.
- [x] Add disposable backend and frontend regressions for deterministic pagination, failures, privacy, non-mutation, real fields, and absence of write controls.
- [ ] Complete manual checks for real Project list/detail/link states, real canonical Tags, empty/offline behavior, and Project/Tag storage non-mutation.
- [ ] Record v1.5.2 pull request, hosted CI, merge, tag, GitHub Release, or post-merge evidence only after those events occur.
- [ ] Complete R-113 beyond Projects/Tags; Settings remains a placeholder and G2 remains open.

## v1.5.1 bounded Reader write vertical slice

- [x] Add independent metadata PATCH and Reading Note PUT command-service boundaries; do not add a combined save.
- [x] Expose only title, authors, year, journal, DOI, abstract, and keywords with strict bounded schemas and unknown-field rejection.
- [x] Add deterministic metadata revisions and explicit absent-note SHA-256 semantics; reject stale commands with zero mutation.
- [x] Canonicalize Reading Note headers while preserving user section bodies and atomic replacement behavior.
- [x] Restore the original index and note after injected coupled metadata/header failures.
- [x] Extend the same-origin bridge with an exact method/path allowlist and keep Range forwarding PDF-only.
- [x] Add accessible independent editors, draft-preserving conflict/error handling, explicit reload, and paper-transition warnings.
- [x] Preserve the v1.5.0 Reader Snapshot, PDF.js lifecycle, managed PDF API, stable identity, local-only binding, and Streamlit workflows.
- [x] Record user-performed Reader pairing, absent-note clean state, save/reload, canonical-header, conflict, restart, transition, and cross-surface visibility evidence.
- [ ] Perform the unreadable persisted-note warning and missing managed-PDF manual scenarios.
- [ ] Record v1.5.1 pull request, hosted CI, merge, tag, GitHub Release, or post-merge evidence only after those events occur.

## v1.5.0 read-only Reader Snapshot vertical slice

- [x] Add strict nested Reader Snapshot response schemas and an allowlisting adapter that preserves exact saved-note text.
- [x] Add GET-only `GET /papers/{paper_id}/reader` through the existing domain builder and generic 404/503 boundaries.
- [x] Allowlist only the exact same-origin Reader path while preserving PDF binary streaming and Range forwarding.
- [x] Switch the web Reader from paper detail to one snapshot request and show a selectable plain-text persisted-note companion.
- [x] Keep absent note, unreadable note, missing PDF, unknown paper, offline API, retry, and paper transition distinct.
- [x] Preserve the Streamlit write boundary, PDF.js lifecycle, managed-root containment, storage format, dependencies, and stable identity.
- [ ] Complete user-performed runtime validation for unreadable-note and missing-PDF behavior; correct PDF/note pairing, absent note, transition, and API restart now have v1.5.1 evidence.
- [ ] Record v1.5.0 pull request, hosted CI, tag, or publication only after those events actually occur.

## v1.4.3 release-state truth repair

- [x] Derive Reader aggregate status from all Reader child statuses.
- [x] Accept truthful completed Streamlit regression evidence without hard-coding a past state.
- [x] Reject VERIFIED evidence with incomplete language and NOT VERIFIED evidence with completion claims.
- [x] Record PR #6 frontend success and Python smoke failure independently.
- [x] Keep schema 4.0, repository HEAD observational, and mutable PR/workflow identifiers out of validator invariants.
- [x] Preserve product, API, Reader, dependency, storage, and user-data behavior unchanged.

## v1.4.2 post-merge evidence and Reader runtime closure

- [x] Separate the immutable v1.4.0 product baseline from completed PR #5 control-plane evidence.
- [x] Make repository HEAD a nullable, explicitly observational field rather than a committed invariant.
- [x] Keep PR-head CI, post-merge `main` CI, tag existence, and GitHub Release publication structurally independent.
- [x] Preserve conflicting v1.4.0 smoke records as historical evidence while exposing only the canonical current result as current state.
- [x] Add deterministic render, stale-output, tracker-export, privacy, status-control, and fresh-clone regression coverage.
- [x] Manual Reader runtime and separate non-mutating Streamlit evidence were supplied with PR #6; v1.4.3 repairs their contradictory canonical representation.

## v1.4.0 PDF.js Reader foundation

- [x] Replace the native `<object>` primary path with a client-only PDF.js canvas renderer using the existing same-origin stable-`paper_id` route.
- [x] Pin `pdfjs-dist` and bundle the explicit worker locally through the Vinext/Vite `?url` asset path with no CDN.
- [x] Add previous/next/direct-page controls, bounded zoom in/out/reset, accessible labels, and first/last disabled states.
- [x] Remove the redundant one-byte Range availability probe; PDF.js is the authoritative load.
- [x] Add loading, unavailable, render-failure, retry, and clearly labeled conditional native-fallback behavior without mounting two viewers.
- [x] Cancel stale renders and clean loading tasks, loaded documents, pages, canvas state, retry cycles, paper changes, and unmounts.
- [x] Add disabled-by-default development diagnostics and automated document-load/render/cancellation/request-mode contracts without private metadata.
- [x] Preserve full/partial PDF responses, exact lengths, Range headers, 400/416 handling, managed-root containment, and the GET-only route surface.
- Current runtime, source-control, publication, and operational state is intentionally represented only in the canonical manifest and generated status document.

## v1.4.1 release-state single source and tracker convergence

- [x] Evolve `docs/tracker_sync_status.json` into the canonical current release-state manifest.
- [x] Generate `docs/CURRENT_RELEASE_STATUS.md` deterministically and reject stale committed output.
- [x] Separate implementation, source control, automated validation, manual validation, publication, and recurring operational procedures.
- [x] Preserve conflicting smoke records instead of selecting a count silently.
- [x] Derive deterministic external-tracker CSV from the canonical manifest.
- [x] Integrate offline release-state validation into the smoke path.

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

## Next: Reader runtime verification and measured hardening

- [ ] Use a disposable or approved real PDF to inspect initial request count, Range behavior, and first-page perceived load without retaining document identity.
- [ ] Verify repeated route entry/exit and rapid page/zoom interaction do not leave persistent loaders or stale renders.
- [ ] Preserve the native-viewer fallback, managed-root containment, Range delivery, and the existing safe PDF-serving contract.
- [ ] Preserve Streamlit as the write/note workflow until a separately approved command boundary exists.

## Deferred product work

Write APIs; project/tag APIs; OpenAPI-generated TypeScript types; UI redesign; database or user-data migration; installer/packaging; automated restore; cloud sync; background services; OCR; semantic/LLM tagging; multi-user support; knowledge graphs; automatic duplicate operations; and `paper_id` redesign.

## Tracker handoff

- [x] `docs/tracker_sync_status.json` is the canonical versioned release-state manifest and repository handoff for the external roadmap tracker.
- [x] `scripts/export_tracker_status.py` emits deterministic UTF-8 CSV under ignored `artifacts/` by default or at an explicit output path.
- [ ] Import or apply the generated CSV to the external tracker outside repository code; no Drive API, OAuth flow, or sync client is added.
