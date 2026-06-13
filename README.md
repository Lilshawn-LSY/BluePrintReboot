# BluePrintReboot

BluePrintReboot is a local-first personal research paper library app.

## v0.3 DOI and Crossref Metadata Assist

- Scans PDF files placed in `papers/`.
- Creates and updates `data/paper_index.csv`.
- Shows indexed papers in a Streamlit Library page.
- Opens a selected paper in Paper Detail.
- Creates, opens, edits, and saves one Markdown note per paper in `notes/`.
- Adds local manual metadata fields: title, authors, year, journal, DOI, tags, status, and reading priority.
- Migrates existing v0.1 index CSV files by adding missing metadata columns.
- Preserves manually edited metadata when PDFs are rescanned.
- Adds Library search and filters for status, reading priority, and tag text.
- Adds optional Crossref lookup by DOI with preview before applying metadata.
- Tracks metadata provenance with source, confidence, and checked timestamp.
- Keeps all user data local.

Metadata is stored locally in `data/paper_index.csv`. That file is ignored by git.
Crossref lookup requires internet, but no API key. Fetched metadata is applied only after you review the preview and click `Accept Crossref Metadata`.

## Layout

- `app.py` - Streamlit entrypoint.
- `ui_streamlit/` - Streamlit UI code.
- `storage/` - Local CSV and note storage helpers.
- `ingest/` - PDF scanning helpers.
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
3. Open `Library` and use search or filters to narrow the table.
4. Select a paper and open it in `Paper Detail`.
5. Edit metadata in the `Metadata` section and press `Save Metadata`.
6. Press `Create/Open Note`.
7. Edit the Markdown note and press `Save Note`.

Library search matches title, filename, authors, journal, DOI, and tags. Filters can limit results by status, reading priority, or tag text.

## Crossref Assist

1. Enter a DOI in the Paper Detail metadata form.
2. Press `Save Metadata`.
3. Press `Lookup Crossref by DOI`.
4. Review the preview fields.
5. Press `Accept Crossref Metadata` to apply title, authors, year, journal, DOI, source, confidence, and checked timestamp.

Tags, status, reading priority, filename, filepath, notes, and added date are not changed by Crossref accept.

## Crossref Troubleshooting

Crossref lookup requires internet access but no API key. Manual metadata editing, scanning, Library filters, and notes still work offline.

If Windows shows an error like `WinError 10061`, the connection is being refused before the app can reach Crossref. Check firewall rules, proxy or VPN settings, corporate or school network restrictions, and whether the machine is offline. The Settings page includes `Test Crossref Connection` for a quick connectivity check.
