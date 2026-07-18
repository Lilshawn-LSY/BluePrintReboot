# BluePrintReboot Backlog

Last synced: 2026-07-18

## Implemented foundations

- [x] v1.0.26 Streamlit finalization, frozen read models, lifecycle safety, and restore-readiness boundary.
- [x] v1.1.0-v1.1.2 four-route GET-only FastAPI foundation and rich paper metadata.
- [x] v1.2.0 desktop TypeScript shell, typed client, and same-origin read-only bridge.
- [x] v1.2.1 portable-Node-aware full local validation gate and separate Python/frontend workflow jobs.

## v1.2.2 runtime and release evidence closure

- [x] Implementation complete: use Vinext's supported IPv4-loopback hostname argument and print deterministic launch diagnostics.
- [x] Implementation complete: preserve push/pull-request CI and add `workflow_dispatch` without changing the required Python/frontend jobs.
- [x] Implementation complete: reconcile v1.2.1 evidence, v1.2.2 version surfaces, checklists, roadmap, and canonical tracker handoff.
- [x] Local validation complete: smoke 86/0/0, pytest 484 passed, lint passed, build plus 10 Node tests passed, deterministic setup passed, and runtime versions were recorded on 2026-07-18.
- [ ] Manual runtime validation complete: local listeners, direct/bridge/query checks, Dashboard, Library, Papers, offline navigation, and Streamlit were verified; Paper Detail remains unperformed because no paper record was available.
- [ ] Hosted CI verified: retain the relevant GitHub Actions conclusion and run URL.
- [ ] Clean-PC restore rehearsed: retain user-performed clean-machine evidence.
- [ ] Commit, push, pull request, merge, tag, and release only after explicit approval.

## Next: read-only Reader/PDF vertical slice

- [ ] Define the minimal safe read-only PDF/Reader API contract without exposing absolute paths.
- [ ] Reconcile the Reader frontend parity checklist with the vertical-slice acceptance criteria.
- [ ] Choose and validate a PDF rendering approach only after the contract and local security boundary are explicit.
- [ ] Preserve Streamlit as the write/note workflow until a separately approved migration exists.

## Deferred product work

Write APIs; project/tag APIs; OpenAPI-generated TypeScript types; UI redesign; database or user-data migration; installer/packaging; automated restore; cloud sync; background services; OCR; semantic/LLM tagging; multi-user support; knowledge graphs; automatic duplicate operations; and `paper_id` redesign.

## Tracker handoff

- [x] `docs/tracker_sync_status.json` is the canonical repository handoff for the external roadmap tracker.
- [ ] Update the external tracker from that handoff outside repository code; do not add a Drive API, OAuth flow, or sync client.
