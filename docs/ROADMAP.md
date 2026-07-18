# BluePrintReboot Roadmap

Last synced: 2026-07-18

BluePrintReboot is a local-first, single-user research workspace with an established Streamlit application, a read-only FastAPI layer, and a TypeScript frontend shell. These are implemented architecture, not future placeholders.

## Implemented architecture

- v1.0.26 finalized Streamlit Reader/lifecycle stability, routed metadata mutations through one coordinator, froze JSON-safe read models, and added non-destructive restore-readiness checks.
- v1.1.0-v1.1.2 established four GET-only FastAPI route shapes for health, library status, paper collection, and paper detail.
- v1.2.0 added the seven-route TypeScript shell and allowlisted same-origin bridge.
- v1.2.1 made Python/frontend validation one reproducible local gate with portable Node resolution, deterministic `npm ci`, bridge tests, evidence output, and separate workflow jobs.
- v1.2.2 corrects the local frontend bind contract, adds manual workflow execution support, reconciles controlled release evidence, and adds a canonical tracker handoff. It adds no product feature.
- v1.3.0 adds the first safe read-only Reader/PDF vertical slice: a managed-file PDF endpoint, a streaming same-origin bridge, Paper Detail navigation, and a dedicated browser-native Reader route.

## Decision gates

| Gate | Current status | Required evidence |
|---|---|---|
| v1.3.0 focused implementation | Verified locally | Disposable PDF endpoint tests cover containment, exact bytes, byte ranges, errors, and the unchanged GET-only surface; frontend tests cover binary streaming and Reader source contracts. |
| v1.3.0 full-stack automated baseline | Verified locally | Smoke 90/0/0, final pytest 496 passed, deterministic `npm ci`, lint passed, production build plus 14 Node tests passed, and full-scope evidence. |
| Runtime address contract | Verified locally | Supported Vinext hostname argument, `127.0.0.1:3000` listener, canonical URL probes, and no external listener. |
| v1.3.0 Reader runtime validation | Verified with disposable data | Papers, Paper Detail, Open Reader, native PDF display, same-origin URL, Back navigation, Range delivery, offline state, navigation continuity, and recovery were visibly checked without real library data. |
| Hosted CI | Open | Relevant GitHub Actions conclusion and run URL; workflow-file existence is insufficient. |
| Clean-PC restore | Open | User-performed clean-machine rehearsal. |
| Separate real Streamlit manual regression | Open | Intentionally not launched because this pass may not read real library content; existing Reader regressions remain automated. |
| Lifecycle and Reader safety | Closed and preserved | Existing disposable-fixture regressions stay green; no contract or format changes. |
| Reader/PDF vertical slice | Implemented in v1.3.0 | Managed-root containment, GET-only streaming, same-origin delivery, explicit Reader states, and no write controls. |

## Next product milestone

Harden the native Reader/PDF slice after runtime evidence is complete, then evaluate PDF.js only as a separately approved enhancement. Any future renderer must preserve the managed-root security boundary, byte-range delivery, same-origin browser access, and Streamlit ownership of all write workflows.

## Continuing constraints

No write API, autosave, automatic duplicate merge/deletion, automatic repair, database migration, OCR, LLM tagging, cloud sync, `paper_id` redesign, installer, background service, or destructive automated restore. Keep real user data out of tests and validation evidence.
