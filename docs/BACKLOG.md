# BluePrintReboot Backlog

Last synced: 2026-07-07

This backlog is ordered for the post-v1.0.15 stabilization cycle and the v1.0.16 roadmap/release evidence sync. It intentionally prioritizes reliability, documentation, and validation over FastAPI/frontend expansion.

## Completed Since v1.0.9

These items should not remain in the active Next queue.

- **v1.0.10 Developer bootstrap scripts** - `scripts/dev_setup.ps1`, `scripts/dev_check.ps1`, `scripts/run_app.ps1`, `start_blueprint.bat`, README Quick Start updates, and script-inspection tests are in place.
- **v1.0.11 Scan/enrich split** - normal scanning is cheap PDF discovery and fingerprint sync; DOI extraction and Crossref lookup are explicit metadata assist actions; accepted metadata is preserved during scans.
- **v1.0.11 Duplicate external note import guard** - duplicate `source_sha256` imports are blocked by default, with an explicit force re-import path in service and UI.
- **v1.0.12 Tag Book v2** - dedicated Tag Book config, method lexicon, candidate patterns, normalization, blocked terms, validation, grouped evidence-bearing suggestions, and legacy config compatibility are implemented.
- **v1.0.13 PaperTextProfile minimal cache** - rebuildable profile caches derive from index metadata, cached extracted-text abstract fallback, Reading Notes, and note blocks.
- **v1.0.14 Tag quality hygiene** - generated candidates are cleaned, scored, rejected when low-quality or duplicate, separated from known canonical suggestions, and kept preview/select-only.
- **v1.0.15 PDF profile extraction repair** - cached/full extracted PDF text can supply cleaned front-matter title, authors, DOI, abstract, keywords, article type, section headings, warnings, metadata gap-fill, and explicit PDF profile tag sources.

## Next

These items should be implemented before starting FastAPI or frontend migration.

### 1. Reader PDF stabilization

- Clarify native PDF versus HTML viewer behavior.
- Keep a reliable fallback when native rendering varies by environment.
- Add large-PDF warning or explicit render action.
- Add `Open PDF externally` if safe in the local app context.
- Hide PDF/extraction diagnostics unless developer/debug mode is enabled.

### 2. Reader state cleanup

- Document the note draft state machine.
- Add tests for unsaved note behavior during metadata refresh.
- Reduce PDF rerenders where Streamlit allows it.
- Keep Save/Reload/Insert/Import precedence explicit.

### 3. Library lifecycle repair completion

- Decide and implement duplicate merge/remove semantics.
- Add clearer user-facing outcomes for unindexed duplicate PDFs skipped by scan.
- Decide how archive should work if `status` remains limited to `unread`, `reading`, and `read`.
- Add orphan note and note-block reattach/export/delete workflows with explicit confirmation.

### 4. Storage safety polish

- Make extracted full-text `.txt` cache writes atomic.
- Consider backup or quarantine behavior for corrupt JSON/text cache files.
- Surface corrupt cache/state files in Library Health Check.

## Partial Completion Items

These are implemented enough to be useful, but not enough to close the relevant decision gate.

### Paper lifecycle repair

Current state:

- Missing indexed PDF reconnect/remove exists.
- `pdf_sha256` supports repair and duplicate review.
- Same-hash duplicates can be reviewed.

Still needed:

- Decide and implement duplicate merge/remove semantics.
- Add clearer user-facing outcomes for unindexed duplicate PDFs skipped by scan.
- Decide how archive should work if `status` remains limited to `unread`, `reading`, and `read`.

### Orphan record handling

Current state:

- Orphan note files and note block files are detected.
- Orphan project links can be removed with confirmation.

Still needed:

- Reattach orphan note files to a selected paper.
- Export orphan notes/note blocks before deletion.
- Optional confirmed delete for orphan note/note-block files.
- Tests for every destructive and non-destructive branch.

### Storage safety

Current state:

- Key JSON writes use atomic temp-file + fsync + replace.
- `paper_index.csv` already uses atomic CSV replacement.

Still needed:

- Make extracted full-text `.txt` cache writes atomic.
- Consider backup or quarantine behavior for corrupt JSON/text cache files.
- Surface corrupt cache/state files in Library Health Check.

### Reader state

Current state:

- Reader note drafts, pending reloads, pending appends, and import reloads are managed through Streamlit session state.
- PaperTextProfile rebuild and tag suggestion panels are available from Reader Workspace.

Still needed:

- Document the state machine.
- Add tests for unsaved note behavior during metadata refresh.
- Reduce PDF rerenders where Streamlit allows it.

### PDF profile extraction

Current state:

- Cached/full extracted PDF text can provide cleaned front-matter title, authors, DOI, abstract, keywords, article type, section headings, and warnings.
- Profile-derived abstract, keywords, and section headings are visible as tag suggestion sources.
- Metadata gap-fill can improve incomplete Crossref previews without overwriting non-empty current fields automatically.

Still needed:

- More real-world fixture coverage for publisher layouts.
- No OCR, image parsing, figure/table parsing, or full methods/results extraction.
- No automatic metadata overwrite, auto-retagging, or LLM/API tagging.

## Backlog

### Tag governance polish

- Keep generated candidates preview/select-only.
- Improve documentation for candidate promotion versus paper-local tag selection.
- Add more corpus fixtures for rejected candidate examples and source attribution.
- Defer semantic synonym merging, external ontology lookup, and automatic retagging.

### Backup/restore polish

- Decide whether extracted text cache should remain excluded or become optional.
- Add restore dry-run documentation or tooling.
- Keep GitHub code and Drive/private user data separation strict.

### FastAPI read-only backend

Defer until the Streamlit foundation closes the lifecycle, Reader, and storage-safety gates.

Initial eventual endpoints:

- `/health`
- `/library/status`
- `/papers`
- `/papers/{paper_id}`

### Frontend migration

Defer until the read-only API boundary is stable and Reader parity requirements are written.

### Packaging / installer

- Keep lightweight launcher work near-term through existing scripts.
- Defer full packaging until the install/restore story is reliable.

### Optional AI-assisted features

- AI summary.
- Recommendation system.
- Relation graph.
- Advanced semantic retrieval.
- Zotero integration.
- Advanced highlighting/annotation.
