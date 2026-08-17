# BluePrintReboot Roadmap

Stable roadmap last edited: 2026-08-17

Current release evidence is not duplicated here. See the generated [Current Release Status](CURRENT_RELEASE_STATUS.md), derived from the canonical machine-readable manifest. This roadmap records stable architecture, closed decision gates, and the next approved product direction rather than mutable repository observations.

BluePrintReboot is a local-first, single-user research workspace with an established Streamlit application, a bounded FastAPI layer with two Reader state commands, one explicit full-text extraction command, two structured Note Block commands, seven Project/link commands, and a TypeScript frontend shell. These are implemented architecture, not future placeholders.

## Implemented architecture

- v1.0.26 finalized Streamlit Reader/lifecycle stability, routed metadata mutations through one coordinator, froze JSON-safe read models, and added non-destructive restore-readiness checks.
- v1.1.0-v1.1.2 established four GET-only FastAPI route shapes for health, library status, paper collection, and paper detail.
- v1.2.0 added the seven-route TypeScript shell and allowlisted same-origin bridge.
- v1.2.1 made Python/frontend validation one reproducible local gate with portable Node resolution, deterministic `npm ci`, bridge tests, evidence output, and separate workflow jobs.
- v1.2.2 corrected the local frontend bind contract, added manual workflow execution support, reconciled controlled release evidence, and added a canonical tracker handoff.
- v1.3.0 added the first safe read-only Reader/PDF vertical slice: a managed-file PDF endpoint, a streaming same-origin bridge, Paper Detail navigation, and a dedicated browser-native Reader route.
- v1.3.1 converged source-control, hosted-CI, manual-regression, restore, and publication state; removed the accidental tracked console-output artifact; added a tracked-entry hygiene gate; and made the external tracker handoff deterministic.
- v1.4.0 made PDF.js the primary web Reader, bundled its worker locally, added bounded navigation/zoom/error/fallback behavior, and instrumented document/render lifecycle without changing the secure PDF API or Streamlit writes.
- v1.4.2 made release evidence non-self-invalidating by separating the immutable product baseline, completed control-plane change evidence, and non-invariant repository observations.
- v1.4.3 made Reader aggregate state derive from its child evidence, permitted truthful Streamlit regression completion, rejected status/evidence contradictions, and removed mutable PR, workflow, HEAD, and exact-count assumptions from validator invariants without changing product behavior.
- v1.5.0 connected the existing `ReaderSnapshot` builder to a strict GET contract and a single-request web Reader that shows the managed PDF with selectable persisted-note context while preserving all write and PDF lifecycle boundaries.
- v1.5.1 adds separate metadata and Reading Note commands, optimistic concurrency, transactional metadata/header consistency, and independent web editors while preserving the v1.5.0 read/PDF/Streamlit contracts.
- v1.5.2 adds bounded Projects and Tags GET contracts, real Projects/Project Detail/Tags views, explicit orphan and candidate-availability states, and shared retry behavior without adding Project or Tag writes.
- v1.5.3 adds one bounded safe Settings summary, a real four-section Settings view, explicit zero-versus-unavailable diagnostics, and backup-evidence presence without adding Settings, health, backup, restore, or repair writes.
- v1.5.4 adds explicit Project create/update/archive and existing-Paper link/unlink commands with separate Project/link revisions, shared locking, atomic replacement, rollback verification, and draft-preserving frontend workflows.
- v1.5.5 adds structured Note Block collection reads, explicit create/update commands, typed Note Block–Project add/unlink commands, safe Project Detail target resolution, and independent Reader workflows without changing storage formats.
- v1.5.8 adds a separate Paper-scoped metadata candidate preview in the web Reader, source-labelled field comparison, and selective application through the existing metadata command without automatic overwrite or new storage.
- v1.5.9 adds bounded web Library scan/preview/selective-import commands for PDFs already in `papers/`, preserving scan/import separation, managed-relative path validation, stable Paper identities, per-file failures, Reader/PDF compatibility, and explicit post-import metadata enrichment.
- v1.5.10 combines the planned canonical-tag governance and candidate-review packages: the existing Tag Book gains revision-checked canonical create/edit/alias/deprecate commands; rulebook candidates gain persisted explicit review, promotion, and separate application through the existing Paper-tag command. Legacy Paper tag text remains untouched, and no candidate is automatically applied.
- v1.5.11 closes the Library/Paper workflow with bounded server-side metadata search/filter/pagination, Library metadata-enrichment reuse, coherent collection navigation, and explicit exact-content reconnect for missing managed PDFs without creating or merging Papers.

## Decision gates

| Gate | Current status | Evidence |
|---|---|---|
| v1.3.0 Reader/PDF implementation | Closed | Disposable endpoint and frontend tests cover containment, exact bytes, byte ranges, errors, binary streaming, Reader states, and the unchanged GET-only surface. |
| v1.3.0 local full-stack baseline | Closed | Smoke 90/0/0, pytest 496 passed, deterministic `npm ci`, lint passed, production build passed, and 14 Node tests passed on 2026-07-18. |
| v1.3.0 runtime and Reader validation | Closed | Local-only Reader/PDF, Range delivery, offline recovery, and cleanup checks passed without retaining private library metadata. |
| Separate Streamlit manual regression | Closed | User-performed Dashboard, Library, Paper Detail, Reader Workspace, existing PDF, and existing-note visibility checks passed without mutation. |
| PR #2 source control and hosted CI | Closed | PR #2 merged into `main`; its PR-head and post-merge Python/frontend workflows succeeded. |
| v1.3.1 repository hygiene and state contracts | Closed | Focused tests, tracked-entry hygiene, smoke, full pytest, deterministic export, frontend lint/build, and Node tests passed. |
| v1.4.0 PDF.js Reader foundation | Closed | PDF.js rendering, lifecycle cleanup, native fallback exclusivity, Range delivery, large-PDF behavior, API restart recovery, and real-PDF manual checks are complete. |
| v1.4.2 release-state closure | Closed | Schema 4.0 separates immutable release baseline, completed change evidence, mutable observations, publication, and recurring operational procedures. |
| v1.4.3 release-state truth repair | Closed | PR #7 merged into `main` at `b9a7fa9f550563b266a2b51a75f2472d21388dac`; PR-head GitHub Actions run `30192175145` completed successfully after local smoke 101/0/0, pytest 543, frontend lint/build, and 30 Node tests passed. |
| v1.5.0 Reader Snapshot implementation | Closed locally | Strict schema/adapter/route, exact bridge allowlist, typed client, plain-text companion, and synthetic failure-state regressions are implemented; hosted and user-performed runtime evidence remain separate. |
| v1.5.1 Reader write implementation | Closed locally | Two strict command routes, deterministic concurrency baselines, rollback coverage, exact bridge allowlisting, accessible editors, and disposable-fixture regressions are implemented; user-performed write/runtime evidence is partially verified while hosted evidence remains separate. |
| v1.5.2 Projects and Tags read parity | Closed locally | Strict list/detail/tag/summary schemas, service/adapters, deterministic pagination, orphan handling, exact bridge paths, real views, negative states, and read-only regressions are implemented; manual and hosted evidence remain separate. |
| v1.5.3 Settings and health safe read parity | Closed locally | A capped lightweight read model, strict adapter/schema, exact bridge path, real Settings view, partial states, privacy checks, and non-mutation regressions are implemented; manual and hosted evidence remain separate. |
| v1.5.4 Project write and Paper–Project links | Runtime parity closed | Five strict command routes and disposable regressions are implemented; the 2026-08-02 user-performed real-data runtime checks are VERIFIED. Hosted, merge, tag, and publication evidence remain separate. |
| v1.5.5 Note Block write and Project links | Runtime parity closed | Five exact read/command routes, complete-state revisions, lock/reload atomicity, failure rollback, typed orphan states, exact bridge paths, explicit UI actions, and disposable regressions are implemented; the 2026-08-02 user-performed runtime checks are VERIFIED. Hosted evidence remains separate. |

## Current product milestone: v1.5.12 R-145 Pre-UX PDF Foundation

v1.5.12 closes PDF rendering, selectable-text geometry, structured extraction, and OCR-routing foundations before the v1.6 visual/Reader UX redesign. It preserves the existing Reader controls, managed PDF Range bridge, flattened profile consumers, and v1.5.11 Library workflow.

### Implemented product slice

- PDF.js canvas output uses `clamp(devicePixelRatio × 1.5, 1, 3)` supersampling while viewport CSS dimensions, text-layer geometry, selection coordinates, and semantic Reader zoom remain unchanged.
- A PDF.js text layer shares the canvas viewport, rotation, page, and zoom lifecycle. Canvas and text work cancel and clean up together across navigation, retry, fallback, document change, and unmount.
- The internal selection contract uses canonical 1-based page numbers and top-left rectangles normalized to the rotated logical page viewport. It does not persist selections or create Note Blocks.
- Default pinned `pdf-inspector==0.2.6` is the preferred structured provider and remains isolated behind BluePrint dataclasses. The adapter explicitly converts its mixed 0-based and 1-based upstream page fields to BluePrint 1-based page numbers.
- Structured extraction records document classification/confidence, page count, per-page text/Markdown/positioned text, OCR-needed state/reasons, warnings/errors, provider version, and source revision. One deterministic page-ordered projection feeds existing flattened-text consumers; MarkItDown then pypdf remain compatible fallbacks.
- Cache metadata keeps SHA-256 stale detection and prior-valid-cache preservation while adding explicit extraction/cache states and reusable OCR-needed results.
- Three bounded FastAPI routes expose status, canonical cached content, and explicit extraction/re-extraction. The existing Reader adds a compact state/action/viewer section; it does not extract in the browser or schedule work automatically.

### Evidence state

- Disposable automated coverage is part of the local release gate. Previously reported normal-PDF rendering, zoom, selection/drag, and lifecycle observations remain recorded separately; supersampling-specific DPR, frontend Full Text, classification, stale-cache, scanned/mixed, and restart checks remain user-performed manual validation.
- Hosted CI, PR, merge, tag, GitHub Release, post-merge validation, and clean-PC restore evidence remain separately unverified.

## Historical product milestone: v1.5.11 Library / Paper Workflow Closure

v1.5.11 is the final Library/Paper workflow closure before the v1.6 UX redesign. It does not relabel the immutable v1.4.0 released baseline and does not claim hosted validation, merge, tag, or publication.

### Implemented product slice

- Library is the primary collection surface. Its server-backed query applies bounded case-insensitive normalized metadata search and exact tag/year/reading-status/lifecycle filters before pagination; `/papers/{paper_id}` and `/papers/{paper_id}/reader` remain stable resource URLs.
- The existing metadata enrichment preview and revision-protected selective metadata command are available from Library as well as Reader; no import-time or background enrichment is introduced.
- Exact-content reconnect is explicit and managed-root-contained. It rechecks a unique missing Paper/hash match under the workspace lock and only updates that existing row's file identity fields; notes, blocks, links, metadata, tags, and `paper_id` are preserved.

- The canonical registry exposes bounded create/edit/alias/deprecate operations through a Tag Book service. Canonical keys remain stable and changes require a Tag Book revision under the shared lock.
- Alias and label collisions are rejected using the existing normalization rules. Categories remain bounded metadata; a deprecated tag stays visible and is not physically deleted.
- Governance writes never rewrite Paper tag values. Historical canonical relationships and existing legacy/noncanonical values remain recoverable and inspectable.
- Candidate generation is a separate persisted review context over the existing rulebook/extracted-text data. It is non-mutating for Papers and carries only existing source/evidence/score/confidence information.
- Approval, rejection, and promotion are explicit review actions. Promotion resolves or creates a canonical registry entry without creating duplicate canonical/alias identities.
- Apply is a distinct final action that delegates to the v1.5.7 Paper-tag command with the Paper tag revision. It preserves no-op, conflict, lock, atomicity, rollback, and unsaved Reading Note draft boundaries.
- A deterministic three-fixture quality baseline records present/missing expected candidates and false positives without optimizing or claiming semantic quality.

### Evidence state

- Local service/API/frontend validation and user-provided v1.5.11 manual browser/runtime validation are recorded in the release manifest; hosted CI, merge, tag, GitHub Release, post-merge, and clean-PC restore remain separately unclaimed.
- Existing v1.5.4-v1.5.9 runtime evidence remains historical context and is not relabeled as v1.5.10 evidence.

### Roadmap item status

| Item | Status after v1.5.10 implementation |
|---|---|
| v1.5.10 canonical Tag Book governance | Complete locally with explicit revision, lock, collision, and deprecation safeguards. |
| v1.5.10 candidate review | Complete locally with persisted review state and separate final Paper apply. |
| v1.5.11 candidate review package | Absorbed into v1.5.10; no separate functional release remains. |
| v1.5.12 R-145 PDF foundation | Complete locally without a Reader visual redesign or Research Block persistence. |
| v1.6.0 Reader Workspace UX Overhaul | Follows the v1.5.12 foundation under a separately approved scope. |
| v1.8.0 Tag Intelligence | Deferred: semantic-quality optimization, embeddings, and LLM/provider work remain out of scope. |

### Historical v1.5.5 Note Block milestone

The former v1.5.5 current-milestone record remains historical context: it delivered the bounded stored-order Note Block collection, explicit create/update and Project-link commands, independent Reader drafts, typed orphan/unavailable states, shared-lock/revision/atomic persistence protections, and 2026-08-02 user-performed runtime evidence. Its broader Reader/shared UX follow-up remains the basis of the separately scoped v1.6.0 overhaul.

## Continuing constraints

No automatic candidate application, automatic tag cleanup, bulk retagging, destructive canonical-tag deletion, ontology editing, embedding/vector/LLM tagging, combined save endpoint, Note Block deletion/reorder/drag-and-drop, selection/highlight persistence or automatic block creation, Project deletion/unarchive, Settings write, configuration editing, automatic backup, automatic duplicate merge/deletion, automatic repair, database migration, OCR engine, cloud sync, `paper_id` redesign, installer, background service, or destructive automated restore. Keep real user data out of automated tests. The Reader workspace visual overhaul remains v1.6.0 work.
