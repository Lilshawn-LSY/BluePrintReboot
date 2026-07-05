# BluePrintReboot

## What is BluePrintReboot?

BluePrintReboot is a local-first research paper library built with Streamlit. It keeps PDFs, metadata, BluePrint Reading Notes, structured note blocks, project links, tags, and extracted text on the local machine.

The canonical managed PDF directory is `papers/`. Paper identity is the stable `paper_id` stored in `data/paper_index.csv`; Reading Notes, note blocks, project links, and extracted-text caches remain attached to that identity even when a PDF filename changes.

## Current Status

Current release target: **v1.0.10-dev-bootstrap**.

v1.0.10 adds Windows PowerShell bootstrap scripts for fresh setup, local verification, and Streamlit launch. The app runtime behavior from v1.0.9 remains unchanged: project JSON persistence uses atomic writes for user-data stores, and missing-PDF repair, same-hash duplicate review, and orphan record review remain available. FastAPI, frontend migration, sample workspace verification, scanner/index/tag/PDF viewer changes, and data lifecycle changes remain deferred.

The app remains intentionally local-first and single-user:

- Runtime library data is ignored by Git.
- GitHub stores the application code, not the personal paper library.
- Crossref is optional; core reading and organization workflows work offline.
- Maintenance actions use preview and confirmation where files or records can change.

## Windows Quick Start

From a fresh clone in Windows PowerShell:

```powershell
git clone <repository-url> BluePrintReboot
cd BluePrintReboot
.\scripts\dev_setup.ps1
.\scripts\dev_check.ps1
.\scripts\run_app.ps1
```

After setup, `start_blueprint.bat` is available as a convenience launcher from File Explorer or Command Prompt. It starts the existing `.venv` app; it does not run setup automatically.

Add PDFs directly to `papers/`, then select **Scan papers** in the app. Open **Library** to choose a paper and continue in **Paper Detail** or **Reader Workspace**.

For optional MarkItDown PDF support:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-optional.txt
```

Manual environment commands are a troubleshooting fallback when the scripts cannot be used:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\smoke_check.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py
```

### Troubleshooting

- **PowerShell execution policy** - Run scripts from PowerShell with `.\scripts\dev_setup.ps1`. If local policy blocks a script, use a process-only bypass such as `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\dev_setup.ps1`.
- **Python not found** - Install Python 3, make sure either `py` or `python` is available on `PATH`, reopen PowerShell, and rerun `.\scripts\dev_setup.ps1`.
- **Missing `.venv`** - Run `.\scripts\dev_setup.ps1`. `.\scripts\dev_check.ps1`, `.\scripts\run_app.ps1`, and `start_blueprint.bat` expect the environment to already exist.
- **Port 8501 already in use** - Launch with another port, for example `.\scripts\run_app.ps1 -Port 8502`.

## Core Reading Workflow

The main loop is:

1. Add a paper to `papers/`.
2. Read the PDF.
3. Edit metadata, status, priority, and tags.
4. Write the BluePrint Reading Note and structured note blocks.
5. Link papers and useful note blocks to projects.
6. Retrieve papers, notes, tags, and project context later.

Current support includes:

- Recursive PDF scanning from the canonical `papers/` directory.
- Stable paper identities and a local CSV metadata index.
- Search and filtering by metadata, status, priority, and tags.
- Reader Workspace with PDF viewing, the canonical BluePrint Reading Note, status, priority, and tags.
- Reading Note headers refresh from accepted paper metadata while preserving existing note body sections.
- Structured note blocks for summaries, claims, methods, evidence, questions, ideas, and limitations.
- BluePrint Reading Note template download and confirmed local import into the Reading Note and structured note blocks.
- Full-text extraction with MarkItDown when available and `pypdf` fallback.
- SHA-256 cache freshness checks and safe stale-cache recovery.

## Metadata/Tag Workflow

- DOI extraction from PDFs.
- Crossref metadata preview and explicit acceptance with classified diagnostics.
- DOI-less metadata fallback for arXiv/preprint/workshop PDFs, including arXiv ID detection, optional arXiv metadata lookup, and weak title guesses from PDF text or filename.
- Manual metadata editing when enrichment is incomplete or offline.
- Fallback metadata suggestions are previewed and user-applied; they do not claim perfect extraction.
- Deterministic tag suggestions and canonical tag governance.
- Research projects linking papers and structured note blocks.
- Paper Hygiene recommendations using `{year}_{first_author}_{short_title}.pdf` without changing `paper_id`.

Crossref polite-access contact resolution uses:

1. `CROSSREF_MAILTO`
2. `BLUEPRINT_CONTACT_EMAIL`
3. the built-in local default

Example:

```powershell
$env:CROSSREF_MAILTO = "researcher@example.edu"
```

Crossref enrichment requires the base dependencies `requests`, `urllib3`, and `certifi`.

## Maintenance/Backup Workflow

Settings is organized into four sections:

- **System** - app/runtime information, workspace paths, extraction backends, and index details.
- **Library Maintenance** - Library Health Check, Tag Rules, Drive Inbox Import, and Paper Hygiene.
- **External Services** - Crossref Diagnostics, dependency versions, and proxy/network status.
- **Backup** - light/full Backup Snapshot controls and manifest summaries.

Library Health Check reports missing or unindexed PDFs, duplicate filenames, duplicate PDF hashes, duplicate DOI values, incomplete metadata, orphan records, noncanonical paths, and stale extracted-text caches. Duplicate PDF hashes are shown as review-only groups with `pdf_sha256`, indexed/unindexed counts, indexed `paper_id`, title, filename, filepath, status, and cheap note/project-link counts when available. Unindexed duplicate PDFs are marked "Do not add to index yet; handle later." Orphan note files and note block files are review-only and marked to preserve for now, reattach manually later, or export before deletion. Orphan project links can be explicitly removed without changing papers, PDFs, notes, note blocks, or index rows. Missing indexed PDFs can be explicitly reconnected to a selected PDF under `papers/` or removed from the index without deleting related user files.

`BLUEPRINT_INBOX_DIR` can point to a Google Drive for desktop synced folder such as `G:\My Drive\BluePrint\paper`. No Google Drive API or OAuth is used. Inbox PDFs are candidates only; the app uses an explicit preview/confirm workflow to copy one selected PDF into `papers/` and leaves the source untouched.

Backup Snapshot creates timestamped ZIP files under `exports/`:

- **Light** - index, projects, links, notes, note blocks, tag configuration, and relevant local settings.
- **Full** - everything in a light snapshot plus managed PDFs from `papers/`.

Each archive contains `manifest.json` with the app version, timestamp, included files, SHA-256 checksums, and counts. Restore remains manual in v1.0.9. See the [new-PC restore checklist](docs/checklists/new_pc_restore_checklist.md).

Recommended move workflow:

1. Run Library Health Check on the old computer.
2. Create a full snapshot, or create a light snapshot and copy `papers/` separately.
3. Install BluePrintReboot on the new computer.
4. With the app stopped, extract the snapshot into the project root while preserving directory structure.
5. Start the app, scan papers, and run Library Health Check again.

## Development/Release Workflow

Foundation release documents:

- [BluePrint principles](docs/BLUEPRINT_PRINCIPLES.md)
- [Roadmap](docs/ROADMAP.md)
- [Backlog](docs/BACKLOG.md)
- [Development workflow](docs/DEV_WORKFLOW.md)
- [Release checklist](docs/RELEASE_CHECKLIST.md)
- [Mandatory regression checklist](docs/checklists/regression_checklist.md)
- [Manual v1.0 smoke test checklist](docs/checklists/v1.0_smoke_test.md)
- [New-PC restore checklist](docs/checklists/new_pc_restore_checklist.md)
- [v1.0.0-foundation release-note draft](docs/release_notes/v1.0_draft.md)

Before Codex-assisted changes, run the baseline validation command and note the result:

```powershell
.\scripts\dev_check.ps1
```

After Codex-assisted changes, run the same command again before review. For release hygiene work, also complete the [mandatory regression checklist](docs/checklists/regression_checklist.md).

```powershell
.\scripts\dev_check.ps1
```

Run a focused test file:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_library_health.py -q
```

Manual release validation is documented in [docs/RELEASE_CHECKLIST.md](docs/RELEASE_CHECKLIST.md), [docs/checklists/regression_checklist.md](docs/checklists/regression_checklist.md), and [docs/checklists/v1.0_smoke_test.md](docs/checklists/v1.0_smoke_test.md).

Do not commit, push, merge, or tag release work until review and explicit release approval are complete.

## Project Structure

- `app.py` - Streamlit entry point.
- `ui_streamlit/` - application pages and workspace UI.
- `ingest/` - scanning, DOI, Crossref, tagging, and text-extraction helpers.
- `services/` - inbox import, filename hygiene, backup, health checks, and workflow orchestration.
- `storage/` - index, notes, note blocks, projects, links, and extracted-text caches.
- `config/` - contact/inbox helpers and user-editable tag configuration.
- `scripts/` - non-destructive setup, check, launch, and readiness utilities.
- `docs/` - release, roadmap, workflow, and checklist documentation.
- `tests/` - automated test suite.
- `papers/` - canonical managed PDF library; ignored by Git.
- `data/` - local metadata and caches; ignored by Git.
- `notes/` - Markdown reading notes; ignored by Git.
- `exports/` - snapshots and exports; ignored by Git.

## Version History

### v1.0.10-dev-bootstrap

- Adds Windows PowerShell scripts for setup, local checks, and Streamlit launch.
- Adds `start_blueprint.bat` as a simple launcher after setup.
- Makes the script-based Windows workflow the default README path.
- Adds text-inspection tests for the developer bootstrap scripts.
- Keeps app behavior, scanner/index/tag/PDF viewer behavior, and user data lifecycle unchanged.

### v1.0.9-atomic-json-writes

- Adds a shared atomic JSON write helper using same-directory temporary files, flush/fsync, and `os.replace`.
- Converts project, project-link, note-block, note-import log, canonical tag, and extracted-text metadata JSON writes to atomic writes.
- Preserves existing JSON formatting conventions and schemas.
- Keeps original target files unchanged when serialization or replacement fails.
- Adds no destructive cleanup behavior beyond removing failed temporary files.

### v1.0.8-orphan-record-repair-review

- Adds dedicated orphan note file, orphan note block file, and orphan project link review records in Library Health Check.
- Keeps orphan note and note block handling review-only with preserve/reattach/export guidance.
- Adds explicit confirmed removal for orphan project links only.
- Leaves papers, PDFs, notes, note blocks, and index rows untouched during orphan project-link removal.
- Preserves v1.0.6 missing-PDF repair and v1.0.7 same-hash duplicate review behavior.

### v1.0.7-same-hash-duplicate-review

- Adds classified duplicate PDF hash review groups for indexed duplicates, indexed + unindexed duplicates, and multiple unindexed duplicates.
- Shows enough context to choose a future canonical record/file: `pdf_sha256`, indexed/unindexed counts, indexed `paper_id`, title, filename, filepath, status, and cheap note/project-link counts when available.
- Marks unindexed duplicate files as "Do not add to index yet; handle later."
- Preserves v1.0.6 missing-PDF reconnect/remove behavior.
- Adds no automatic merge, PDF deletion, or index-row removal; real merge/remove workflow remains deferred.

### v1.0.6-missing-pdf-repair-workflow

- Adds explicit missing-PDF repair actions in Library Health Check.
- Reconnects a missing index record to a selected PDF in `papers/` while preserving `paper_id` and updating only filename, filepath, and `pdf_sha256`.
- Requires explicit confirmation before accepting a replacement PDF with a different SHA-256.
- Removes missing records from the index only after confirmation and leaves notes, note blocks, project links, PDFs, and caches untouched.
- Defers archive lifecycle, orphan cleanup, and full duplicate repair.

### v1.0.5-pdf-hash-identity-foundation

- Adds `pdf_sha256` to the paper index schema with non-destructive migration/backfill when PDFs are available.
- Preserves the existing `paper_id` when a scanned PDF's SHA-256 safely matches one existing record after a path rename.
- Leaves ambiguous same-hash duplicate content out of automatic merge/repair behavior and reports duplicate PDF hashes through Library Health Check.
- Introduces no repair UI, duplicate lifecycle workflow, viewer change, API, frontend migration, or packaging change.

### v1.0.4-baseline-regression-lock

- Locks the current Streamlit baseline with mandatory before/after regression validation.
- Adds a mandatory regression checklist and makes the smoke check require it.
- Aligns runtime version metadata with `1.0.4`.
- Introduces no product behavior changes.

### v1.0.2-google-docs-note-import

- Adds one canonical BluePrint Reading Note template under `docs/templates/`.
- Adds local one-way import from Markdown/text template files and Google Docs-exported `.docx` files.
- Previews parsed fields, detected sections, target paper matches, block counts, raw-note append behavior, and duplicate imports before apply.
- Appends imported Raw Notes into the Reading Note and creates structured note blocks only after explicit confirmation.
- Refreshes only the BluePrint Reading Note metadata header after accepted metadata updates; note body sections are preserved.
- Clarifies that structured blocks are retrieval/project-link cards while the Reading Note is the main paper note.

### v1.0.1-doi-less-metadata

- Adds DOI-less metadata candidates for arXiv/preprint/workshop PDFs.
- Detects modern and old-style arXiv IDs from filenames and PDF/extracted text.
- Adds optional arXiv metadata lookup with graceful offline/network failure diagnostics.
- Applies fallback metadata only after preview, preserving existing non-empty fields unless replacement is explicitly selected.

### v1.0.0-foundation

- Marks the stable foundation release target.
- Adds foundation principles, roadmap, backlog, development workflow, and release checklist docs.
- Keeps the app local-first, single-user, and Streamlit-based.
- Updates the runtime version reference to `1.0.0`.

### v0.9.9

- Adds a read-only release-readiness smoke-check script.
- Adds v1.0 manual smoke-test and new-PC restore checklists.
- Clarifies fresh-clone setup, Backup Snapshot manifest expectations, and manual restore validation.
- Updates the unpublished v1.0 draft without claiming a release.

### v0.9.8

- Reorganizes Settings into System, Library Maintenance, External Services, and Backup.
- Standardizes maintenance and diagnostic labels without changing service behavior.
- Restructures README startup, feature, development, and limitation guidance.
- Adds an unpublished v1.0 release-note draft under `docs/release_notes/`.

### v0.9.7

- Added light/full Backup Snapshots with checksummed manifests.
- Added the read-only Library Health Check.

### v0.9.6

- Added copy-only Drive Inbox Import while keeping `papers/` canonical.

### v0.9.5

- Hardened Crossref requests, diagnostics, contact identity, and non-empty metadata overlays.

### v0.9.4

- Added preview/confirm Paper Hygiene with stable paper identity.

### v0.9.0-v0.9.3

- Added projects, project links, tag governance, and workflow safety cleanup.

### v0.8.x

- Added structured note blocks and editing while preserving Markdown notes.

### v0.7.x

- Added full-text extraction, cache diagnostics, and stale-cache recovery.

### v0.5-v0.6

- Added metadata enrichment, tag suggestions, and the Reader Workspace.

## Known Limitations

- Visual PDF highlighting, coordinate annotations, OCR, graph visualization, Zotero integration, and relation graphs are not implemented.
- Google Drive support is local-folder based only; there is no Drive API or OAuth integration.
- BluePrint Reading Note import is local file import only; there is no Google OAuth, Google Docs API, live sync, or export to Google Docs.
- Structured note blocks are separate retrieval/project-link cards, not a live-synced replacement for the Reading Note.
- Backup restore is manual and should be performed while the app is stopped.
- Crossref depends on internet, TLS certificates, proxy settings, and provider availability.
- Image-only or scanned PDFs may yield no extracted text because OCR is not included.
- Native Streamlit PDF rendering can vary by environment; the stable HTML viewer remains the default.

If Crossref reports an SSL/certificate problem, update the networking dependencies and check for TLS inspection:

```powershell
python -m pip install --upgrade requests urllib3 certifi
```
