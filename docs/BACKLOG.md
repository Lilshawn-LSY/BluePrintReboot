# BluePrintReboot Backlog

Last synced: 2026-07-05

This backlog is ordered for the post-v1.0.9 stabilization cycle. It intentionally prioritizes boring reliability over FastAPI/frontend expansion.

## Next

These items should be implemented before starting FastAPI or frontend migration.

### 1. Developer bootstrap scripts

- Add `scripts/dev_setup.ps1`.
- Add `scripts/dev_check.ps1`.
- Add `scripts/run_app.ps1`.
- Add `start_blueprint.bat`.
- Update README Quick Start to prefer scripts while keeping manual commands available.

### 2. Scan/enrich split

- Refactor scan so it only discovers PDFs and records file fingerprints.
- Move DOI extraction to explicit enrichment.
- Ensure scan does not overwrite accepted user metadata.
- Add focused tests for scan speed boundaries and metadata preservation.

### 3. Duplicate external note import guard

- Disable apply when the same `source_sha256` has already been imported into the selected paper.
- Add an explicit `Force re-import` checkbox.
- Add tests for duplicate warning, disabled apply, and forced re-import.

### 4. Reader PDF stabilization

- Make native PDF viewing the preferred/default path when available.
- Demote HTML base64 rendering to fallback/experimental.
- Add large-PDF warning or explicit render action.
- Add `Open PDF externally`.
- Hide PDF/extraction debug panels unless developer/debug mode is enabled.

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

Still needed:

- Document the state machine.
- Add tests for unsaved note behavior during metadata refresh.
- Reduce PDF rerenders where Streamlit allows it.

## Backlog

### Tag suggestion v2

- Add method/assay dictionary.
- Add noun-phrase candidates.
- Group candidates by category.
- Add approve-to-tag and approve-to-rulebook flows.

### Backup/restore polish

- Decide whether extracted text cache should remain excluded or become optional.
- Add restore dry-run documentation or tooling.
- Keep GitHub code and Drive/private user data separation strict.

### FastAPI read-only backend

Defer until the Streamlit foundation closes the setup, scan, Reader, and tag gates.

Initial eventual endpoints:

- `/health`
- `/library/status`
- `/papers`
- `/papers/{paper_id}`

### Frontend migration

Defer until the read-only API boundary is stable and Reader parity requirements are written.

### Packaging / installer

- Keep lightweight launcher work near-term.
- Defer full packaging until the install/restore story is reliable.

### Optional AI-assisted features

- AI summary.
- Recommendation system.
- Relation graph.
- Advanced semantic retrieval.
- Zotero integration.
- Advanced highlighting/annotation.
