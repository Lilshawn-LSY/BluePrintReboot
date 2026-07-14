# BluePrintReboot Backlog

Last synced: 2026-07-14

## Implemented foundations

- [x] v1.0.26 Streamlit finalization, frozen read models, lifecycle safety, and restore-readiness boundary.
- [x] v1.1.0 read-only health/library FastAPI foundation.
- [x] v1.1.1 paper list/detail API and v1.1.2 rich paper metadata.
- [x] v1.2.0 desktop TypeScript shell, typed client, and same-origin read-only bridge.

## v1.2.1 full-stack validation gate

- [x] Resolve Node from `-NodeHome`, `BLUEPRINT_NODE_HOME`, or `PATH`, enforcing Node 22.13.0 and complete node/npm executables.
- [x] Add deterministic `npm ci` frontend setup and keep Python-only setup usable.
- [x] Make the default `dev_check.ps1` run smoke, full pytest, frontend lint, and one frontend build/test pass.
- [x] Label `-PythonOnly` and `-SmokeOnly` as partial, non-release-qualified validation.
- [x] Add opt-in ignored JSON evidence without command output, secrets, or private paths.
- [x] Add allowlist, query, upstream error, fetch failure, and GET-only bridge tests.
- [x] Split GitHub Actions into equivalent Python and frontend jobs.
- [x] Record final automated results: smoke 84/0/0, pytest 476/0/0, frontend lint passed, and frontend build plus 10 tests passed.
- [ ] Record manual browser checks only if actually performed; do not infer completion.
- [ ] Commit, merge, tag, and release only after explicit approval.

## Next: read-only Reader/PDF vertical slice

- [ ] Define the minimal safe read-only PDF/Reader API contract without exposing absolute paths.
- [ ] Reconcile the Reader frontend parity checklist with the vertical-slice acceptance criteria.
- [ ] Choose and validate a PDF rendering approach only after the contract and local security boundary are explicit.
- [ ] Preserve Streamlit as the write/note workflow until a separately approved migration exists.

## Deferred product work

Write APIs; project/tag APIs; OpenAPI-generated TypeScript types; UI redesign; database or user-data migration; installer/packaging; automated restore; cloud sync; background services; OCR; semantic/LLM tagging; multi-user support; knowledge graphs; automatic duplicate operations; and `paper_id` redesign.

## Documentation cleanup

- [x] Treat the old project-level `backup_guideline.txt` as superseded by `docs/checklists/new_pc_restore_checklist.md`.
- [ ] Merge or archive tracker rows that still describe implemented FastAPI health/library/paper adapters or the v1.2.0 frontend shell as future work.
