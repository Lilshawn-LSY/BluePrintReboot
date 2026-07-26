# BluePrintReboot Roadmap

Stable roadmap last edited: 2026-07-26

Current release evidence is not duplicated here. See the generated [Current Release Status](CURRENT_RELEASE_STATUS.md), derived from the canonical machine-readable manifest. This roadmap records stable architecture, closed decision gates, and the next approved product direction rather than mutable repository observations.

BluePrintReboot is a local-first, single-user research workspace with an established Streamlit application, a read-only FastAPI layer, and a TypeScript frontend shell. These are implemented architecture, not future placeholders.

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

## Next product milestone: v1.5.0 read-only Reader Snapshot vertical slice

The next version should convert the existing `ReaderSnapshot` domain model into a complete read-only web workflow rather than adding another release-control-only patch.

### Planned product slice

- Add strict `GET /papers/{paper_id}/reader` adaptation for the existing `build_reader_snapshot` domain builder.
- Expose only persisted Reading Note content, canonical note-header values, PDF state, note baseline hash/size, safe warnings, and an unavailable reason.
- Extend the centralized TypeScript client and same-origin bridge allowlist for exactly this GET route.
- Update the web Reader to load one Reader Snapshot and present the managed PDF with persisted note context in a read-only companion panel.
- Distinguish unknown paper, missing PDF, absent note, unreadable note, degraded project-link context, API offline, retry, and paper-transition states without fabricating content.
- Preserve current PDF.js cancellation, Range delivery, managed-root containment, stable `paper_id`, local-only operation, and native fallback behavior.

### Exit gates

- No note-content or private absolute path leaks beyond the explicitly approved local read-only response.
- No write endpoint, editor, autosave, mutation coordinator, or user-data migration.
- Reader Snapshot domain, API schema, adapter, dependency, bridge, client, rendered-state, and failure-state tests pass.
- Existing PDF API, PDF.js lifecycle, Streamlit write workflows, smoke, full pytest, frontend lint/build, and Node tests remain green.
- Manual validation confirms PDF and saved-note context stay synchronized across paper changes, API restart, missing-note, and missing-PDF scenarios.

### Why this milestone is next

`ReaderSnapshot` and `build_reader_snapshot` already exist and are tested at the domain layer, but the FastAPI router currently exposes paper detail and PDF bytes only. The web Reader therefore renders PDF plus limited `PaperDetail` metadata while persisted Reading Note context remains inaccessible in the web surface. This slice closes that specific architecture gap with bounded read-only risk and creates visible user value before any write-command boundary is considered.

## Continuing constraints

No write API, autosave, automatic duplicate merge/deletion, automatic repair, database migration, OCR, LLM tagging, cloud sync, `paper_id` redesign, installer, background service, or destructive automated restore. Keep real user data out of tests and validation evidence. Projects, Tags, and Settings remain deferred until a separately approved read or command contract provides real data and behavior.
