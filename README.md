# BluePrintReboot

BluePrintReboot is a local-first personal research paper library app built with Streamlit.

## v0.5 Metadata Enrichment Workflow

- Scans PDF files placed in `papers/`.
- Creates and updates `data/paper_index.csv` while preserving user-edited metadata.
- Stores metadata locally, including title, authors, year, journal, DOI, abstract, keywords, tags, status, reading priority, and extraction provenance.
- Extracts DOI text with `pypdf` first.
- Falls back to optional `MarkItDown` PDF conversion when available.
- Provides one primary `Enrich Metadata` action in Paper Detail.
- Saves a detected DOI only when the paper does not already have one.
- Looks up Crossref metadata by DOI and shows a preview before applying it.
- Keeps Crossref accept explicit; fetched metadata is not automatically applied.
- Suggests tags with deterministic keyword rules and merges accepted suggestions without removing existing tags.
- Shows extraction backend status in Settings.

All paper metadata is stored in `data/paper_index.csv`. That file is ignored by git. Notes are stored as Markdown files in `notes/`.

Crossref lookup requires internet access but no API key. PDF scanning, DOI extraction, manual metadata editing, tag suggestion, and notes work locally.

## Optional MarkItDown Fallback

The base app uses `pypdf`. To enable the MarkItDown fallback:

```powershell
pip install -r requirements-optional.txt
```

The optional file currently installs:

```text
markitdown[pdf]
```

## Layout

- `app.py` - Streamlit entrypoint.
- `ui_streamlit/` - Streamlit UI code.
- `ingest/` - PDF scanning, DOI extraction, Crossref helpers, and tag suggestion.
- `storage/` - Local CSV and note storage helpers.
- `tests/` - Test suite.
- `data/`, `papers/`, `notes/`, `exports/` - Local workspace directories.

## Run

```powershell
pip install -r requirements.txt
streamlit run app.py
```

## Test

```powershell
python -m pytest
```

## Usage

1. Put PDF files into `papers/`.
2. Run the app and press `Scan papers`.
3. Open `Library` and select a paper.
4. Open it in `Paper Detail`.
5. Press `Enrich Metadata`.
6. Review detected DOI, extraction source, save status, and Crossref lookup status.
7. Review the Crossref preview and press `Accept Crossref Metadata` only if it is correct.
8. Review suggested tags and press `Accept Suggested Tags` if useful.
9. Edit manual fields or notes whenever needed.

## Metadata Assist

`Enrich Metadata` uses the saved DOI if one exists. If no DOI is saved, it attempts PDF DOI extraction and saves the detected DOI only when the DOI field is empty. If a DOI is available, it tries Crossref lookup and stores the result in the preview table.

Manual DOI correction remains available in the metadata form. Advanced manual Crossref lookup is still available from Paper Detail.

## Tag Suggestions

Tag suggestion uses the editable local rulebook at `config/tag_rules.json`. Each canonical tag has a category, aliases, and a weight. Suggestions can come from title, abstract, keywords, journal, filename, Crossref subjects, markdown text, and future OpenAlex or Semantic Scholar fields when those fields are present.

Suggested tags are never applied automatically. Press `Accept Suggested Tags` to merge them into the paper's existing tags. Existing user tags are preserved and duplicates are skipped.

### v0.5.3 Tag Suggestion Hotfix

Tag suggestions now use unsaved metadata form input and Crossref preview metadata before those values are saved or accepted. The Suggested Tags area includes a compact `Tag suggestion input` expander for debugging which fields are being used. The rulebook aliases include more common scientific spellings such as `scRNA-seq`, single-cell RNA sequencing, and machine-learning/deep-learning variants.

## Tag Rule Maintenance

`config/tag_rules.json` is editable. Settings validates the rulebook and reports issues such as missing fields, duplicate aliases, invalid weights, and non-normalized tag names.

Settings also audits the current library tags. Unknown tags and unused rulebook tags are reported for review, but BluePrintReboot does not automatically change existing user tags.

## Settings

Settings shows:

- Local workspace paths.
- Current CSV index schema.
- Extraction backend status for `pypdf` and `markitdown`.
- Crossref connectivity test and proxy environment hints.

## Crossref Troubleshooting

Crossref lookup is optional. If lookup fails because of SSL inspection, proxy, certificate, DNS, firewall, or timeout issues, local paper management still works. You can paste or edit DOI and metadata manually.
