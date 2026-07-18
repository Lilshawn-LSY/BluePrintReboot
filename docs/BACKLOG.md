# BluePrintReboot Backlog

Last synced: 2026-07-18

## Implemented foundations

- [x] v1.0.26 Streamlit finalization, frozen read models, lifecycle safety, and restore-readiness boundary.
- [x] v1.1.0-v1.1.2 four-route GET-only FastAPI foundation and rich paper metadata.
- [x] v1.2.0 desktop TypeScript shell, typed client, and same-origin read-only bridge.
- [x] v1.2.1 portable-Node-aware full local validation gate and separate Python/frontend workflow jobs.
- [x] v1.2.2 local runtime and release-evidence closure.

## v1.3.0 read-only Reader/PDF vertical slice

- [x] Add `GET /papers/{paper_id}/pdf` with managed-root containment, explicit failure states, inline delivery, streaming, and browser byte-range support.
- [x] Extend the same-origin bridge for only the exact PDF GET route, including binary streaming, Range forwarding, and safe response-header preservation.
- [x] Add `/papers/{paper_id}/reader`, explicit metadata/PDF/offline/native-viewer states, and stable-identity navigation from Paper Detail.
- [x] Keep notes, metadata changes, PDF maintenance, and every other write workflow in Streamlit.
- [x] Complete and record the current v1.3.0 full local validation gate: smoke 90/0/0, final pytest 496 passed, lint passed, build passed, and 14 Node tests passed.
- [x] Complete disposable read-only browser validation without reading or recording private paper identity, metadata, or local paths.
- [ ] Verify a relevant GitHub-hosted CI run after a future approved commit and push.
- [ ] Complete the user-performed clean-PC restore rehearsal.
- [ ] Commit, push, pull request, merge, tag, and release only after explicit approval.

## v1.2.2 runtime and release evidence closure

- [x] Implementation complete: use Vinext's supported IPv4-loopback hostname argument and print deterministic launch diagnostics.
- [x] Implementation complete: preserve push/pull-request CI and add `workflow_dispatch` without changing the required Python/frontend jobs.
- [x] Implementation complete: reconcile v1.2.1 evidence, v1.2.2 version surfaces, checklists, roadmap, and canonical tracker handoff.
- [x] Local validation complete: smoke 86/0/0, pytest 484 passed, lint passed, build plus 10 Node tests passed, deterministic setup passed, and runtime versions were recorded on 2026-07-18.
- [ ] Manual runtime validation complete: local listeners, direct/bridge/query checks, Dashboard, Library, Papers, offline navigation, and Streamlit were verified; Paper Detail remains unperformed because no paper record was available.
- [ ] Hosted CI verified: retain the relevant GitHub Actions conclusion and run URL.
- [ ] Clean-PC restore rehearsed: retain user-performed clean-machine evidence.
- [ ] Commit, push, pull request, merge, tag, and release only after explicit approval.

## Next: Reader/PDF hardening and optional PDF.js evaluation

- [ ] Collect v1.3.0 hosted-CI evidence before expanding the Reader surface.
- [ ] Evaluate PDF.js only as a separately scoped, dependency-reviewed enhancement; do not assume it is required.
- [ ] Preserve native-viewer fallback and the existing safe PDF-serving contract if another renderer is introduced.
- [ ] Preserve Streamlit as the write/note workflow until a separately approved migration exists.

## Deferred product work

Write APIs; project/tag APIs; OpenAPI-generated TypeScript types; UI redesign; database or user-data migration; installer/packaging; automated restore; cloud sync; background services; OCR; semantic/LLM tagging; multi-user support; knowledge graphs; automatic duplicate operations; and `paper_id` redesign.

## Tracker handoff

- [x] `docs/tracker_sync_status.json` is the canonical repository handoff for the external roadmap tracker.
- [ ] Update the external tracker from that handoff outside repository code; do not add a Drive API, OAuth flow, or sync client.
