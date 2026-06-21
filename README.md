# BluePrintReboot

## What is BluePrintReboot?

BluePrintReboot is a local-first research paper library built with Streamlit. It keeps PDFs, metadata, reading notes, structured note blocks, project links, tags, and extracted text on the local machine.

The canonical managed PDF directory is `papers/`. Paper identity is the stable `paper_id` stored in `data/paper_index.csv`; notes, note blocks, project links, and extracted-text caches remain attached to that identity even when a PDF filename changes.

## Current Status

Version **0.9.9** is the final pre-v1.0 readiness and documentation pass. The app remains intentionally local-first and single-user:

- Runtime library data is ignored by Git.
- GitHub stores the application code, not the personal paper library.
- Crossref is optional; core reading and organization workflows work offline.
- Maintenance actions use preview and confirmation where files or records can change.

## Quick Start

From a fresh clone in PowerShell:

```powershell
git clone <repository-url> BluePrintReboot
cd BluePrintReboot
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/smoke_check.py
streamlit run app.py
```

Add PDFs directly to `papers/`, then select **Scan papers** in the app. Open **Library** to choose a paper and continue in **Paper Detail**.

For optional MarkItDown PDF support:

```powershell
pip install -r requirements-optional.txt
```

## Core Features

### Library and Reader

- Recursive PDF scanning from the canonical `papers/` directory.
- Stable paper identities and a local CSV metadata index.
- Search and filtering by metadata, status, priority, and tags.
- Reader Workspace with PDF viewing, Markdown notes, status, priority, and tags.
- Structured note blocks for summaries, claims, methods, evidence, questions, ideas, and limitations.
- Full-text extraction with MarkItDown when available and `pypdf` fallback.
- SHA-256 cache freshness checks and safe stale-cache recovery.

### Metadata and Organization

- DOI extraction from PDFs.
- Crossref metadata preview and explicit acceptance with classified diagnostics.
- Manual metadata editing remains available when enrichment is incomplete or offline.
- Deterministic tag suggestions and canonical tag governance.
- Research projects linking papers and structured note blocks.
- Paper Hygiene recommendations using `{year}_{first_author}_{short_title}.pdf` without changing `paper_id`.

### Library Maintenance

Settings is organized into four sections:

- **System** - app/runtime information, workspace paths, extraction backends, and index details.
- **Library Maintenance** - Library Health Check, Tag Rules, Drive Inbox Import, and Paper Hygiene.
- **External Services** - Crossref Diagnostics, dependency versions, and proxy/network status.
- **Backup** - light/full Backup Snapshot controls and manifest summaries.

Library Health Check reports missing or unindexed PDFs, duplicate filenames and DOI values, incomplete metadata, orphan records, noncanonical paths, and stale extracted-text caches.

### Drive Inbox Import

`BLUEPRINT_INBOX_DIR` can point to a Google Drive for desktop synced folder such as `G:\My Drive\BluePrint\paper`. No Google Drive API or OAuth is used.

Inbox PDFs are candidates only. An explicit preview/confirm workflow copies one selected PDF into `papers/`, leaves the source untouched, and then uses the existing scanner/index workflow. Inbox paths are never persisted as managed paper paths.

### Backup and Moving Computers

Backup Snapshot creates timestamped ZIP files under `exports/`:

- **Light** - index, projects, links, notes, note blocks, tag configuration, and relevant local settings.
- **Full** - everything in a light snapshot plus managed PDFs from `papers/`.

Each archive contains `manifest.json` with the app version, timestamp, included files, SHA-256 checksums, and counts. Restore is manual in v0.9.9. See the [manifest expectations and new-PC restore checklist](docs/checklists/new_pc_restore_checklist.md).

Recommended move workflow:

1. Run Library Health Check on the old computer.
2. Create a full snapshot, or create a light snapshot and copy `papers/` separately.
3. Install BluePrintReboot on the new computer.
4. With the app stopped, extract the snapshot into the project root while preserving directory structure.
5. Start the app, scan papers, and run Library Health Check again.

### Crossref Configuration

Crossref polite-access contact resolution uses:

1. `CROSSREF_MAILTO`
2. `BLUEPRINT_CONTACT_EMAIL`
3. the built-in local default

Example:

```powershell
$env:CROSSREF_MAILTO = "researcher@example.edu"
```

Crossref enrichment requires the base dependencies `requests`, `urllib3`, and `certifi`.

## Project Structure

- `app.py` - Streamlit entry point.
- `ui_streamlit/` - application pages and workspace UI.
- `ingest/` - scanning, DOI, Crossref, tagging, and text-extraction helpers.
- `services/` - inbox import, filename hygiene, backup, health checks, and workflow orchestration.
- `storage/` - index, notes, note blocks, projects, links, and extracted-text caches.
- `config/` - contact/inbox helpers and user-editable tag configuration.
- `scripts/` - non-destructive readiness utilities.
- `docs/checklists/` - manual smoke-test and restore procedures.
- `tests/` - automated test suite.
- `papers/` - canonical managed PDF library; ignored by Git.
- `data/` - local metadata and caches; ignored by Git.
- `notes/` - Markdown reading notes; ignored by Git.
- `exports/` - snapshots and exports; ignored by Git.

## Development Commands

Run the non-destructive readiness check:

```powershell
python scripts/smoke_check.py
```

Run the complete automated test suite:

```powershell
python -m pytest
```

Run a focused test file:

```powershell
python -m pytest tests/test_library_health.py -q
```

The GitHub Actions workflow runs the full pytest suite on pushes to `main` and pull requests.

Manual release validation is documented in [docs/checklists/v1.0_smoke_test.md](docs/checklists/v1.0_smoke_test.md).

## Version History

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
- Backup restore is manual and should be performed while the app is stopped.
- Crossref depends on internet, TLS certificates, proxy settings, and provider availability.
- Image-only or scanned PDFs may yield no extracted text because OCR is not included.
- Native Streamlit PDF rendering can vary by environment; the stable HTML viewer remains the default.

See [docs/checklists/v1.0_smoke_test.md](docs/checklists/v1.0_smoke_test.md) for the complete pre-release manual verification pass.

If Crossref reports an SSL/certificate problem, update the networking dependencies and check for TLS inspection:

```powershell
python -m pip install --upgrade requests urllib3 certifi
```
