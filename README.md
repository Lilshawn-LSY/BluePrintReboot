# BluePrintReboot

BluePrintReboot is a local-first personal research paper library app.

## v0.1

- Scans PDF files placed in `papers/`.
- Creates and updates `data/paper_index.csv`.
- Shows indexed papers in a Streamlit Library page.
- Opens a selected paper in Paper Detail.
- Creates, opens, edits, and saves one Markdown note per paper in `notes/`.
- Keeps all user data local.

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
3. Open `Library`, select a paper, and open it in `Paper Detail`.
4. Press `Create/Open Note`.
5. Edit the Markdown note and press `Save Note`.
