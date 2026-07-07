# BluePrintReboot Roadmap

Last synced: 2026-07-07

This roadmap reflects the GitHub `main` branch at `v1.0.15-pdf-profile-extraction-repair` plus the `v1.0.16-roadmap-release-evidence-sync` documentation pass. v1.0.16 does not add product features or change runtime data behavior. BluePrintReboot remains local-first, single-user, and Streamlit-based. FastAPI, frontend migration, packaging, external ontology integration, and AI-assisted features remain deferred until the Streamlit foundation is more predictable.

## Current Status Snapshot

Implemented through v1.0.15:

- v1.0.10 added Windows developer bootstrap scripts: `scripts/dev_setup.ps1`, `scripts/dev_check.ps1`, `scripts/run_app.ps1`, and `start_blueprint.bat`.
- v1.0.11 split cheap local scanning from explicit DOI/Crossref enrichment, preserved existing accepted metadata during scan, and blocked duplicate external note imports unless force re-import is explicitly selected.
- v1.0.12 introduced the Tag Book v2 configuration under `config/tag_book/`, with canonical tags, aliases, normalization rules, blocked terms, candidate patterns, method lexicon support, validation, grouped evidence-bearing suggestions, and compatibility with the legacy tag config.
- v1.0.13 added the rebuildable `PaperTextProfile` cache from paper index metadata, cached extracted-text abstract fallback, Reading Note sections, and structured note blocks.
- v1.0.14 improved deterministic tag candidate hygiene, including source-prefix cleanup, source-aware quality scoring, duplicate canonical/alias rejection, separated known versus candidate suggestions, and non-selectable rejected candidates.
- v1.0.15 repaired PDF profile extraction from cached/full extracted text: cleaned front matter, title, authors, DOI, abstract, keywords, article type, section headings, extraction warnings, metadata gap-fill for incomplete Crossref previews, and explicit `pdf_abstract`, `pdf_keywords`, and `pdf_section_headings` tag suggestion sources.
- Earlier v1.0.x safety work remains in place: `pdf_sha256` support, missing-PDF reconnect/remove, same-hash duplicate review, orphan record review, confirmed orphan project-link removal, atomic JSON writes, backup snapshot, and release-readiness documentation.

Partial or incomplete:

- `paper_id` is still generated from the relative file path. Content hash supports repair/reconnect, but it is not the primary identity.
- Same-hash duplicate handling remains review-oriented. Full duplicate merge/remove policy is still deferred.
- Orphan note and note-block handling remains review-only. Reattach/export/delete workflows are not implemented for those files.
- Atomic persistence covers key JSON metadata and CSV replacement, but extracted full-text `.txt` cache writes are still direct writes.
- Reader Workspace still has Streamlit rerun limitations around PDF rendering, note editing, tags, status changes, and metadata refresh.
- Native PDF viewing is not the default. The stable HTML viewer remains the default/fallback path, and broader PDF viewer stabilization is deferred.
- Tag suggestions are deterministic and evidence-bearing, but generated candidates are not automatically promoted to the Tag Book. Candidate promotion remains a deliberate user governance action.
- PDF profile extraction relies on readable cached/full extracted text. It does not include OCR, image parsing, full methods/results extraction, external ontology lookup, or LLM/API tagging.
- FastAPI and frontend migration remain blocked by the open lifecycle, Reader, and storage-safety decisions.

## Decision Gates

| Gate | Status | Meaning | Required to close |
|---|---|---|---|
| G0: Baseline validation | Active | Smoke check, pytest, environment details, and manual checklist evidence must be recorded before release handoff. | Run `.\scripts\dev_check.ps1`, record Python, Streamlit, and platform evidence, and keep runtime/user data out of Git. |
| G1: Library lifecycle safety | Partial | Missing/reconnect, duplicate review, orphan review, and atomic JSON writes are in place. | Add clearer duplicate merge/remove policy, orphan note/block reattach/export/delete options, and atomic text-cache writes. |
| G2: Setup friction | Closed | Scripted setup/check/run flow exists for Windows. | Keep README and scripts aligned when dependencies or launch behavior change. |
| G3: Scan/enrich separation | Closed | Scan discovers PDFs and fingerprints; DOI/Crossref work is explicit. | Keep scan cheap and add regression coverage when scanner behavior changes. |
| G4: Reader stability | Partial | Reader workflows exist, but PDF viewing and rerun boundaries still need hardening. | Make PDF rendering behavior clearer, reduce rerun side effects, document note draft state, and add focused Reader-state tests. |
| G5: Deterministic tag quality | Mostly closed | Tag Book v2, method lexicon candidates, candidate hygiene, profile sources, and preview-only generated candidates are implemented. | Keep improving corpus fixtures and make candidate promotion/rejection governance clearer before any semantic or AI-assisted expansion. |
| G6: FastAPI readiness | No | Data contracts are still shifting around lifecycle and Reader behavior. | Wait until G1, G4, and storage-safety gaps are closed or explicitly accepted. |
| G7: Frontend readiness | No | Streamlit stabilization and read-only API boundaries are not complete. | Wait until the read-only API boundary and Reader parity requirements are clear. |

## Next Implementation Queue

### 1. Reader PDF stabilization

Goal: make PDF reading more dependable inside Streamlit without changing the data model.

Target behavior:

- Clarify native PDF versus HTML viewer behavior.
- Keep a reliable fallback when native rendering varies by environment.
- Add size warning or explicit render action for large PDFs.
- Add an `Open PDF externally` escape hatch if safe in the local app context.
- Hide PDF/extraction diagnostics behind an intentional developer/debug affordance.

### 2. Reader state cleanup

Goal: reduce accidental rerun side effects while editing notes and metadata.

Target behavior:

- Document the note draft state machine.
- Add tests for metadata refresh with unsaved note drafts.
- Keep Save/Reload/Insert/Import precedence explicit.
- Verify tag/status changes do not discard unsaved note edits.

### 3. Library lifecycle repair completion

Goal: finish repair policies that are currently review-only.

Target behavior:

- Decide duplicate PDF merge/remove semantics.
- Add safer outcomes for unindexed same-hash duplicates.
- Add orphan note and note-block reattach/export/delete workflows with explicit confirmation.
- Keep notes, note blocks, project links, PDFs, and index rows protected unless the user confirms a specific action.

### 4. Storage safety polish

Goal: make cache/state failures easier to recover from.

Target behavior:

- Make extracted full-text `.txt` cache writes atomic.
- Consider backup or quarantine behavior for corrupt JSON/text cache files.
- Surface corrupt cache/state files in Library Health Check.

### 5. FastAPI read-only layer

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
