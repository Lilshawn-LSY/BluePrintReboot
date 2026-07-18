# BluePrintReboot Roadmap

Last synced: 2026-07-18

BluePrintReboot is a local-first, single-user research workspace with an established Streamlit application, a read-only FastAPI layer, and a TypeScript frontend shell. These are implemented architecture, not future placeholders.

## Implemented architecture

- v1.0.26 finalized Streamlit Reader/lifecycle stability, routed metadata mutations through one coordinator, froze JSON-safe read models, and added non-destructive restore-readiness checks.
- v1.1.0-v1.1.2 established four GET-only FastAPI route shapes for health, library status, paper collection, and paper detail.
- v1.2.0 added the seven-route TypeScript shell and allowlisted same-origin bridge.
- v1.2.1 made Python/frontend validation one reproducible local gate with portable Node resolution, deterministic `npm ci`, bridge tests, evidence output, and separate workflow jobs.
- v1.2.2 corrects the local frontend bind contract, adds manual workflow execution support, reconciles controlled release evidence, and adds a canonical tracker handoff. It adds no product feature.

## Decision gates

| Gate | Current status | Required evidence |
|---|---|---|
| Full-stack automated baseline | Verified locally for the dirty v1.2.2 working tree | Smoke 86/0/0, pytest 484 passed, lint passed, build plus 10 Node tests passed, deterministic setup and runtime-version evidence. |
| Runtime address contract | Verified locally | Supported Vinext hostname argument, `127.0.0.1:3000` listener, canonical URL probes, and no external listener. |
| Manual runtime validation | Open only for Paper Detail | API/frontend/Streamlit listeners, direct and bridged requests, query forwarding, Dashboard, Library, Papers, offline unavailable states, and sidebar navigation were verified; no paper record was available for a detail-route check. |
| Hosted CI | Open | Relevant GitHub Actions conclusion and run URL; workflow-file existence is insufficient. |
| Clean-PC restore | Open | User-performed clean-machine rehearsal. |
| Lifecycle and Reader safety | Closed and preserved | Existing disposable-fixture regressions stay green; no contract or format changes. |
| Reader/PDF vertical slice | Next product milestone | A separately scoped safe read-only PDF/Reader contract and parity plan. |

## Next product milestone

Build one read-only Reader/PDF vertical slice in the web frontend. It should connect a paper detail to safe PDF/Reader presentation while preserving explicit note-save semantics and the existing Streamlit workflows. PDF.js selection, PDF-serving contracts, and security/path behavior require a separate scoped design; they are not part of v1.2.2.

## Continuing constraints

No write API, autosave, automatic duplicate merge/deletion, automatic repair, database migration, OCR, LLM tagging, cloud sync, `paper_id` redesign, installer, background service, or destructive automated restore. Keep real user data out of tests and validation evidence.
