# BluePrintReboot Roadmap

Last synced: 2026-07-11

This roadmap reflects the `v1.0.24-reader-validation-and-parity-closure` target. BluePrintReboot remains local-first, single-user, and Streamlit-based. FastAPI and frontend implementation remain out of scope while v1.0.25 lifecycle/recovery closure is pending.

## Current Status Snapshot

Implemented through v1.0.24:

- v1.0.10 added Windows developer bootstrap scripts: `scripts/dev_setup.ps1`, `scripts/dev_check.ps1`, `scripts/run_app.ps1`, and `start_blueprint.bat`.
- v1.0.11 split cheap local scanning from explicit DOI/Crossref enrichment, preserved existing accepted metadata during scan, and blocked duplicate external note imports unless force re-import is explicitly selected.
- v1.0.12 introduced the Tag Book v2 configuration under `config/tag_book/`, with canonical tags, aliases, normalization rules, blocked terms, candidate patterns, method lexicon support, validation, grouped evidence-bearing suggestions, and compatibility with the legacy tag config.
- v1.0.13 added the rebuildable `PaperTextProfile` cache from paper index metadata, cached extracted-text abstract fallback, Reading Note sections, and structured note blocks.
- v1.0.14 improved deterministic tag candidate hygiene, including source-prefix cleanup, source-aware quality scoring, duplicate canonical/alias rejection, separated known versus candidate suggestions, and non-selectable rejected candidates.
- v1.0.15 repaired PDF profile extraction from cached/full extracted text: cleaned front matter, title, authors, DOI, abstract, keywords, article type, section headings, extraction warnings, metadata gap-fill for incomplete Crossref previews, and explicit `pdf_abstract`, `pdf_keywords`, and `pdf_section_headings` tag suggestion sources.
- v1.0.16 synced roadmap, backlog, checklist, release notes, and README evidence without changing app behavior.
- v1.0.17 made native Streamlit PDF rendering the default Reader path, demoted HTML/base64 rendering to explicit experimental fallback, added large-PDF guardrails and external path guidance, and preserved Reader paper context across note, tag, status, priority, and Reader project-link actions.
- v1.0.18 added read-only file lifecycle diagnosis, same-hash duplicate keep/reconnect/ignore/remove controls, duplicate reconnect that preserves `paper_id`, confirmed duplicate index-row removal, and regression coverage proving same-hash rows are not auto-merged.
- v1.0.19 added orphan extracted-text cache detection, export/reattach/delete workflows for orphan notes and note blocks, export/reattach/unlink workflows for orphan project links, and atomic extracted-text `.txt` cache writes.
- v1.0.20 added typed corrupt JSON handling, action-oriented Health Check guidance, explicit backup snapshot inclusion/exclusion policy, clearer Streamlit safety feedback, and focused safety regression tests.
- v1.0.21 added conservative PDF hash metadata reuse, Reader note draft baselines, non-destructive metadata header refresh for unsaved drafts, and concise Streamlit feedback around Reader and scan actions.
- v1.0.22 added shared atomic Reading Note writes, failure-safety coverage, and read-only backup snapshot verification without changing note format, draft-save behavior, or restore policy.
- v1.0.23 added a paper-scoped Reader note state contract, visible state, explicit dirty-reload Keep/Discard decisions, idempotent pending operations, and documented transition precedence.
- v1.0.24 combined status/priority Apply, removed safe redundant explicit reruns, documented Reader action/rerun behavior, and defined the minimum future frontend parity contract.
- Earlier v1.0.x safety work remains in place: `pdf_sha256` support, missing-PDF reconnect/remove, same-hash duplicate review, orphan record review, confirmed orphan project-link removal, atomic JSON writes, backup snapshot, and release-readiness documentation.

Partial or incomplete:

- `paper_id` is still generated from the relative file path. Content hash supports repair/reconnect, but it is not the primary identity.
- Same-hash duplicate handling is explicit and conservative. Automatic merge remains intentionally deferred.
- Orphan note, note-block, and project-link repair is available through explicit repair workflows. Automatic deletion remains intentionally deferred.
- Atomic persistence covers key JSON metadata, CSV replacement, extracted full-text `.txt` cache writes, and Reading Note creation/save/header refresh.
- Reader note behavior is automated and documented; user-performed Streamlit manual smoke is still required. Remaining full-script/PDF rerenders are accepted until the future frontend/PDF.js slice.
- Native PDF viewing is now the default. The HTML/base64 viewer is explicit experimental fallback only and is guarded for large PDFs.
- Tag suggestions are deterministic and evidence-bearing, but generated candidates are not automatically promoted to the Tag Book. Candidate promotion remains a deliberate user governance action.
- PDF profile extraction relies on readable cached/full extracted text. It does not include OCR, image parsing, full methods/results extraction, external ontology lookup, or LLM/API tagging.
- FastAPI and frontend migration remain blocked by the open lifecycle, Reader, and storage-safety decisions.

## Decision Gates

| Gate | Status | Meaning | Required to close |
|---|---|---|---|
| G0: Baseline validation | Active | Smoke check, pytest, environment details, and manual checklist evidence must be recorded before release handoff. | Run `.\scripts\dev_check.ps1`, record Python, Streamlit, and platform evidence, and keep runtime/user data out of Git. |
| G1: Library lifecycle safety | Mostly closed | Missing/reconnect, duplicate-row policy, orphan repair, atomic JSON writes, and atomic extracted-text writes are in place. | Decide archive semantics, corrupt-cache quarantine, and whether unindexed duplicate PDFs need additional non-destructive outcomes beyond keep/ignore/reconnect. |
| G2: Setup friction | Closed | Scripted setup/check/run flow exists for Windows. | Keep README and scripts aligned when dependencies or launch behavior change. |
| G3: Scan/enrich separation | Closed | Scan discovers PDFs and fingerprints; DOI/Crossref work is explicit, with cached hash metadata reuse for unchanged indexed PDFs. | Keep scan cheap and add regression coverage when scanner behavior changes. |
| G4: Reader stability | Conditional | Automated state/parity coverage, combined settings Apply, safe rerun reduction, explicit note state, confirmed dirty reload, and non-destructive header refresh are in place. | User must complete and record the v1.0.24 Streamlit manual smoke. Remaining PDF rerenders are accepted until the frontend/PDF.js slice. |
| G5: Deterministic tag quality | Frozen | Tag Book v2, method lexicon candidates, candidate hygiene, profile sources, and preview-only generated candidates are implemented. | Do not expand tag governance or quality during the current stabilization sequence. |
| G6: FastAPI readiness | No | Reader parity is documented, but manual Reader evidence and v1.0.25 lifecycle/recovery closure remain. | Wait until G1/G4 are closed or explicitly accepted after v1.0.25. |
| G7: Frontend readiness | No | Streamlit stabilization and read-only API boundaries are not complete. | Wait until the read-only API boundary and Reader parity requirements are clear. |

## Next Implementation Queue

### 1. Reader polish

Goal: keep Reader interactions predictable while reducing remaining Streamlit rerun friction.

Target behavior:

- Complete user-performed Streamlit manual smoke and then close G4 if it passes.
- Keep the documented action/rerun and Save/Reload/Insert/Import contracts aligned.
- Preserve paper-scoped state across every new non-note Reader action.
- Defer deeper PDF rerender work to the future frontend/PDF.js vertical slice.

### 2. Library lifecycle edge-case polish

Goal: keep lifecycle repair conservative while clarifying remaining edge cases.

Target behavior:

- Keep duplicate PDF auto-merge out of scope unless a future design explicitly proves it is safe.
- Add safer outcomes for unindexed same-hash duplicates.
- Decide how archive should work if `status` remains limited to `unread`, `reading`, and `read`.
- Keep notes, note blocks, project links, PDFs, and index rows protected unless the user confirms a specific action.

### 3. Storage safety polish

Goal: make cache/state failures easier to recover from.

Target behavior:

- Consider backup or quarantine behavior for corrupt JSON/text cache files.
- Surface corrupt cache/state files in Library Health Check.

### 4. FastAPI read-only layer

Goal: introduce backend boundaries only after the Streamlit data model is stable.

Initial eventual scope:

- `/health`
- `/library/status`
- `/papers`
- `/papers/{paper_id}`
- read-only notes, tags, projects, and health summaries after the first endpoints are stable.

No write endpoints should be added until Streamlit write paths and data lifecycle policies are stable.

## Deferred Until Gates Close

### Frontend migration

Do not start React/Next/PDF.js migration until the read-only API boundary, Reader parity requirements, and file lifecycle policy are clear.

### Packaging / launcher / installer

Keep the existing Windows launcher and PowerShell scripts lightweight. Full packaging should wait until setup scripts, restore workflow, and Reader behavior are reliable.

### AI-assisted features

Do not introduce LLM-dependent features until local deterministic retrieval/tagging workflows are useful without external APIs.

## Operating Principle

Stabilize the local research workflow before expanding the platform. The priority is not adding surface area; it is making add/read/note/tag/link/repair/backup behavior boring, predictable, and recoverable.
