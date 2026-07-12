# BluePrintReboot Backlog

Last synced: 2026-07-12

This backlog is ordered after the v1.0.25 lifecycle and recovery implementation. It prioritizes manual gate evidence before FastAPI/frontend work.

## Completed Since v1.0.9

These items should not remain in the active Next queue.

- **v1.0.10 Developer bootstrap scripts** - `scripts/dev_setup.ps1`, `scripts/dev_check.ps1`, `scripts/run_app.ps1`, `start_blueprint.bat`, README Quick Start updates, and script-inspection tests are in place.
- **v1.0.11 Scan/enrich split** - normal scanning is cheap PDF discovery and fingerprint sync; DOI extraction and Crossref lookup are explicit metadata assist actions; accepted metadata is preserved during scans.
- **v1.0.11 Duplicate external note import guard** - duplicate `source_sha256` imports are blocked by default, with an explicit force re-import path in service and UI.
- **v1.0.12 Tag Book v2** - dedicated Tag Book config, method lexicon, candidate patterns, normalization, blocked terms, validation, grouped evidence-bearing suggestions, and legacy config compatibility are implemented.
- **v1.0.13 PaperTextProfile minimal cache** - rebuildable profile caches derive from index metadata, cached extracted-text abstract fallback, Reading Notes, and note blocks.
- **v1.0.14 Tag quality hygiene** - generated candidates are cleaned, scored, rejected when low-quality or duplicate, separated from known canonical suggestions, and kept preview/select-only.
- **v1.0.15 PDF profile extraction repair** - cached/full extracted PDF text can supply cleaned front-matter title, authors, DOI, abstract, keywords, article type, section headings, warnings, metadata gap-fill, and explicit PDF profile tag sources.
- **v1.0.16 Roadmap/release evidence sync** - roadmap, backlog, regression checklist, release notes, and README were synced to the implemented v1.0.10 through v1.0.15 state.
- **v1.0.17 Reader PDF stabilization** - native PDF rendering is the default Reader path, HTML/base64 rendering is an explicit experimental fallback, large PDFs avoid automatic base64 rendering, external path guidance is available, and Reader paper context is preserved across note, tag, status, priority, and Reader project-link actions.
- **v1.0.18 File lifecycle duplicate policy** - read-only lifecycle diagnosis, same-hash duplicate keep/reconnect/ignore/remove controls, `paper_id`-preserving duplicate reconnect, confirmed duplicate index-row removal, and no-auto-merge regression coverage are implemented.
- **v1.0.19 Orphan repair and storage hardening** - orphan extracted-text cache detection, orphan note/note-block export/reattach/delete, orphan project-link export/reattach/unlink, and atomic extracted-text `.txt` cache writes are implemented.
- **v1.0.20 Safety release foundation** - typed corrupt JSON handling, action-oriented Health Check guidance, explicit backup snapshot policy, clearer Streamlit safety feedback, release hygiene docs, and focused safety regression tests are implemented.
- **v1.0.21 Reader performance polish** - conservative hash metadata reuse, Reader draft baselines, safe reload, pending metadata header refresh, and concise Reader/scan feedback are implemented.
- **v1.0.22 Note durability and validation closure** - shared atomic Reading Note writes, replacement-failure regression coverage, existing unsaved metadata-refresh coverage, and read-only backup snapshot verification are implemented.
- **v1.0.23 Reader state-machine closure** - per-paper transition helpers, visible state, explicit dirty-reload Keep/Discard decisions, event precedence, idempotence, and newer-edit protection are implemented and documented.
- **v1.0.24 Reader validation and parity closure** - combined status/priority Apply, safe rerun reduction, Reader action/rerun classification, automated parity evidence, and a future frontend parity checklist are implemented.
- **v1.0.25 Lifecycle and recovery closure** - structured app-owned corruption diagnosis, verified recovery-copy/quarantine/restore, exact reversible duplicate decisions, metadata-only archive, backup coverage, and pure read summaries are implemented.

## Next

These items should be implemented before starting FastAPI or frontend migration.

### 1. Reader polish

- Record user-performed Streamlit manual smoke for the v1.0.24 Reader checklist.
- Accept remaining full-script/PDF rerenders until a future frontend/PDF.js vertical slice.
- Keep the documented action/rerun and Save/Reload/Insert/Import contracts aligned with future changes.

### 2. Library lifecycle validation

- Perform the manual recovery-copy, quarantine, restore, ignore/unignore, archive/unarchive, and archived-open Streamlit workflow.
- Keep automatic duplicate merge and duplicate-file deletion deferred.

### 3. Storage safety polish

- Keep critical user state manual-repair-only and cache quarantine explicit.

## Partial Completion Items

These are implemented enough to be useful, but not enough to close the relevant decision gate.

### Paper lifecycle repair

Current state:

- Missing indexed PDF reconnect/remove exists.
- `pdf_sha256` supports repair and duplicate review.
- Same-hash duplicates can be reviewed and repaired through explicit keep/reconnect/ignore/remove actions.
- Confirmed duplicate index-row removal deletes only the selected index row and preserves linked user data by default.

Still needed:

- Keep automatic duplicate merge deferred unless future UX and recovery policy make it safe.
- Add clearer user-facing outcomes for unindexed duplicate PDFs skipped by scan.
- Decide how archive should work if `status` remains limited to `unread`, `reading`, and `read`.

### Orphan record handling

Current state:

- Orphan note files and note block files are detected.
- Orphan extracted-text caches are detected.
- Orphan notes and note blocks can be exported, reattached, or deleted with confirmation.
- Orphan project links can be exported, reattached, or unlinked with confirmation.

Still needed:

- Consider whether orphan extracted-text caches need an export/delete workflow, or whether detection plus manual cleanup is enough.
- Add corrupt-cache quarantine guidance.

### Storage safety

Current state:

- Key JSON writes use atomic temp-file + fsync + replace.
- `paper_index.csv` already uses atomic CSV replacement.
- Extracted full-text `.txt` cache writes use atomic temp-file + fsync + replace.
- Reading Note creation, explicit save, and metadata-header refresh use the shared atomic text writer.

Still needed:

- Consider backup or quarantine behavior for corrupt JSON/text cache files.
- Surface corrupt cache/state files in Library Health Check.

### Reader state

Current state:

- Reader note drafts, pending reloads, pending appends, and import reloads are managed through Streamlit session state.
- PaperTextProfile rebuild and tag suggestion panels are available from Reader Workspace.
- Native PDF rendering is the default and HTML/base64 fallback is explicit and guarded for large files.
- Reader actions preserve the active paper and Paper Detail context across reruns.
- Clean/dirty state, reload decisions, header refresh, queued replacement, and append precedence are implemented in Streamlit-free helpers and documented.
- Safe application-triggered reruns are reduced; status/priority share one explicit Apply action; frontend parity requirements are documented.

Still needed:

- Complete and record user-performed Streamlit manual smoke before closing G4.
- Treat remaining PDF rerenders as accepted Streamlit behavior until the future frontend/PDF.js slice.

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

- Freeze tag-governance and tag-quality expansion during the v1.0.24-v1.0.25 stabilization sequence.
- Keep generated candidates preview/select-only.
- Improve documentation for candidate promotion versus paper-local tag selection.
- Add more corpus fixtures for rejected candidate examples and source attribution.
- Defer semantic synonym merging, external ontology lookup, and automatic retagging.

### Backup/restore polish

- Decide whether extracted text cache should remain excluded or become optional.
- Consider whether a future release should add guided restore after the read-only verifier; automated restore remains deferred.
- Keep GitHub code and Drive/private user data separation strict.

### FastAPI read-only backend

Defer implementation until v1.0.25 lifecycle/recovery closure and user-performed Reader manual validation are complete.

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
