# BluePrintReboot

## What is BluePrintReboot?

BluePrintReboot is a local-first research paper library built with Streamlit. It keeps PDFs, metadata, BluePrint Reading Notes, structured note blocks, project links, tags, and extracted text on the local machine.

The canonical managed PDF directory is `papers/`. Paper identity is the stable `paper_id` stored in `data/paper_index.csv`; Reading Notes, note blocks, project links, and extracted-text caches remain attached to that identity even when a PDF filename changes.

## Current Status

Current release target: **v1.0.19-orphan-repair-and-storage-hardening**.

v1.0.18 and v1.0.19 harden file lifecycle maintenance: same-hash duplicate rows now have explicit keep/reconnect/ignore/remove controls, orphan notes, note blocks, and project links can be exported or repaired through confirmation-gated workflows, orphan extracted-text caches are surfaced, and extracted-text `.txt` cache writes use atomic replacement. The app preserves the local Tag Book, `PaperTextProfile`, and Reader PDF architecture; automatic duplicate merging, automatic deletion, data schema changes, FastAPI, frontend migration, packaging, external ontologies, and unrelated UI redesigns remain deferred.

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

Add PDFs directly to `papers/`, then select **Scan papers (local sync)** in the app. Open **Library** to choose a paper and continue in **Paper Detail** or **Reader Workspace**.

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

- Fast recursive PDF/index sync from the canonical `papers/` directory without default metadata enrichment.
- Stable paper identities and a local CSV metadata index.
- Search and filtering by metadata, status, priority, and tags.
- Reader Workspace with PDF viewing, the canonical BluePrint Reading Note, status, priority, and tags.
- Reading Note headers refresh from accepted paper metadata while preserving existing note body sections.
- Structured note blocks for summaries, claims, methods, evidence, questions, ideas, and limitations.
- BluePrint Reading Note template download and confirmed local import into the Reading Note and structured note blocks, with duplicate source imports blocked unless explicitly forced.
- Full-text extraction with MarkItDown when available and `pypdf` fallback.
- SHA-256 cache freshness checks and safe stale-cache recovery.

## Metadata/Tag Workflow

- Explicit DOI extraction from PDFs through metadata assist, separate from the normal local scan.
- Crossref metadata preview and explicit acceptance with classified diagnostics.
- DOI-less metadata fallback for arXiv/preprint/workshop PDFs, including arXiv ID detection, optional arXiv metadata lookup, and weak title guesses from PDF text or filename.
- Manual metadata editing when enrichment is incomplete or offline.
- Fallback metadata suggestions are previewed and user-applied; they do not claim perfect extraction.
- Deterministic tag suggestions and canonical tag governance through the local Tag Book.
- Minimal `PaperTextProfile` caches are derived from `paper_index.csv`, extracted-text abstract fallback, Reading Notes, and structured note blocks. They are rebuildable caches, not the source of truth.
- Tag Book configuration lives under `config/tag_book/`: `tag_book.json`, `method_lexicon.json`, `normalization_rules.json`, `blocked_terms.json`, and `candidate_patterns.json`.
- A canonical tag is the approved stored tag value; an alias is a matched spelling or phrase that resolves to a canonical tag; category and status control grouping and suggestion eligibility.
- Candidate tags are plausible new tags detected from metadata, filenames, and available extracted-text previews. They are preview-only until a user explicitly selects them as paper-local tags or promotes them later as canonical tags or aliases in Tag Manager.
- Tag suggestions include category, source, matched text, evidence, and reason. No LLM tagging, external ontology lookup, semantic synonym auto-merge, image parsing, or automatic retagging is performed.
- `normalization_rules.json` is loaded by the Tag Book helper for deterministic kebab-case normalization; full semantic normalization remains out of scope.
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
- **Library Maintenance** - Library Health Check, Tag Book, Drive Inbox Import, and Paper Hygiene.
- **External Services** - Crossref Diagnostics, dependency versions, and proxy/network status.
- **Backup** - light/full Backup Snapshot controls and manifest summaries.

Library Health Check reports missing or unindexed PDFs, duplicate filenames, duplicate PDF hashes, duplicate DOI values, incomplete metadata, orphan records, orphan extracted-text caches, noncanonical paths, and stale extracted-text caches. Duplicate PDF hash groups show `pdf_sha256`, indexed/unindexed counts, indexed `paper_id`, title, filename, filepath, status, and cheap note/project-link counts when available. Duplicate rows can be explicitly kept, reconnected to an unindexed same-hash PDF, ignored for the current session, or removed from `paper_index.csv` after confirmation; none of these actions auto-merge or delete PDFs, notes, note blocks, project links, or extracted text. Orphan note files and note block files can be exported, reattached to an indexed paper, or deleted only after explicit confirmation. Orphan project links can be exported, reattached, or unlinked without changing papers, PDFs, notes, note blocks, or index rows. Missing indexed PDFs can be explicitly reconnected to a selected PDF under `papers/` or removed from the index without deleting related user files.

`BLUEPRINT_INBOX_DIR` can point to a Google Drive for desktop synced folder such as `G:\My Drive\BluePrint\paper`. No Google Drive API or OAuth is used. Inbox PDFs are candidates only; the app uses an explicit preview/confirm workflow to copy one selected PDF into `papers/` and leaves the source untouched.

Backup Snapshot creates timestamped ZIP files under `exports/`:

- **Light** - index, projects, links, notes, note blocks, tag configuration, and relevant local settings.
- **Full** - everything in a light snapshot plus managed PDFs from `papers/`.

Each archive contains `manifest.json` with the app version, timestamp, included files, SHA-256 checksums, and counts. Restore remains manual. See the [new-PC restore checklist](docs/checklists/new_pc_restore_checklist.md).

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

### v1.0.19-orphan-repair-and-storage-hardening

- Detects orphan extracted-text cache files whose `paper_id` no longer exists in the index.
- Adds export, reattach, and confirmed delete workflows for orphan Reading Note files and structured note-block files.
- Adds export, reattach, and unlink wording for orphan project links while preserving link notes where possible.
- Writes extracted-text `.txt` cache files through same-directory temporary files, flush/fsync, and atomic replacement.
- Preserves notes, note blocks, project links, PDFs, extracted text, and runtime user data by default; destructive repair actions require confirmation.

### v1.0.18-file-lifecycle-duplicate-policy

- Adds a read-only file lifecycle diagnosis layer for missing indexed PDFs, unindexed PDFs, same-hash duplicate candidates, duplicate rows, and likely reconnect candidates.
- Adds explicit same-hash duplicate actions in Library Health Check: keep, reconnect, ignore, and confirmed index-row removal.
- Reconnect preserves the selected `paper_id` and updates only file identity fields.
- Duplicate index-row removal deletes only the selected row after confirmation and warns that orphan records may remain for the orphan repair workflow.
- Keeps same-hash duplicate import behavior conservative; no automatic merge is performed.

### v1.0.17-reader-pdf-stabilization

- Makes native Streamlit PDF rendering the default Reader PDF path.
- Demotes HTML/base64 PDF rendering to an explicit experimental fallback with browser, Streamlit, file-size, and security-policy warnings.
- Adds a conservative large-PDF warning and blocks automatic large-file HTML/base64 rendering unless explicitly confirmed.
- Provides an external-open/local-path option for PDFs that are slow, blocked, or too large for in-app rendering.
- Preserves active Reader paper context across note save, tag apply, status/priority updates, and Reader project-link actions.
- Does not change tag suggestion logic, PDF profile extraction, metadata extraction, data schemas, FastAPI, or frontend architecture.

### v1.0.16-roadmap-release-evidence-sync

- Syncs ROADMAP, BACKLOG, regression checklist, release notes, and README against the implemented v1.0.10 through v1.0.15 state.
- Records validation expectations and automated evidence for the current `main` branch.
- Adds no product features, runtime migrations, paper/library data changes, or app version bump.

### v1.0.15-pdf-profile-extraction-repair

- Adds deterministic PDF text cleanup for profile extraction, including soft-wrap joining, line-break dehyphenation, common header/footer removal, downloaded-from/page-number noise removal, and safer author superscript cleanup.
- Extends `PaperTextProfile` with authors, DOI, article type, section headings, and extraction warnings.
- Extracts Abstract and Keywords from cached/full extracted PDF text and uses them to fill blank Crossref preview fields without overwriting non-empty current metadata.
- Adds explicit `pdf_abstract`, `pdf_keywords`, and `pdf_section_headings` tag suggestion sources.
- Keeps generated candidate tags preview-only; no LLM/API tagging and no automatic candidate application.

### v1.0.14-tag-quality-hygiene

- Adds deterministic cleanup for generated tag candidate phrases, including leaked section/source prefixes and low-information boilerplate tails.
- Classifies generated candidates as high, medium, weak, or rejected, with source-aware scoring that prefers title, keywords, and note Methods evidence over generic abstract fragments.
- Rejects duplicate candidate phrases already covered by canonical tags or aliases and preserves alias suggestions for safer future promotion review.
- Separates known canonical suggestions from candidate phrase suggestions in the UI and keeps rejected phrases in a collapsed debug view.
- Still defers full PDF methods/results extraction, LLM/API tagging, and automatic candidate application.

### v1.0.13-paper-text-profile-minimal

- Adds a JSON-backed minimal `PaperTextProfile` cache in `data/paper_profiles/{paper_id}.json`.
- Builds profiles from existing paper metadata, conservative abstract fallback text, Reading Note sections, and structured note blocks.
- Lets tag suggestion use profile title, abstract, keywords, and note sections with source-aware evidence while preserving Tag Book canonical/alias matching.
- Adds a Reader Workspace rebuild action and compact profile summary.
- Defers PDF methods/results extraction and weak keyphrase mining; profiles remain derived and rebuildable, not source-of-truth records.

### v1.0.12-tag-book-v2

- Adds dedicated Tag Book configuration under `config/tag_book/`.
- Routes default canonical tag, alias, validation, and suggestion flows through the Tag Book while preserving legacy config files for compatibility.
- Adds evidence-bearing grouped tag suggestions and preview-only method candidates.
- Adds Tag Book validation for duplicate canonicals, alias conflicts, normalized alias conflicts, blocked terms, and inactive statuses.
- Keeps paper, note, note-block, project, and project-link storage schemas unchanged.

### v1.0.11-scan-enrich-import-guard

- Keeps normal paper scanning focused on local PDF discovery, path/hash sync, and index row updates.
- Moves DOI extraction and Crossref lookup behind explicit metadata assist actions instead of the default scan path.
- Preserves existing DOI, metadata, tags, notes, note blocks, project links, and extracted-text data during cheap scans.
- Blocks duplicate external note imports at the service layer by default.
- Adds a deliberate force re-import path in the Streamlit import UI for intentional duplicate external note imports.

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
- Native Streamlit PDF rendering is the default Reader path, but rendering can still vary by environment.
- The HTML/base64 PDF viewer is an explicit experimental fallback and may fail depending on browser, Streamlit, file size, or local security policy.
- Large PDFs are warned before rendering; large-file HTML/base64 fallback requires explicit confirmation.
- Same-hash duplicate rows are never auto-merged; users must choose keep, reconnect, ignore, or confirmed index-row removal.
- Orphan repair can reattach/export/unlink/delete supported records, but archive lifecycle and corrupt-cache quarantine remain deferred.

If Crossref reports an SSL/certificate problem, update the networking dependencies and check for TLS inspection:

```powershell
python -m pip install --upgrade requests urllib3 certifi
```
