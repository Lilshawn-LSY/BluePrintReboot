# Release Checklist

Current evidence is generated from the canonical manifest. Inspect [Current Release Status](CURRENT_RELEASE_STATUS.md) rather than recording mutable counts, source-control state, or manual completion in this checklist.

## v1.5.12-pre-ux-pdf-foundation

- [x] PDF.js keeps logical viewport/CSS size and semantic zoom independent from bounded DPR-aware backing-canvas resolution.
- [x] Selectable PDF.js text uses the same page viewport and lifecycle as canvas rendering; stale layers cancel and clear across page/zoom/document/retry/fallback/unmount transitions.
- [x] The internal selection contract reports canonical 1-based page numbers and top-left page-normalized rectangles independent of DPR and zoom.
- [x] Optional `pdf-inspector==0.2.6` is isolated behind BluePrint-owned structured extraction models and explicit mixed upstream index normalization.
- [x] Extraction/cache state distinguishes not-extracted, success, cached, stale, failed, and OCR-needed outcomes while preserving partial mixed-document text.
- [x] MarkItDown/pypdf fallback, SHA-256 stale checks, restart reuse, and valid old-cache preservation remain covered by disposable tests.
- [x] OCR execution, selection persistence, Research Blocks, highlight UX, and Reader/Library visual redesign remain absent.
- [ ] Representative real-PDF DPR, text alignment, selection-coordinate, classification, stale-cache, restart, and Library-to-Reader checks remain unverified until user-performed.
- [ ] v1.5.12 PR-head CI, merge to `main`, tag, GitHub Release, post-merge `main` CI, and clean-PC restore remain unverified until observed.

## Historical v1.5.11-library-paper-workflow-closure

- [x] Library is the primary web Paper collection: scan/import, server-backed search/filter/pagination, explicit enrichment reuse, and Paper Detail/Reader navigation are one bounded workflow.
- [x] Search/filter occurs in the Paper read model before pagination and returns only allowlisted Paper summary fields.
- [x] Managed scan distinguishes registered paths, exact duplicate content, uniquely reconnectable missing Papers, and ambiguous reconnect candidates without automatic mutation.
- [x] Explicit reconnect is managed-root-contained, lock/reload/atomic-persistence protected, keeps `paper_id`, and updates only the managed-file identity fields after a fresh exact-content check.
- [x] Disposable backend/frontend regressions cover search/filter/pagination, bridge allowlisting, offline/error states, and non-destructive reconnect preservation.
- [x] User-provided manual validation verified the full v1.5.11 browser workflow, offline/conflict states, restart persistence, existing-surface regressions, and browser Network payload privacy.
- [ ] v1.5.11 PR-head CI, merge to `main`, v1.5.11 tag, GitHub Release, post-merge `main` CI, and clean-PC restore remain open until separately observed.

## Historical v1.5.10-tag-governance-candidate-review

- [x] Runtime, package/lockfile, README, local release manifest, release-note draft, and generated status identify v1.5.10 while the immutable released baseline remains v1.4.0.
- [x] Canonical Tag Book create/edit/alias/deprecate commands are revision-checked, lock-protected, atomically persisted, and return controlled stale/conflict/error states.
- [x] Canonical/alias identity collisions, ambiguous aliases, self-aliases, and inconsistent normalization are rejected using existing conservative Tag Book rules; categories remain bounded metadata.
- [x] Deprecation retains the canonical record and historical Paper relationships. No governance action deletes, renames, or rewrites legacy/noncanonical Paper tag text.
- [x] Candidate generation and persisted review are Paper-tag non-mutating. Candidate source/evidence and existing score/confidence fields remain inspectable without fabricated values.
- [x] Approve, reject, and promote are explicit review actions. Promotion resolves or creates an active canonical registry entry without duplicate canonical/alias identities; rejected candidates remain persisted until deliberate reset/re-generation.
- [x] Apply is a separate final action that reuses the existing v1.5.7 Paper tag command, including tag revisions, locking, atomicity, conflict/no-op behavior, and Reading Note draft safety.
- [x] The deterministic fixture baseline records 2 expected candidates present, 0 misses, 1 false positive, and precision-like 0.667 across 3 cases; it is measurement only.
- [x] Disposable backend/frontend tests cover registry governance, candidate non-mutation/review/promotion/apply, stale conflicts, existing Paper-tag compatibility, and bounded bridge/UI routes.
- [x] User-provided manual verification covers canonical registry changes, alias/deprecation visibility, candidate review states, explicit apply/no-auto-apply, stale conflict recovery, unsaved Reader draft preservation, regressions, and the complete end-to-end workflow.
- [ ] Separately verify private-safe browser Network responses for governance and candidate-review routes.
- [ ] v1.5.10 PR-head CI, merge to `main`, v1.5.10 tag, GitHub Release, post-merge `main` CI, and clean-PC restore remain open until separately observed.
- [ ] v1.6.0 owns the Reader Workspace UX Overhaul. Automatic apply/cleanup, bulk retagging, embeddings/LLM tagging, ontology/graph work, and v1.8.0 Tag Intelligence remain excluded.

## Historical v1.5.9-pdf-scan-import-frontend

- [x] Runtime, package/lockfile, README, local release manifest, release-note draft, and generated status identify v1.5.9 while the immutable released baseline remains v1.4.0.
- [x] `POST /papers/scan` is a preview-only recursive managed-directory scan. It returns safe relative candidates without creating or changing a Paper record or triggering enrichment/tags.
- [x] `POST /papers/import` accepts only selected safe relative `.pdf` paths, revalidates them under the shared workspace lock, and uses the established atomic index merge for selected new records only.
- [x] New, already-registered, invalid, unavailable, and disappeared-file outcomes are actionable and per-file; repeated scan/import does not create a duplicate Paper according to existing canonical path/registry handling.
- [x] Imported Papers appear through existing Paper/read models, open through the Reader/PDF API, and retain the explicit v1.5.8 metadata-enrichment follow-up rather than automatic provider calls or tags.
- [x] Disposable backend/frontend tests cover preview non-mutation, non-PDF rejection, registration, partial selection/failure, duplicate safety, Reader/PDF compatibility, reload, metadata follow-up, bridge method/path limits, candidate rendering, selection, and error state sources.
- [x] User-provided v1.5.9 manual verification covers real-library scan preview non-mutation, selected and partial import, duplicate/new/invalid distinctions, filename compatibility, failure safety, collection/Reader visibility, reload/restart persistence, metadata-enrichment follow-up, and existing Reader/Project/Tag workflow compatibility.
- [x] User-provided v1.5.11 manual validation verified private-safe browser Network responses for scan/import workflow coverage.
- [ ] v1.5.9 PR-head CI, merge to `main`, v1.5.9 tag, GitHub Release, post-merge `main` CI, and clean-PC restore remain open until separately observed.
- [ ] Drag/drop, watcher, OCR, full-text extraction, automatic enrichment/tags, semantic/content-hash deduplication redesign, moved-file repair, cleanup, migration, backup redesign, citation workflow, and free-form folder management remain excluded.

## v1.5.8-metadata-enrichment-frontend

- [x] Runtime, package/lockfile, README, local release manifest, release-note draft, and generated status identify v1.5.8 while the immutable released baseline remains v1.4.0.
- [x] `POST /papers/{paper_id}/metadata/enrichment-preview` is a separate non-persistent, Paper-scoped preview over the existing PDF DOI, Crossref, arXiv, and local fallback capabilities; it neither scans the library nor writes Paper state.
- [x] The Reader compares current saved and candidate values for all editable metadata fields and visibly distinguishes source/provenance, unchanged values, conflicts, available candidates, and unavailable candidate fields.
- [x] Apply is disabled without selected fields and sends only selected nonblank candidates through the existing revision-checked, lock-protected, atomic metadata command; missing values never clear stored metadata.
- [x] Unselected/manual metadata, dirty metadata fields, and unsaved Reading Note drafts remain intact through preview, partial apply, provider failure, and stale-revision conflict; conflict recovery requires a deliberate reload/retry.
- [x] Disposable backend/frontend tests cover non-persistent preview, candidate comparison/provenance, partial and repeated apply, missing values, provider fallback/failure, stale revisions, reload, bridge allowlisting, and draft preservation while existing metadata writes remain compatible.
- [x] User-provided v1.5.8 manual verification is recorded in the canonical manifest and generated Current Release Status, covering preview non-mutation, comparison/provenance, selective apply/persistence, provider safety, draft preservation, stale conflict, reload, and Reader/Project/Tag smoke behavior.
- [ ] v1.5.8 PR-head CI, merge to `main`, v1.5.8 tag, GitHub Release, post-merge `main` CI, and clean-PC restore remain open until separately observed.
- [ ] Automatic/background or bulk enrichment, full-text extraction/OCR, automatic overwrite, tag generation/governance, citation export, backup/recovery redesign, and Reader UX redesign remain separately scoped; v1.5.9 later delivered only bounded manual managed-directory scan/import.

## v1.5.7-paper-tag-apply-remove

- [x] Runtime, package/lockfile, README, local release manifest, release-note draft, and generated status identify v1.5.7 while the immutable released baseline remains v1.4.0.
- [x] Paper tag add/remove commands use stable Paper identity, a tag-only revision, shared workspace locking, reload-after-lock checks, atomic index persistence, verification, and rollback.
- [x] Existing normalization applies only to the intended added/removal tag identity; legacy/noncanonical unrelated stored tags remain intact.
- [x] Successful mutations refresh the canonical Reading Note header while keeping its body exact and retaining unsaved Reader note drafts.
- [x] The Reader shows current tags, explicit add/remove controls, saving/no-op/conflict/error states, retry/reload behavior, and canonical Tag Book choices when available.
- [x] Disposable backend/frontend regressions cover persistence, duplicate/absent no-ops, stale revisions, read parity, draft preservation, rollback, API privacy, bridge allowlisting, and existing Reader/Library/Project/Tag/PDF behavior.
- [ ] User-performed browser and real-data validation, hosted CI, merge to `main`, v1.5.7 tag, GitHub Release, and post-merge `main` CI remain open until separately observed.
- [ ] Canonical Tag CRUD, alias governance, automatic/bulk tagging, drag and drop, metadata-editor tag fields, and design-system work remain excluded.

## v1.5.6-project-workspace-closure

- [x] Project Detail keeps explicit metadata/status/priority editing, Paper-link management, and existing Note Block-link management together without a second storage path.
- [x] The Project-local Note Block picker is bounded by existing Papers and the selected Paper's stored blocks; it uses the existing read and typed link-command contracts.
- [x] Typed Paper and Note Block counts flow from the Project read model through the API/schema/frontend types; controlled orphan and unavailable states remain visible and non-destructive.
- [x] Project metadata drafts and link commands remain independent; dirty drafts block link controls, archived Projects remain read-only, and link commands keep their separate revision checks.
- [x] Disposable regression coverage includes metadata/list/detail persistence, both link types, canonical Note Block link visibility, duplicate no-ops, conflicts, archived controls, and target-state preservation.
- [ ] User-performed browser validation of the Project-local Note Block picker and cross-surface persistence remains separate and is not claimed here.
- [ ] Hosted CI, merge to `main`, v1.5.6 tag, GitHub Release, and post-merge `main` CI remain open until separately observed.
- [ ] Drag-and-drop, PDF selection/highlighting, Note Block delete/reorder, automatic generation, autosave, Tag changes, graph/citation/backup work, design-system overhaul, Streamlit removal, database/cloud sync, Project delete, and unarchive remain excluded.

## v1.5.5-note-block-write-project-links

- [x] Runtime, package/lockfile, README, manifest, release-note draft, and generated status identify v1.5.5 while the immutable released baseline remains v1.4.0.
- [x] The stored-order Note Block collection exposes only canonical content, server-owned identity/timestamps, source Paper identity, total, safe Project links, and a deterministic complete-state revision.
- [x] Create/update form an independent command boundary with strict fields and bounds, explicit save, no-op detection, stale-revision zero mutation, shared locking, reload-after-lock, atomic verification, and rollback.
- [x] Note Block Project-link add/unlink validates exact Project/Paper/block identities, archived state, allowed link type, duplicate truthfulness, stale link revision, and store isolation.
- [x] Project Detail distinguishes available, missing-block, missing-Paper, and unavailable targets and never auto-deletes or repairs an orphan link.
- [x] Reader Metadata, Reading Note, and Note Block drafts remain independent; conflict/offline states preserve drafts and selections; Paper transitions isolate Note Block state.
- [x] The frontend uses explicit create/edit/save/cancel/reload/link/unlink actions, bounded Project selection, unlink confirmation, stable Reader navigation, and archived Project control absence.
- [x] API, bridge, and TypeScript contracts admit only exact methods/paths and JSON commands; encoded paths, unlisted subpaths, arbitrary dictionaries, and private error details remain excluded.
- [x] Disposable focused/full Python and frontend regressions cover strictness, concurrency, rollback, privacy, target states, navigation, draft preservation, and unchanged Reader/PDF/Project/Paper-link behavior.
- [x] User-performed real-data v1.5.5 Note Block and Project-link runtime checks were recorded as VERIFIED on 2026-08-02.
- [ ] Hosted CI, merge to `main`, v1.5.5 tag, GitHub Release, and post-merge `main` CI remain open until separately observed.
- [ ] Note Block delete/reorder, drag-and-drop, PDF selection/highlight, automatic block creation, autosave, combined save, and broader writes remain excluded.

## v1.5.4-project-write-paper-links

- [x] Runtime, package/lockfile, visible shell, README, manifest, and release-note draft identify v1.5.4 while the immutable released baseline remains v1.4.0.
- [x] Project create/update/archive and Paper-link add/remove delegate through one strict command-service boundary.
- [x] Metadata is bounded and allowlisted; archive is one-way; server identity/timestamps are protected; Project deletion and unarchive are absent.
- [x] Existing-Paper link commands fix `target_type` to `paper`, validate Project/Paper identities, return honest duplicate results, and exclude Note Block targets.
- [x] Separate Project/link revisions, shared lock acquisition, reload-after-lock conflict checks, atomic replacement, verification, and exact-byte rollback are covered.
- [x] The API and bridge admit only the five exact command method/path pairs with controlled private-safe errors.
- [x] The frontend uses explicit create/edit/save/cancel/archive/add/remove actions, preserves drafts/selections on failure, confirms archive/unlink, and hides write controls for archived Projects.
- [x] Disposable backend/frontend tests cover strictness, stale/no-op behavior, lock contention, rollback injection, store isolation, privacy, bridge allowlisting, and regressions.
- [x] R130 and R131 are complete; the specified local R133/G4 Project runtime parity evidence is recorded; R132 proceeds in v1.5.5; broader v1.6 expansion remains deferred.
- [x] User-performed real-data web/Streamlit parity, persistence, conflict recovery, offline/restart recovery, archived read behavior, and private-safe Network responses were recorded on 2026-08-02.
- [ ] v1.5.4 PR, hosted CI, merge, tag, GitHub Release, and post-merge evidence remain open until separately observed.

## v1.5.3-settings-health-read-parity

- [x] Runtime, package/lockfile, visible shell, README, manifest, and release-note draft identify v1.5.3 while the immutable released baseline remains v1.4.0.
- [x] `GET /settings/summary` uses a dedicated lightweight read model plus strict adapter/schema/dependency/route boundaries.
- [x] Application, Workspace, Data integrity, and Backup readiness expose only canonical or aggregate safe values.
- [x] File discovery, index rows, per-file JSON reads, and total JSON bytes per request are capped; Settings performs no PDF hashing/parsing, extraction, archive verification, repair, backup, restore, cache rebuild, or write.
- [x] Component failures remain section-level warnings/unavailable states; verified zeroes remain distinct from unavailable null counts.
- [x] The Settings page uses the established shell and shared loading, empty, offline, controlled error, partial warning, and retry behavior.
- [x] The bridge admits only exact GET `/settings/summary`; no Settings/action/write route or control was added.
- [x] Disposable tests cover real aggregates, corruption, privacy, determinism, backup presence/absence, no-heavy-binary reads, and byte/mtime non-mutation.
- [x] R-112, R-113, and G2 frontend read-parity implementation are complete; actual release evidence remains separately tracked.
- [ ] Manually confirm real Application/Workspace/integrity/backup values, offline retry, private-detail-free Network response, and browsing non-mutation.
- [ ] v1.5.3 PR, hosted CI, merge, tag, GitHub Release, and post-merge evidence remain open until separately observed.

## v1.5.2-projects-tags-read-parity

- [x] Runtime, package/lockfile, visible shell, README, manifest, and release-note draft identify v1.5.2 while the immutable released baseline remains v1.4.0.
- [x] Projects and Tags GET routes use strict response schemas, service/read-model builders, adapters, deterministic ordering, and bounded pagination.
- [x] Project detail returns allowlisted stored links and paper summaries, explicit orphan states, generic 404/422/503 behavior, and no storage paths or arbitrary dictionaries.
- [x] Tag listing returns canonical key, label, category, aliases, status, and real strength only; primary, empty, legacy fallback, and corrupt configuration are controlled.
- [x] Candidate summary derives fixed counts from existing deterministic data or returns an explicit unavailable state.
- [x] Projects, Project Detail, and Tags use real API data plus loading, empty, offline, read-model error, not-found where applicable, and explicit GET retry.
- [x] The bridge admits every new exact GET path and no Project/Tag write path; Reader commands and PDF Range behavior remain unchanged.
- [x] Disposable tests confirm Project and Tag GETs do not modify Projects, links, Tag Book files, or candidate sources.
- [x] R-110 and R-111 are implementation-complete; R-113 is partial for Projects/Tags; R-112 is unchanged; G2 remains open.
- [ ] Manually confirm real Projects list, Project detail, linked-paper state, canonical Tags, aliases/category/status, empty/offline behavior, and no browsing mutation.
- [ ] v1.5.2 PR, hosted CI, merge, tag, GitHub Release, and post-merge evidence remain open until separately observed.

## v1.5.1-reader-write-vertical-slice

- [x] Runtime, package/lockfile, visible shell, README, manifest, and release notes identify v1.5.1 while the immutable released baseline remains v1.4.0.
- [x] Metadata PATCH and Reading Note PUT remain separate and delegate through a command service.
- [x] Metadata allowlists exactly seven fields, normalizes through existing domain logic, bounds values, and rejects unknown or malformed fields.
- [x] Metadata revisions use stable normalized serialization; note commands use exact UTF-8 SHA-256, with an explicit absent-note baseline.
- [x] Stale commands return generic 409 responses and perform zero mutation.
- [x] Coupled index/header failures restore original persistent state; note saves retain atomic replacement and prior-file-on-failure behavior.
- [x] The bridge admits only the exact two command method/path pairs, forwards JSON correctly, and keeps Range PDF-only.
- [x] Metadata and note editors have separate explicit saves and Clean, Dirty, Saving, Saved, Conflict, and Error states.
- [x] Dirty drafts survive conflicts, failures, metadata header refresh, and PDF failures; intentional replacement requires explicit action.
- [x] PDF document identity is not changed by either save flow, and v1.5.0 GET/PDF/Range plus Streamlit regressions remain covered.
- [x] Persisted note, metadata, and the correct managed PDF are manually confirmed together.
- [x] A newly synchronized paper without a persisted note opens with a clean empty editor and no stale prior-paper state.
- [ ] Unreadable-note warning is manually confirmed.
- [ ] Missing-PDF behavior is manually confirmed.
- [x] Unsaved-change cancellation and deliberate transition between papers are manually confirmed without stale editor content.
- [x] API restart followed by Reader reload recovery is manually confirmed.
- [x] All seven supported metadata fields save and survive reload; title, authors, year, and DOI refresh the canonical note header without damaging its body.
- [x] Reading Note edits save, survive browser reload, and appear in Streamlit.
- [x] Stale Reading Note and metadata writes from a second tab conflict without newer-result or draft loss and support explicit reload, re-edit, and save.
- [x] Metadata and Reading Note changes are manually visible in all four Streamlit/web directions.
- [x] Explicit browser refresh discards unsaved drafts under the accepted no-autosave and no-browser-local-draft-persistence policy.
- [ ] v1.5.1 PR, hosted CI, merge, tag, GitHub Release, and post-merge evidence remain open until separately observed.

## v1.5.0-reader-snapshot-readonly-vertical-slice

- [x] Runtime, frontend package/lockfile, README, canonical manifest, and release-note surfaces identify the v1.5.0 runtime target while the immutable released baseline remains v1.4.0.
- [x] `GET /papers/{paper_id}/reader` calls the existing snapshot builder once and returns strict allowlisted paper, note, baseline, warning, and PDF-state fields.
- [x] Exact persisted-note whitespace and line endings survive API adaptation; API code performs no note reread or hash recomputation.
- [x] Unknown paper and builder failure use generic 404/503 responses; absent note, unreadable note, and missing PDF remain successful snapshot states.
- [x] The same-origin bridge admits only the exact Reader GET route, excludes subpaths and write methods, and never forwards Range to JSON.
- [x] The web Reader uses one snapshot request, keeps stale paper data out during transitions, and presents selectable plain text without raw HTML insertion.
- [x] The PDF.js component, worker lifecycle, same-origin PDF URL, byte Range semantics, and managed-root containment remain unchanged.
- [x] Before the compatibility correction, the native fallback displayed the same managed PDF successfully.
- [x] Browser inspection confirmed HTTP 206, `application/pdf`, correct `Content-Range`/`Accept-Ranges`, `%PDF` starting bytes, and matching file size through the API and bridge.
- [x] The legacy PDF.js main/worker build rendered the real PDF first page successfully in Chrome 131 with Vinext dev.
- [x] Reader diagnostics showed Document loads 1, Page renders 1, and Render cancellations 0.
- [x] No write API, editor, autosave, metadata mutation, storage migration, dependency, project/tag API, OCR, or cloud behavior is added.
- [ ] User-performed runtime validation still covers unreadable-note and missing-PDF states; persisted-note pairing, note absence, paper transition, and API restart now have v1.5.1 runtime evidence.
- [ ] v1.5.0 PR, hosted CI, tag, GitHub Release, and post-merge evidence remain open until separately observed.

## v1.4.3-release-state-truth-repair

- [x] Reader aggregate status is derived from VERIFIED and NOT VERIFIED child states.
- [x] Streamlit regression accepts controlled states and requires completion evidence when VERIFIED.
- [x] Status/evidence contradiction checks are limited to canonical release-state evidence summaries.
- [x] PR number, current repository HEAD, workflow result, and exact test counts are not validator constants.
- [x] PR #6's frontend success and Python smoke failure are represented truthfully.
- [x] Remaining open evidence is limited to post-merge `main` CI, GitHub Release publication, and genuine clean-PC restore.
- [x] No product feature, API contract, storage format, dependency, or PDF Reader behavior changes.

## v1.4.2-post-merge-evidence-and-reader-runtime-closure

- [x] The immutable v1.4.0 product baseline commit and tag are independent from later control-plane changes.
- [x] Completed PR #5 merge and PR-head CI evidence are structurally independent from mutable repository HEAD and unverified post-merge `main` CI.
- [x] Repository HEAD is nullable, observational, and never required to equal the commit containing the manifest.
- [x] Tag existence and GitHub Release publication remain independent evidence fields.
- [x] Current smoke evidence is distinct from preserved historical conflicting v1.4.0 records.
- [x] Generated status and tracker export have deterministic, stale-output, status-control, and privacy regressions.
- [x] Reader and separate Streamlit manual evidence was supplied with PR #6 and is represented by the v1.4.3 canonical repair.
- [ ] A genuine clean-PC restore remains open until user-performed evidence is supplied.

## v1.4.0-pdfjs-reader-foundation

- [x] Runtime, frontend package, lockfile, visible shell labels, README, tracker, and release-note version surfaces identify v1.4.0.
- [x] The primary web Reader renders through PDF.js into one canvas and never accepts a path or arbitrary URL.
- [x] `pdfjs-dist` is pinned and `pdf.worker.min.mjs?url` emits a production asset with no CDN or server-side browser import.
- [x] Previous, next, bounded direct page entry, zoom in/out/reset, loading, error, retry, and accessible states are implemented.
- [x] The one-byte probe is removed and one authoritative PDF.js load is used per paper load cycle.
- [x] The native `<object>` fallback is conditional, labeled, uses the safe same-origin URL, and is not mounted with PDF.js.
- [x] Loading tasks, documents, page/render tasks, canvas state, retries, paper changes, and unmounts have explicit cleanup contracts.
- [x] Full and partial response, exact-length, `Accept-Ranges`, `Content-Range`, malformed/unsatisfiable Range, missing-file, traversal, and GET-only regressions are covered.
- [x] Development diagnostics are disabled by default and expose only bounded counts, durations, cancellation, and inferred request mode.
- [x] Automated and manual evidence is structured in `docs/tracker_sync_status.json`; conflicting evidence remains explicit.
- [x] The generated status document separates passed and pending Reader checks and keeps Streamlit regression independent.

## Operational approval policy

Commit, push, merge, tag, GitHub Release publication, and external-tracker application are separately authorized procedures. Their instructions are not release-state evidence and cannot close a gate.

## v1.3.1-release-state-convergence-and-repo-hygiene

- [x] Runtime, frontend package, lockfile, README, tracker, and release-note version surfaces identify v1.3.1.
- [x] The tracked root file `tatus --short` is deleted; no ignored runtime/user-data directory is inspected or changed.
- [x] `scripts/check_repo_hygiene.py` reads tracked entry names through Git and rejects the known artifact, root logs/output, shell-fragment filenames, generated evidence, dependencies, and private runtime/user-data paths with narrow rules.
- [x] Repository hygiene runs inside `scripts/smoke_check.py`, which is executed by the normal local gate and GitHub Actions Python job.
- [x] Release-state tests conditionally accept VERIFIED and NOT VERIFIED CI states only when evidence fields and the corresponding open gate agree.
- [x] Clean-PC restore, tag creation, and GitHub release publication remain independently validated and are not closed by CI success.
- [x] PR #2 commit, push, pull request, merge, and hosted run `29641757582` are recorded as completed/verified.
- [x] The separate post-merge `main` run `29641792069` is recorded as verified against merge SHA `9663c8cd052a2fa106382630afff7dcd9cfda421`.
- [x] The separate user-performed Streamlit regression remains recorded as VERIFIED.
- [x] External tracker tasks `R-001` through `R-025` use only controlled status values and repository-grounded evidence.
- [x] `scripts/export_tracker_status.py` uses only the Python standard library and emits deterministic UTF-8 CSV with the required five columns.
- [x] Record focused tests 40 passed, standalone hygiene/export passed, smoke 94/0/0, full pytest 524 passed, `npm ci` passed, lint passed, production build plus 14 Node tests passed, and final `git diff --check`/`git status --short` in the v1.3.1 release notes.
- [ ] A user performs the clean-PC restore rehearsal on a genuinely clean machine.
- [ ] A v1.3.x tag is created only after explicit instruction.
- [ ] A v1.3.x GitHub release is published only after explicit instruction.

## v1.3.0-reader-pdf-readonly-vertical-slice

- [x] `GET /papers/{paper_id}/pdf` resolves only an indexed paper and never accepts a filesystem path from the request.
- [x] PDF resolution remains inside the canonical managed papers directory and rejects missing, non-file, non-PDF, escaped, or otherwise unsafe paths without exposing an absolute path.
- [x] PDF delivery is GET-only, streamed as `application/pdf`, presented inline, and supports browser byte ranges through the response implementation.
- [x] The same-origin bridge allowlists only the exact PDF route, forwards Range, streams binary bytes, and preserves only safe PDF response headers.
- [x] Paper Detail exposes an Open Reader action based on stable `paper_id`, with an unavailable state when no managed PDF reference exists.
- [x] `/papers/{paper_id}/reader` provides title/citation context, back navigation, native PDF display, explicit loading/missing/offline/error states, and no write controls.
- [x] Notes and all write, metadata, PDF-maintenance, and recovery workflows remain in Streamlit.
- [x] Focused disposable-fixture API and frontend tests pass.
- [x] Current v1.3.0 smoke 90/0/0, final full pytest 496 passed, deterministic frontend setup, lint, build, 14 Node tests, and full release gate are recorded.
- [x] Disposable read-only API/frontend browser validation and API-offline recovery are recorded without private library metadata.
- [x] User-performed local-only FastAPI/frontend launch and listener validation passed with the expected v1.3.0 runtime diagnostics and no external listener.
- [x] User-performed real-library Papers, Paper Detail, Open Reader, correct managed PDF, title/citation, stable-identity URL, Back navigation, and no-write-control validation passed without retaining private metadata.
- [x] User-performed same-origin PDF bridge validation passed for HTTP 206, an exact 16-byte range body, safe representation headers, invalid-path rejection, and no filesystem-path exposure.
- [x] User-performed unknown-paper, FastAPI-offline navigation, restart recovery, and Reader/PDF recovery validation passed.
- [x] A separate user-performed Streamlit regression passed for Dashboard, Library, Paper Detail, Reader Workspace, existing PDF viewing, and existing note visibility without an application exception or mutation action.
- [x] Temporary frontend, FastAPI, and Streamlit processes were stopped; ports 3000, 8000, and 8501 were clear after validation.
- [x] Commit `1d51f37971e5898d2f531e9812510c150a4ab56b` was created and pushed on the feature branch; PR #2 was created and merged into `main`.
- [x] PR #2 GitHub Actions run `29641757582` concluded successfully with successful Python and frontend jobs.
- [x] Post-merge `main` GitHub Actions run `29641792069` concluded successfully for merge commit `9663c8cd052a2fa106382630afff7dcd9cfda421`, with successful Python and frontend jobs.
- [ ] A user performs the clean-PC restore rehearsal on a clean machine.
- [ ] A v1.3.x tag is created only after explicit instruction; none is currently approved or created.
- [ ] A v1.3.x GitHub release is published only after explicit instruction; none is currently approved or published.

## v1.2.2-runtime-and-release-evidence-closure

- [x] Implementation uses Vinext's supported `--hostname 127.0.0.1` argument and keeps the frontend local-only.
- [x] The launcher prints the configured bind address, port, canonical browser URL `http://127.0.0.1:3000`, Node version, npm version, Node source, and a post-launch probe.
- [x] `push` and `pull_request` remain in the primary workflow, and `workflow_dispatch` is defined locally for deliberate execution after the workflow is committed and pushed.
- [x] Python and frontend remain separate jobs requiring smoke, pytest, `npm ci`, lint, and frontend build/tests.
- [x] v1.2.1 historical evidence uses one controlled status per verification item.
- [x] Numeric version surfaces, current release name, release-note index, roadmap/backlog, and tracker handoff identify v1.2.2.
- [x] Focused launcher and release-contract tests pass and are recorded in v1.2.2 release notes.
- [x] Canonical `npm ci` frontend setup and the full `dev_check.ps1 -WriteEvidence` gate pass.
- [x] Independent smoke, full pytest, frontend lint, and frontend build/Node-test results are recorded with actual v1.2.2 counts.
- [x] FastAPI listener, direct requests, canonical frontend launcher/listener, and bridge/query behavior are manually checked.
- [x] Dashboard, Library, and Papers are visibly checked in a browser.
- [x] One existing Paper Detail route is visibly checked in the v1.2.2 read-only shell without retaining private paper metadata.
- [x] FastAPI-offline unavailable states and sidebar navigation are visibly checked in a browser.
- [x] Separate Streamlit launch/basic regression is performed without mutating library data.
- [x] GitHub Actions run `29639358889` for commit `5710dfaf2ec8e9a0212bc68d74f11ce573d87fe1` concluded successfully with successful Python and frontend jobs.
- [ ] A user performs the clean-PC restore rehearsal on a clean machine.
- [x] Commit `e26ee8c` was created by the user.
- [x] The feature branch was pushed to origin by the user.
- [x] Pull Request #1 was created.
- [x] PR #1 was merged and the v1.2.2 tag exists in repository history.
- [ ] GitHub release publication is not asserted without separate evidence.

## v1.2.1-full-stack-validation-gate

- [x] The implemented baseline is reconciled: v1.0.26 Streamlit/read contracts, v1.1.0-v1.1.2 read-only FastAPI routes, and the v1.2.0 frontend shell are current architecture.
- [x] Shared Node resolution prefers `-NodeHome`, then `BLUEPRINT_NODE_HOME`, then `PATH`, and enforces Node 22.13.0 plus both required executables.
- [x] Frontend dependency setup requires `package-lock.json` and runs `npm ci`; Python-only setup remains usable.
- [x] Default `dev_check.ps1` includes smoke, full pytest, frontend lint, and frontend test/build without duplicate builds.
- [x] `-PythonOnly` and `-SmokeOnly` are prominent partial, non-release-qualified modes.
- [x] `-WriteEvidence` is opt-in, ignored, machine-readable, and excludes command output and private paths.
- [x] Bridge tests cover exact allowlisting, query forwarding, upstream 404, generic 503 mapping, network failure, and absence of write methods.
- [x] GitHub Actions has independent Python 3.12 and Node 22.13.1 jobs with lock-file caching and `npm ci`.
- [x] Exact local smoke, pytest, frontend lint, frontend build/test, diff, and status results are recorded in v1.2.1 release notes.
- [ ] Manual API/frontend/Streamlit launch checks are recorded only if actually performed.
- [ ] Commit, push, merge, tag, and release occur only after explicit instruction.

## v1.0.26-streamlit-finalization-api-contract-freeze

- [x] Clean v1.0.25 baseline recorded: smoke 49 passed/0 warnings/0 failed; pytest 396 passed.
- [x] Reader manual/suggested tags use the shared metadata coordinator and converge with Reading Note headers.
- [x] Dirty drafts remain unsaved, paper-scoped, and dirty through metadata refresh; explicit Save converges header and body.
- [x] Edit metadata, DOI, DOI-less, selected tags, and Crossref acceptance use the shared coordinator.
- [x] Five JSON-safe, non-mutating read contracts are frozen without API routes.
- [x] Snapshot/disposable-target readiness validation is read-only and rejects unsafe or non-empty targets.
- [x] Prior v1.0.24 Reader and v1.0.25 lifecycle manual completion is recorded from the user's report.
- [x] Focused architecture validation passed 145; focused Reader Save/navigation validation passed 64; final smoke passed 53/0/0; pytest passed 417; serialization and repository-data audit passed.
- [x] User reported focused v1.0.26 manual validation Sections A-H passed; Save convergence and paper-navigation discard are accepted; G4 is closed.
- [ ] Commit, push, merge, tag, and release occur only after explicit instruction.

## v1.0.25-lifecycle-and-recovery-closure

- [x] Required v1.0.24 checkpoint, branch, clean tree, version, and documents verified.
- [x] Baseline recorded: smoke 48 passed/0 warnings/0 failed; pytest 377 passed.
- [x] Lifecycle/recovery contract documents critical state, rebuildable cache, and application configuration policy.
- [x] Recovery copies preserve and verify bytes; quarantine/restore are contained, explicit, and non-overwriting.
- [x] Exact duplicate decisions are atomic, reversible, path/SHA-bound, and included in snapshots.
- [x] Archive is orthogonal metadata visibility and preserves PDFs, IDs, notes, blocks, links, cache, status, and priority.
- [x] Focused validation passed (85 tests); final smoke passed 49/0/0 and pytest passed 396.
- [x] User reported the v1.0.25 Streamlit lifecycle validation completed before v1.0.26 work.
- [x] User reported the v1.0.24 Reader validation completed before v1.0.26 work.
- [ ] Release tag or checkpoint commit occurs only after explicit instruction.

## v1.0.24-reader-validation-and-parity-closure

- [x] Clean v1.0.23 baseline recorded: smoke 46 passed/0 warnings/0 failed; pytest 374 passed.
- [x] Status and priority persist through one explicit Apply action; unchanged settings produce no write payload.
- [x] Safe redundant explicit reruns are removed and retained reruns are classified/documented.
- [x] Paper-scoped note state and renderer keys have focused automated coverage.
- [x] Reader frontend parity checklist covers Must preserve, May redesign, and Intentionally deferred behavior.
- [x] Final `dev_check.ps1` evidence is recorded in v1.0.24 release notes.
- [x] Codex disposable checks and not-performed browser checks are clearly separated.
- [x] User-reported Streamlit manual Reader smoke completion is recorded by the v1.0.26 request.
- [x] Git status confirms no runtime/user data, PDFs, notes, exports, caches, or secrets are included.
- [ ] Release tag or checkpoint commit occurs only after explicit instruction.

## v1.0.23-reader-state-machine-closure

- [x] Clean v1.0.22 baseline recorded: smoke 46 passed/0 warnings/0 failed; pytest 362 passed.
- [x] Reader note states, events, invariants, and transition precedence are documented.
- [x] Dirty Reload preserves the exact draft and offers Keep draft / Discard changes and reload.
- [x] Header refresh preserves the latest dirty body and does not mark later edits saved.
- [x] Whole-draft replacement precedes append, protects newer edits, and pending events are idempotent.
- [x] Paper-scoped state and non-note rerun preservation have automated coverage.
- [x] Final `dev_check.ps1` result is recorded in v1.0.23 release notes.
- [x] Streamlit manual smoke is performed or clearly recorded as not performed.
- [x] Git status confirms no runtime/user data, PDFs, notes, exports, caches, or secrets are included.
- [ ] Release tag is created and pushed only after explicit approval.

## v1.0.22-note-durability-and-validation-closure

- [x] Baseline `dev_check.ps1` recorded: smoke 46 passed/0 warnings/0 failed; pytest 356 passed.
- [x] Reading Note creation, save, and header refresh use shared same-directory atomic UTF-8 writes.
- [x] Replacement-failure tests prove old note bytes survive and temporary files are removed.
- [x] Existing-note creation remains non-overwriting, and Reader save baselines remain unchanged.
- [x] Read-only snapshot verification checks manifest policy, safe paths, presence, size, SHA-256, and counts using disposable ZIP fixtures.
- [x] Final `dev_check.ps1` result is recorded in v1.0.22 release notes.
- [x] Reader save/reload/pending-header-refresh manual smoke is completed and recorded, or clearly marked not performed.
- [x] Backup create plus read-only verifier smoke is completed and recorded.
- [x] Git status confirms no runtime/user data, PDFs, notes, exports, caches, or secrets are included.
- [ ] Release tag is created and pushed only after explicit approval.

## v1.0.21-reader-performance-polish

- [ ] Working tree is clean before release preparation begins.
- [ ] Confirm `.gitignore` still excludes runtime data: `data/`, `papers/`, `notes/`, `exports/`, `.venv/`, and caches.
- [ ] `python scripts\smoke_check.py` passes.
- [ ] `python -m pytest -q` passes.
- [ ] Repeated scan of unchanged indexed PDFs reuses stored hash metadata.
- [ ] Changed PDF size or modified time triggers a SHA-256 recompute.
- [ ] Reader note save, reload, skipped reload, and metadata header refresh feedback are smoke-tested.
- [ ] Metadata changes with an unsaved Reader draft do not overwrite draft body text.
- [ ] Duplicate and missing PDF repair remains explicit, deterministic, and confirmation-gated.
- [ ] Release notes include Reader UX changes, hash-performance changes, Streamlit feedback, validation commands, known limitations, and deferred items.
- [ ] Release tag is created and pushed only after explicit approval.

## v1.0.20-safety-release-foundation

- [ ] Working tree is clean before release preparation begins.
- [ ] Confirm `.gitignore` still excludes runtime data: `data/`, `papers/`, `notes/`, `exports/`, `.venv/`, and caches.
- [ ] `python scripts\smoke_check.py` passes.
- [ ] `python -m pytest -q` passes.
- [ ] Health Check surfaces corrupt JSON with path, issue, and recovery-safe next action in a disposable workspace.
- [ ] Health Check shows severity, meaning, and recommended next action for detected issue sections.
- [ ] Light Backup Snapshot manifest documents included files, excluded files, app version, checksums, counts, and cache exclusion policy.
- [ ] Full Backup Snapshot includes managed PDFs under `papers/` only after explicit confirmation.
- [ ] Backup snapshots exclude `.git`, `.venv`, `__pycache__`, package caches, secrets, logs, temporary files, and regenerable caches.
- [ ] Reader note editing, structured note blocks, and Reader PDF behavior are smoke-tested without UX changes.
- [ ] Release notes include changes, rationale, validation commands, manual smoke checklist, known limitations, and deferred items.
- [ ] Release tag is created and pushed only after explicit approval.

## v1.0.0-foundation

- [ ] Working tree is clean before release preparation begins.
- [ ] Dependencies install from a fresh virtual environment.
- [ ] `python -m pytest` passes.
- [ ] `python scripts/smoke_check.py` passes.
- [ ] `streamlit run app.py` launches.
- [ ] Dashboard opens.
- [ ] Library opens.
- [ ] Paper Detail opens.
- [ ] Reader Workspace opens.
- [ ] Settings opens.
- [ ] README version/status is updated.
- [ ] Release tag is created and pushed after explicit approval.
