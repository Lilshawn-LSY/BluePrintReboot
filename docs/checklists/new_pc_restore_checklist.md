# Fresh Clone and New-PC Restore Checklist

This is the canonical clean-PC and disposable restore rehearsal sequence. Snapshot verification and readiness checks are read-only; archive extraction and the final clean-PC rehearsal remain user-performed. BluePrintReboot does not automate restore extraction.

## A. Fresh clone and runtime setup

Open PowerShell on the new computer:

```powershell
git clone <repository-url> BluePrintReboot
cd BluePrintReboot
.\scripts\dev_setup.ps1
.\scripts\frontend_setup.ps1 -NodeHome "C:\Users\Public\tools\node-v24.18.0-win-x64"
.\scripts\dev_check.ps1 -NodeHome "C:\Users\Public\tools\node-v24.18.0-win-x64"
```

- [ ] Python environment setup completes in the repository `.venv` from `requirements.txt`.
- [ ] Portable Node resolves from `-NodeHome`, or deliberately from `BLUEPRINT_NODE_HOME`/`PATH`, and reports Node 22.13.0 or newer plus npm.
- [ ] Frontend dependency setup uses committed `frontend/package-lock.json` and `npm ci`, not `npm install`.
- [ ] Smoke reports zero failures.
- [ ] Full pytest, frontend lint, and frontend build/tests pass.
- [ ] No setup script downloads Node, permanently changes PATH, or removes library data.

Optional MarkItDown support may be installed separately with `python -m pip install -r requirements-optional.txt`. A Streamlit-only machine may omit frontend setup and use `dev_check.ps1 -PythonOnly`, but that result is partial and not release-qualified.

## B. FastAPI and frontend launch contract

Start FastAPI first:

```powershell
.\scripts\run_api.ps1
```

Then launch the frontend in a second PowerShell window:

```powershell
.\scripts\run_frontend.ps1 -NodeHome "C:\Users\Public\tools\node-v24.18.0-win-x64"
```

- [ ] FastAPI launches on local-only `127.0.0.1:8000`.
- [ ] `GET /health` returns a successful response.
- [ ] `GET /papers` returns a successful response without writing data.
- [ ] The frontend launcher prints the canonical browser URL `http://127.0.0.1:3000`.
- [ ] The frontend launches on the configured deterministic port.
- [ ] `Get-NetTCPConnection -State Listen -LocalPort 3000` reports only IPv4 loopback `127.0.0.1`, not an external address.
- [ ] `[System.Net.Dns]::GetHostAddresses("localhost")` is inspected when diagnosing address-family behavior.
- [ ] `Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:3000" -TimeoutSec 10` succeeds after startup.
- [ ] No frontend or API listener uses `0.0.0.0`, bare `::`, a LAN address, or another external interface.

## C. Read-only frontend smoke and offline behavior

Use only existing records and do not save, edit, import, reconnect, restore, or run maintenance actions.

- [ ] Dashboard visibly renders in a browser.
- [ ] Library visibly renders in a browser.
- [ ] Papers visibly renders in a browser.
- [ ] One existing Paper Detail route visibly renders without recording private identifiers or metadata in evidence.
- [ ] Frontend-to-FastAPI bridge requests reach the local API.
- [ ] A read-only papers query forwards its query parameters correctly.
- [ ] After FastAPI is stopped, API-backed pages show an explicit unavailable state.
- [ ] Sidebar navigation remains functional while FastAPI is offline.
- [ ] FastAPI is restarted only if further read-only checks require it.

## D. Separate Streamlit regression

```powershell
.\scripts\run_app.ps1
```

- [ ] Streamlit launches separately on a local-only listener.
- [ ] Dashboard opens without an application error.
- [ ] A basic non-mutating Library/Paper navigation regression completes.
- [ ] No note, metadata, tag, project, snapshot, restore, import, delete, reconnect, or maintenance action is performed for this launch check.
- [ ] All temporary API, frontend, and Streamlit processes are stopped after validation.

## E. Prepare and manually verify the snapshot

- [ ] Stop editing notes and metadata during backup preparation.
- [ ] Run **Library Health Check** and review every reported issue.
- [ ] Create a **Full Backup Snapshot** when practical; for a light snapshot, separately copy the complete `papers/` directory.
- [ ] Copy the snapshot to storage independent of the old workspace.
- [ ] Open the ZIP as an archive without extracting over the active library.
- [ ] Run `.\.venv\Scripts\python.exe scripts\verify_snapshot.py <snapshot.zip>` and confirm read-only verification succeeds.
- [ ] Manually verify `manifest.json` exists at the archive root and lists the expected index, project, note, note-block, tag, and—when full—managed PDF files.
- [ ] Confirm the manifest records `created_at`, `app_version`, `snapshot_type`, `includes_pdfs`, per-file paths/sizes/SHA-256 values, and expected counts.
- [ ] Confirm the archive excludes `.git/`, `.venv/`, caches, previous exports, and secrets.

## F. Disposable restore readiness and manual extraction

Create an existing empty disposable directory outside the active repository, then run:

```powershell
.\.venv\Scripts\python.exe scripts\restore_check.py <snapshot.zip> <existing-empty-disposable-directory>
```

- [ ] Confirm `ready` is true and the helper leaves the snapshot and target unchanged.
- [ ] Confirm the active repository, non-empty directories, and real user-data directories are rejected as targets.
- [ ] Manually copy/extract only into the verified disposable directory if rehearsal is desired.
- [ ] Do not automate archive extraction.

## G. Manual restore on the new computer

- [ ] Confirm Streamlit and all other BluePrintReboot processes are stopped.
- [ ] Preserve any existing new-PC `data/`, `notes/`, and `papers/` content before replacement.
- [ ] Manually extract the snapshot into the repository root while preserving relative paths.
- [ ] For a light snapshot, manually copy the separately backed-up PDFs into `papers/`.
- [ ] Do not copy `.venv`, Git metadata, Python caches, or machine-specific temporary files.
- [ ] Reconfigure machine-local environment values such as `CROSSREF_MAILTO` and `BLUEPRINT_INBOX_DIR`.

## H. Verify the restored library

- [ ] Launch Streamlit and perform the user-approved scan once.
- [ ] Run **Settings > Library Maintenance > Library Health Check**.
- [ ] Confirm indexed and physical PDF counts are plausible.
- [ ] Open several papers and verify metadata, PDF viewing, Reading Notes, structured note blocks, projects, links, tags, archive state, and lifecycle decisions.
- [ ] Verify extracted text or rebuild it when excluded caches were not restored.
- [ ] Re-run the full release gate on a full development machine.
- [ ] Keep the original snapshot until normal daily use is verified.

## I. Completion evidence

- [ ] Record the manual snapshot verification result and date.
- [ ] Record the actual runtime, route, bridge, offline, Streamlit, and listener checks performed.
- [ ] Record the real clean-PC restore rehearsal as user-performed; do not infer it from automated checks.
- [ ] User-performed clean-PC restore rehearsal completed on a genuinely clean machine.
