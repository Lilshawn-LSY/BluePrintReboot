# BluePrintReboot Roadmap

Stable roadmap last edited: 2026-07-26

Current release evidence is not duplicated here. See the generated [Current Release Status](CURRENT_RELEASE_STATUS.md), derived from the canonical machine-readable manifest.

BluePrintReboot is a local-first, single-user research workspace with an established Streamlit application, a read-only FastAPI layer, and a TypeScript frontend shell. These are implemented architecture, not future placeholders.

## Implemented architecture

- v1.0.26 finalized Streamlit Reader/lifecycle stability, routed metadata mutations through one coordinator, froze JSON-safe read models, and added non-destructive restore-readiness checks.
- v1.1.0-v1.1.2 established four GET-only FastAPI route shapes for health, library status, paper collection, and paper detail.
- v1.2.0 added the seven-route TypeScript shell and allowlisted same-origin bridge.
- v1.2.1 made Python/frontend validation one reproducible local gate with portable Node resolution, deterministic `npm ci`, bridge tests, evidence output, and separate workflow jobs.
- v1.2.2 corrected the local frontend bind contract, added manual workflow execution support, reconciled controlled release evidence, and added a canonical tracker handoff.
- v1.3.0 added the first safe read-only Reader/PDF vertical slice: a managed-file PDF endpoint, a streaming same-origin bridge, Paper Detail navigation, and a dedicated browser-native Reader route.
- v1.3.1 converges source-control, hosted-CI, manual-regression, restore, and publication state; removes the accidental tracked console-output artifact; adds a tracked-entry hygiene gate; and makes the external tracker handoff deterministic.
- v1.4.0 makes PDF.js the primary web Reader, bundles its worker locally, adds bounded navigation/zoom/error/fallback behavior, and instruments document/render lifecycle without changing the secure PDF API or Streamlit writes.
- v1.4.2 makes release evidence non-self-invalidating by separating the immutable product baseline, completed control-plane change evidence, and non-invariant repository observations.
- v1.4.3 makes Reader aggregate state derive from its child evidence, permits truthful Streamlit regression completion, and rejects status/evidence contradictions without changing product behavior.

## Decision gates

| Gate | Current status | Evidence |
|---|---|---|
| v1.3.0 Reader/PDF implementation | Closed | Disposable endpoint and frontend tests cover containment, exact bytes, byte ranges, errors, binary streaming, Reader states, and the unchanged GET-only surface. |
| v1.3.0 local full-stack baseline | Closed | Smoke 90/0/0, pytest 496 passed, deterministic `npm ci`, lint passed, production build passed, and 14 Node tests passed on 2026-07-18. |
| v1.3.0 runtime and Reader validation | Closed | Local-only Reader/PDF, Range delivery, offline recovery, and cleanup checks passed without retaining private library metadata. |
| Separate Streamlit manual regression | Closed | User-performed Dashboard, Library, Paper Detail, Reader Workspace, existing PDF, and existing-note visibility checks passed without mutation. |
| PR #2 source control | Closed | Commit and push completed; PR #2 merged into `main` at `9663c8cd052a2fa106382630afff7dcd9cfda421`. |
| PR #2 hosted CI | Closed | GitHub Actions run `29641757582` tested `1d51f37971e5898d2f531e9812510c150a4ab56b`; Python and frontend jobs succeeded. |
| Post-merge `main` hosted CI | Closed | GitHub Actions run `29641792069` tested merge commit `9663c8cd052a2fa106382630afff7dcd9cfda421`; Python and frontend jobs succeeded. |
| v1.3.1 repository hygiene and state contracts | Verified locally | Focused tests 40 passed; hygiene passed; smoke 94/0/0; full pytest 524 passed; deterministic export, `npm ci`, lint, production build, and 14 Node tests passed. |
| v1.4.0 PDF.js Reader foundation | Canonical current state | Implementation, source control, automated/manual validation, tag, publication, and recurring operations are rendered from the [Current Release Status](CURRENT_RELEASE_STATUS.md). |
| v1.4.2 release-state closure | Canonical current state | Schema 4.0 and all current verification boundaries are rendered from the [Current Release Status](CURRENT_RELEASE_STATUS.md), without a committed mutable-HEAD invariant. |
| v1.4.3 release-state truth repair | Canonical current state | Reader and Streamlit completion evidence, the failed PR #6 Python job, and remaining open release checks are represented independently in the [Current Release Status](CURRENT_RELEASE_STATUS.md). |

## Next product milestone

Preserve the completed real-PDF and separate Streamlit evidence. Future Reader hardening may address only newly measured gaps and must preserve managed-root containment, same-origin byte-range delivery, stable `paper_id`, and Streamlit ownership of all write workflows.

## Continuing constraints

No write API, autosave, automatic duplicate merge/deletion, automatic repair, database migration, OCR, LLM tagging, cloud sync, `paper_id` redesign, installer, background service, or destructive automated restore. Keep real user data out of tests and validation evidence.
