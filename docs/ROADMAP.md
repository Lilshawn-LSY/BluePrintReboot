# BluePrintReboot Roadmap

Stable roadmap last edited: 2026-07-26

Current release evidence is not duplicated here. See the generated [Current Release Status](CURRENT_RELEASE_STATUS.md), derived from the canonical machine-readable manifest. This roadmap records stable architecture, closed decision gates, and the next approved product direction rather than mutable repository observations.

BluePrintReboot is a local-first, single-user research workspace with an established Streamlit application, a read-model FastAPI layer with two bounded Reader commands, and a TypeScript frontend shell. These are implemented architecture, not future placeholders.

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

## Current product milestone: v1.5.1 Reader write vertical slice

The v1.5.1 runtime target adds a deliberately narrow mutation boundary to the v1.5.0 Reader. It does not relabel the immutable v1.4.0 released baseline and does not claim a v1.5.1 tag, GitHub Release, pull request, merge, or hosted workflow result.

### Implemented product slice

- `PATCH /papers/{paper_id}/metadata` accepts only seven bibliographic fields and requires the deterministic revision derived from those normalized fields.
- `PUT /papers/{paper_id}/reading-note` accepts complete note text and requires the exact persisted SHA-256; absence is explicit through `exists: false` plus the empty-byte digest.
- Routes call a command service rather than CSV/Markdown storage. Coupled metadata/header persistence either completes or restores the original index and note.
- The same-origin bridge admits only the exact GET routes and the two exact method/path command pairs; Range is forwarded only for managed PDF GET.
- Metadata and note editors keep separate draft/save/conflict/error states. Header refresh retains a dirty note body and advances its baseline without reloading the PDF.
- PDF.js cancellation, Range delivery, managed-root containment, stable `paper_id`, local-only operation, native fallback behavior, and Streamlit writes remain unchanged.

### Remaining evidence gate

- User-performed validation verified correct Reader pairing, absent-note clean state, explicit save/reload behavior, canonical header refresh, two-tab conflicts, API restart recovery, transition handling, and four-direction Streamlit/web visibility.
- Explicit refresh discarding unsaved drafts, no autosave or browser-local draft persistence, and a clean empty editor for a new paper without a persisted note are accepted v1.5.1 behaviors.
- The unreadable persisted-note warning and missing managed-PDF scenarios remain NOT VERIFIED pending separate evidence.
- Pull request, hosted CI, merge, tag, GitHub Release, post-merge, and clean-PC restore evidence remain separate and unclaimed.

### Why this slice

The existing metadata coordinator, note-template refresh, note store, and atomic text replacement already supplied the storage primitives. The new command service composes those primitives behind concurrency and rollback boundaries without creating a general-purpose storage API.

## Continuing constraints

No autosave, combined save endpoint, arbitrary metadata fields, automatic duplicate merge/deletion, automatic repair, database migration, OCR, LLM tagging, cloud sync, `paper_id` redesign, installer, background service, or destructive automated restore. Keep real user data out of tests and validation evidence. Projects, Tags, and Settings remain deferred until a separately approved read or command contract provides real data and behavior.
