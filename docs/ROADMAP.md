# BluePrintReboot Roadmap

Stable roadmap last edited: 2026-07-27

Current release evidence is not duplicated here. See the generated [Current Release Status](CURRENT_RELEASE_STATUS.md), derived from the canonical machine-readable manifest. This roadmap records stable architecture, closed decision gates, and the next approved product direction rather than mutable repository observations.

BluePrintReboot is a local-first, single-user research workspace with an established Streamlit application, a bounded FastAPI layer with two Reader commands and five Project/Paper-link commands, and a TypeScript frontend shell. These are implemented architecture, not future placeholders.

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
| v1.5.4 Project write and Paper–Project links | Closed locally | Five strict command routes, optimistic revisions, lock/reload atomicity, failure rollback, exact bridge paths, explicit UI actions, and disposable regressions are implemented; manual and hosted evidence remain separate. |

## Current product milestone: v1.5.4 Project write and Paper–Project link commands

The v1.5.4 runtime target adds the first web Project mutation slice without broadening into Project deletion, unarchive, Note Block commands, Tag governance, Settings writes, bulk workflows, or schema migration. It does not relabel the immutable v1.4.0 released baseline and does not claim v1.5.4 publication or hosted evidence.

### Implemented product slice

- `POST /projects`, `PATCH /projects/{project_id}`, and `POST /projects/{project_id}/archive` allow only bounded Project metadata and preserve server-owned identity/timestamps.
- `POST /projects/{project_id}/paper-links` and `DELETE /projects/{project_id}/paper-links/{link_id}` act only on existing Paper targets and never create, update, archive, or delete a Paper.
- `project_revision` and `links_revision` are deterministic complete-state tokens. Commands acquire the shared lock, reload state, reject stale requests before writing, atomically replace only the owning store, reload/verify, and restore original bytes and timestamps after injected failure.
- The frontend exposes only explicit create/edit/save/cancel/archive/add/remove actions. Conflicts and offline failures preserve drafts or selections; duplicate exact links return an unchanged result; archived Projects remain readable with write controls absent.
- Reader, PDF Range, Tags, Settings, Streamlit storage formats, stable identities, local-only operation, and dependency versions remain unchanged.

### Remaining evidence gate

- User-performed real-data parity checks for create/edit/archive, add/remove Paper links, reload persistence, cross-surface visibility, conflict recovery, API-offline recovery, archived read behavior, and private-safe Network responses remain NOT VERIFIED.
- The unreadable persisted-note warning and missing managed-PDF Reader scenarios remain NOT VERIFIED pending separate evidence.
- Pull request, hosted CI, merge, tag, GitHub Release, post-merge, and clean-PC restore evidence remain separate and unclaimed.

### Roadmap item status

| Item | Status after v1.5.4 implementation |
|---|---|
| R130 Project command service and API | Complete. |
| R131 web Project metadata and Paper-link workflows | Complete. |
| R132 Note Block read/write/link commands | Deferred. |
| R133 cross-surface Project command evidence | Partially complete: automated disposable coverage is complete; real runtime parity evidence remains open. |
| G4 Project write parity | Open pending the required manual and hosted evidence. |
| v1.6 broader write expansion | Deferred until G4 evidence closes and scope is separately approved. |

## Continuing constraints

No autosave, combined save endpoint, Project deletion/unarchive, Note Block write/link command, Tag governance/write, Settings write, configuration editing, automatic backup, automatic duplicate merge/deletion, automatic repair, database migration, OCR, LLM tagging, cloud sync, `paper_id` redesign, installer, background service, or destructive automated restore. Keep real user data out of tests and validation evidence. Broader UI polish and v1.6 scope remain deferred.
