# BluePrintReboot Roadmap

Last synced: 2026-07-05

This roadmap reflects the GitHub `main` branch at `v1.0.9-atomic-json-writes` and the updated developer roadmap tracker. BluePrintReboot remains local-first, single-user, and Streamlit-based. FastAPI, frontend migration, packaging, and AI-assisted features remain deferred until the Streamlit foundation is more predictable.

## Current Status Snapshot

v1.0.9 materially improved user-data safety and library maintenance, but it is not yet a platform-migration-ready baseline.

Implemented or mostly implemented:

- Atomic JSON writes for projects, project links, note blocks, note-import logs, canonical tag config, and extracted-text metadata.
- `pdf_sha256` index support and backfill.
- Missing indexed PDF reconnect/remove workflow.
- Same-hash duplicate review support.
- Orphan note, note block, and project-link review support, with confirmed removal for orphan project links.
- Backup snapshot and readiness documentation.

Partial or incomplete:

- Paper lifecycle repair exists, but `paper_id` is still generated from the relative file path. Content hash supports repair/reconnect but is not the primary identity.
- Same-hash duplicate handling is review-oriented. Full merge/remove policy is still deferred.
- Orphan note and note-block handling is review-only. Reattach/export/delete workflows are not implemented.
- Atomic persistence is available for key JSON metadata, but extracted full-text `.txt` writes are still direct writes.
- Reader Workspace still has Streamlit rerun limitations around PDF rendering, note editing, tags, and status changes.
- `scan_papers` still performs DOI extraction, so scanning can block on PDF parsing.
- External note import warns on duplicate source import but does not hard-block repeat imports by default.
- Tag suggestion remains rulebook/alias based. It does not yet have a method/assay dictionary or noun-phrase candidate layer.
- Native PDF viewing is not yet the default; the HTML base64 viewer remains available and should be treated as fallback/experimental.

## Decision Gates

| Gate | Status | Meaning | Required to close |
|---|---|---|---|
| G0: Baseline validation | Partial | Smoke check and pytest commands exist, but must be run before each new implementation cycle. | Run `python scripts/smoke_check.py` and `python -m pytest -q` on a clean local working tree. |
| G1: Library lifecycle safety | Partial | Missing/reconnect, duplicate review, orphan review, and atomic JSON writes are in place. | Add clearer duplicate merge/remove policy, orphan note/block reattach/export/delete options, and atomic text-cache writes. |
| G2: Setup friction | No | Quick Start is still manual. | Add `scripts/dev_setup.ps1`, `scripts/dev_check.ps1`, `scripts/run_app.ps1`, and `start_blueprint.bat`. |
| G3: Scan/enrich separation | No | Scan still does DOI extraction. | Make scan only discover PDFs and fingerprints; move DOI/metadata work to explicit enrich actions. |
| G4: Reader stability | No | PDF/note/tag/status actions still share the same Streamlit rerun tree. | Make native PDF default, demote HTML to fallback, reduce debug noise, add large-PDF safeguards, and document remaining Streamlit limits. |
| G5: Tag quality | No | Suggestions rely on configured aliases. | Add method/assay dictionary, noun-phrase candidates, category grouping, and user-approved promotion. |
| G6: FastAPI readiness | No | Data contracts are still shifting. | Wait until G1-G5 are closed or explicitly accepted as stable enough. |
| G7: Frontend readiness | No | Streamlit stabilization is not complete. | Wait until the read-only API boundary and Reader parity requirements are clear. |

## Next Implementation Queue

### 1. Baseline validation and roadmap sync

Goal: ensure the current branch is clean and the tracker/docs match the codebase before Codex changes more files.

Recommended checks:

```powershell
python scripts/smoke_check.py
python -m pytest -q
```

### 2. Developer bootstrap scripts

Goal: reduce repeated Windows/PowerShell setup friction.

Add:

- `scripts/dev_setup.ps1` - create `.venv`, upgrade pip, install base requirements.
- `scripts/dev_check.ps1` - run smoke check and pytest.
- `scripts/run_app.ps1` - activate `.venv` and launch Streamlit.
- `start_blueprint.bat` - one-click app launcher for Windows.

Done when a fresh clone can be set up, checked, and launched with documented script commands.

### 3. Scan/enrich split

Goal: make `Scan papers` cheap and predictable.

Target behavior:

- Scan only finds PDFs and records path, filename, size/mtime if needed, and SHA-256.
- DOI extraction is moved to explicit metadata enrichment.
- Existing DOI metadata should not be overwritten by scan.
- Large or difficult PDFs should not make scan feel frozen.

### 4. Duplicate external note import guard

Goal: prevent accidental repeated Google Docs/Markdown note imports.

Target behavior:

- If `source_sha256` was already imported into the selected `paper_id`, disable apply by default.
- Show a `Force re-import` checkbox.
- Only allow repeated import when the user explicitly opts in.

### 5. Reader PDF stabilization

Goal: make PDF reading more dependable inside Streamlit.

Target behavior:

- Prefer native PDF viewer by default when available.
- Demote HTML base64 viewer to fallback/experimental mode.
- Add size warning or explicit render button for large PDFs.
- Add an `Open PDF externally` escape hatch.
- Hide PDF/extraction debug information behind developer/debug mode.

### 6. Reader state cleanup

Goal: reduce accidental rerun side effects while editing notes.

Target behavior:

- Document the note draft state machine.
- Add tests for metadata refresh with unsaved note drafts.
- Keep Save/Reload/Insert/Import precedence explicit.

### 7. Tag suggestion v2

Goal: improve retrieval quality without requiring LLM/API use.

Target behavior:

- Keep current rulebook suggestions.
- Add deterministic method/assay dictionary matches.
- Add noun-phrase tag candidates from title, abstract, keywords, and extracted text preview.
- Group candidates by `field`, `organism`, `method`, `assay`, `concept`, and `paper-type`.
- Require user approval before adding tags or promoting aliases to the rulebook.

### 8. FastAPI read-only layer

Goal: introduce backend boundaries only after the Streamlit data model is stable.

Initial scope:

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

A simple Windows launcher can be added now, but full packaging should wait until setup scripts and restore workflow are reliable.

### AI-assisted features

Do not introduce LLM-dependent features until local deterministic retrieval/tagging workflows are useful without external APIs.

## Operating Principle

Stabilize the local research workflow before expanding the platform. The priority is not adding surface area; it is making add/read/note/tag/link/repair/backup behavior boring, predictable, and recoverable.
