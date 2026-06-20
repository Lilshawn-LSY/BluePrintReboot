# BluePrintReboot

## Overview

BluePrintReboot is a local-first personal research paper library built with Streamlit. It scans local PDFs, maintains a CSV paper index, supports Markdown and structured reading notes, and caches extracted full text beside the local library data.

Paper metadata is stored in `data/paper_index.csv`, Markdown notes are stored in `notes/`, structured note blocks are stored in `data/note_blocks/`, and extracted text is stored under `data/extracted_text/`. These user-generated files are ignored by git.

PDF management, DOI extraction, manual metadata editing, tag suggestions, notes, and full-text extraction work locally. Crossref lookup is optional and requires internet access, but no API key.

## Current Features

- Dashboard counts for papers, reading status, priority, DOI coverage, Crossref metadata, and notes.
- Recursive PDF scanning from `papers/` with stable paper IDs.
- Local CSV metadata index that preserves user-edited fields across rescans.
- Search and filtering by metadata, reading status, priority, and tags.
- DOI detection with `pypdf` and an optional MarkItDown fallback.
- Explicit Crossref preview and acceptance instead of automatic metadata replacement.
- Deterministic tag suggestions using `config/tag_rules.json`.
- Reader Workspace with a local PDF viewer, Markdown notes, note templates, tags, reading status, and priority controls.
- JSON-backed structured note blocks for summaries, claims, methods, evidence, questions, ideas, and limitations.
- Stable HTML PDF rendering by default, with an optional native Streamlit PDF viewer and automatic fallback.
- User-triggered full-text extraction with MarkItDown when available and `pypdf` fallback.
- Full-text cache status, diagnostics, preview, forced re-extraction, and cache clearing.
- SHA-256 stale-cache detection with automatic refresh when a changed PDF can be extracted successfully.
- Cache-safe recovery that preserves previous usable text when re-extraction fails.

Visual PDF highlighting, coordinate annotations, mouse-selection capture, project linking, graph visualization, Zotero integration, and relation schemas are not yet implemented.

## Quick Start

Install the base dependencies:

```powershell
pip install -r requirements.txt
```

Run the app:

```powershell
streamlit run app.py
```

Run the test suite:

```powershell
python -m pytest
```

`requirements.txt` includes `streamlit[pdf]`. The Reader Workspace still defaults to the stable HTML viewer because native component support can vary by environment.

### Optional MarkItDown

The base app includes `pypdf`. Install the optional MarkItDown PDF support with:

```powershell
pip install -r requirements-optional.txt
```

The optional requirements file installs `markitdown[pdf]`. Full-text extraction prefers MarkItDown when available and falls back to `pypdf`. DOI detection tries `pypdf` first and then MarkItDown.

### Project Layout

- `app.py` - Streamlit entry point.
- `ui_streamlit/` - App pages and Reader Workspace UI.
- `ingest/` - PDF scanning, DOI handling, Crossref helpers, tag suggestions, and text extraction.
- `services/` - Full-text extraction workflow orchestration.
- `storage/` - CSV index, Markdown notes, structured note blocks, extracted-text cache, and workspace path helpers.
- `config/tag_rules.json` - Editable deterministic tag rulebook.
- `tests/` - Automated test suite.
- `data/` - Local index, structured note blocks, and extracted-text cache.
- `papers/` - Local PDF library.
- `notes/` - Markdown reading notes.
- `exports/` - Local export destination.

## Workflow

1. Put PDF files in `papers/`.
2. Start the app and select **Scan papers**.
3. Open **Library**, choose a paper, and open **Paper Detail**.
4. Use the Reader Workspace to view the PDF and continue editing its existing Markdown note.
5. Add structured note blocks when a summary, claim, method, evidence item, question, idea, or limitation should be stored as a separate record.
6. Select **Enrich Metadata** to detect a DOI and request a Crossref preview. Crossref metadata is applied only after **Accept Crossref Metadata** is selected.
7. Review suggested tags and accept them when useful. Existing tags are preserved and duplicates are skipped.
8. Select **Extract full text** to create or reuse a successful current cache. If the PDF hash has changed, BluePrintReboot attempts a fresh extraction. A successful result replaces the stale cache; a failed result preserves the previous usable text and remains marked stale.
9. Use **Re-extract full text** to force extraction or **Clear text cache** to remove the cached text and metadata.

Extracted text cache files are:

- `data/extracted_text/{paper_id}.txt` for text.
- `data/extracted_text/{paper_id}.json` for extraction metadata and the source PDF fingerprint.

Failed or empty initial extraction results are recorded for diagnostics but are not reusable. If recovery of an existing usable cache fails, the previous text and source fingerprint are preserved while the failed attempt is recorded separately. Older caches without a usable PDF hash remain reusable because their freshness cannot be determined reliably.

## Version Notes

### v0.8.0

- Introduces a validated structured note block schema and JSON-backed storage under `data/note_blocks/`.
- Adds a minimal Reader Workspace interface for viewing, creating, and deleting structured blocks.
- Keeps the existing Markdown note files and editor intact.

### v0.7.5

- Stabilizes cache safety by preserving previous usable text when stale-cache recovery fails.
- Makes the cache-status return schema consistent with and without a PDF path.
- Clarifies reusable, stale, missing, and failed-recovery states in Reader Workspace.

### v0.7.4

- Implemented stale-cache recovery using SHA-256 mismatch detection and automatic re-extraction for changed PDFs.
- Added Reader Workspace stale warnings and cache recovery tests.

### v0.7.1-v0.7.3

- Internal full-text extraction and cache workflow refactor steps.

### v0.7.0

- Added user-triggered full-text extraction, local text and metadata caches, diagnostics, previews, forced re-extraction, and cache clearing.

### v0.6.3

- Made the stable HTML PDF viewer the default and kept the native Streamlit viewer as an opt-in renderer with fallback.

### v0.6

- Added the reader-first workspace with PDF viewing, Markdown notes, structured Markdown templates, tags, reading status, and priority controls.

### v0.5

- Added metadata enrichment, DOI extraction, explicit Crossref acceptance, deterministic tag suggestions, and extraction backend status.

## Troubleshooting / Limitations

### Crossref lookup

Crossref is optional. SSL inspection, proxy settings, certificate errors, DNS failures, firewalls, rate limits, or timeouts can prevent lookup while local paper management continues to work. DOI and metadata fields can always be edited manually. Settings includes a Crossref connectivity check and sanitized proxy hints.

### PDF rendering

Use the default **Stable HTML viewer** if the native Streamlit PDF component is unavailable. The PDF debug panel reports the resolved path, file existence, size, selected renderer, attempted methods, final method, and native renderer errors.

### Full-text extraction

Open **Extraction debug** to inspect backend availability, attempted extraction methods, errors, character count, stale status, and current/cached PDF hashes. Scanned or image-only PDFs may produce no readable text without OCR, which is not currently included.

If a cache is marked stale, select **Extract full text** or **Re-extract full text**. If recovery fails, the previous extracted text is preserved and remains marked stale. If either the current or cached PDF hash is unavailable, BluePrintReboot does not mark the cache stale because there is no reliable mismatch to compare.

### Tag rules

Settings validates `config/tag_rules.json` and reports malformed rules, duplicate aliases, unknown library tags, and unused canonical tags. The app does not automatically rewrite existing user tags.
