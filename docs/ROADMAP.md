# BluePrintReboot Roadmap

Last synced: 2026-07-14

BluePrintReboot is a local-first, single-user research workspace with an established Streamlit application, a read-only FastAPI layer, and a TypeScript frontend shell. These are implemented architecture, not future placeholders.

## Implemented architecture

- v1.0.26 finalized Streamlit Reader/lifecycle stability, routed metadata mutations through one coordinator, froze JSON-safe read models, and added non-destructive restore-readiness checks.
- v1.1.0 exposed read-only `GET /health` and `GET /library/status` FastAPI adapters.
- v1.1.1 added read-only paper collection and detail routes; v1.1.2 extended paper detail with rich citation metadata without changing storage identity.
- v1.2.0 added the seven-route TypeScript frontend shell and an allowlisted same-origin bridge for the four GET route shapes.
- v1.2.1 makes Python and frontend validation one reproducible release gate, with portable Node resolution, deterministic `npm ci`, bridge tests, optional evidence, and equivalent independent CI jobs.

## Decision gates

| Gate | Status after v1.2.1 implementation | Required evidence |
|---|---|---|
| G0: Full-stack automated baseline | Closed for v1.2.1 | Smoke 84/0/0, pytest 476/0/0, frontend lint, frontend build plus 10 tests, diff, evidence, and data-hygiene checks passed. |
| G1: Lifecycle safety | Closed and preserved | Existing disposable-fixture regressions remain green; no data formats change. |
| G4: Reader stability | Closed and preserved | Previously reported v1.0.26 manual evidence remains valid; new manual claims require an actual run. |
| G6: Read-only FastAPI foundation | Implemented | Four GET-only route shapes and response contracts remain unchanged. |
| G7: Frontend shell readiness | Implemented | Rendered shell and same-origin bridge behavior are in the canonical frontend gate. |
| G8: Reader/PDF vertical slice | Next | Define a read-only PDF/Reader contract and preserve Reader parity before choosing rendering details. |

## Next product milestone

Build one read-only Reader/PDF vertical slice in the web frontend. It should connect a paper detail to safe PDF/Reader presentation while preserving explicit note-save semantics and the existing Streamlit workflows. PDF.js selection, PDF-serving contracts, and security/path behavior require a separate scoped design; they are not part of v1.2.1.

## Continuing constraints

No write API, autosave, automatic duplicate merge/deletion, automatic repair, database migration, OCR, LLM tagging, cloud sync, `paper_id` redesign, installer, background service, or destructive automated restore. Keep real user data out of tests and validation evidence.
