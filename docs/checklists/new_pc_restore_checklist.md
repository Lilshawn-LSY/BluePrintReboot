# Fresh Clone and New-PC Restore Checklist

This is the canonical clean-PC and disposable restore rehearsal sequence. Snapshot and target checks are automated and read-only; extraction, launch, inspection, and the final real clean-PC rehearsal are user-performed. BluePrintReboot does not provide automated restore.

## A. Prepare the Old Computer

- [ ] Stop editing notes and metadata during backup preparation.
- [ ] Run **Library Health Check** and review every reported issue.
- [ ] Create a **Full Backup Snapshot** when practical.
- [ ] If using a light snapshot, separately copy the complete `papers/` directory.
- [ ] Copy the snapshot to storage that is independent of the old workspace.
- [ ] Keep the old library unchanged until the new computer is verified.

## B. Inspect the Snapshot

- [ ] Open the ZIP as an archive; do not extract it over the active old library.
- [ ] Run `.\.venv\Scripts\python.exe scripts\verify_snapshot.py <snapshot.zip>` and confirm it passes without extracting any file.
- [ ] Confirm `manifest.json` exists at the archive root.
- [ ] Confirm expected index, project, note, note-block, and tag files are listed.
- [ ] For a full snapshot, confirm managed PDFs are listed under `papers/`.
- [ ] For a light snapshot, confirm `includes_pdfs` is `false` and the PDF count is zero.

### Manifest Expectations

`manifest.json` should contain:

- `created_at` - UTC snapshot timestamp.
- `app_version` - BluePrintReboot version that created the snapshot.
- `snapshot_type` - `light` or `full`.
- `includes_pdfs` - boolean PDF inclusion policy.
- `included_files` - entries containing `path`, `size_bytes`, and `sha256`.
- `counts` - `included_files`, `index_rows`, `projects`, `project_links`, `notes`, `note_block_files`, and `pdfs`.

The archive should not contain `.git/`, `.venv/`, `venv/`, `.pytest_cache/`, `__pycache__/`, previous `exports/`, or secrets.

## C. Fresh Clone on the New Computer

Open PowerShell and run:

```powershell
git clone <repository-url> BluePrintReboot
cd BluePrintReboot
.\scripts\dev_setup.ps1
.\scripts\dev_check.ps1
```

- [ ] Confirm the smoke check reports zero failures.
- [ ] Do not launch Streamlit until the restore files are in place.

Optional MarkItDown support:

```powershell
python -m pip install -r requirements-optional.txt
```

This is the only canonical setup order: clone, enter the repository, run `dev_setup.ps1`, then `dev_check.ps1`. Setup failures stop with an actionable error and do not remove library data.

## D. Disposable Restore Rehearsal

Create an empty disposable directory outside the active repository, then run:

```powershell
.\.venv\Scripts\python.exe scripts\restore_check.py <snapshot.zip> <existing-empty-disposable-directory>
```

- [ ] Confirm `ready` is true before manually extracting anything.
- [ ] Confirm the helper leaves the original snapshot and empty target unchanged.
- [ ] Manually copy the snapshot if desired, then extract only into the disposable directory.
- [ ] Never point the rehearsal at the active repository, a non-empty directory, or real user data.

## E. Manual Restore on the New Computer

- [ ] Confirm Streamlit is stopped.
- [ ] Make a copy of any existing new-PC `data/`, `notes/`, and `papers/` content before replacing it.
- [ ] Extract the snapshot into the repository root while preserving relative paths.
- [ ] If the snapshot is light, copy the separately backed-up PDFs into `papers/`.
- [ ] Do not copy `.venv`, Git metadata, Python caches, or old machine-specific temporary files.
- [ ] Reconfigure environment variables such as `CROSSREF_MAILTO` and `BLUEPRINT_INBOX_DIR` for the new machine.

## F. Verify the Restored Library

```powershell
.\scripts\run_app.ps1
```

- [ ] Select **Scan papers** once.
- [ ] Run **Settings > Library Maintenance > Library Health Check**.
- [ ] Confirm indexed and physical PDF counts are plausible.
- [ ] Open several papers and verify metadata, PDF viewing, Markdown notes, and structured note blocks.
- [ ] Open Project Workspace and verify projects and links.
- [ ] Confirm `data/lifecycle_decisions.json`, when present, restored exact duplicate-ignore behavior and is included in the snapshot manifest.
- [ ] Confirm archived papers are hidden by default, visible in the archived view, and can be opened without moving PDFs.
- [ ] Check Tag Manager and tag configuration.
- [ ] Verify extracted text or re-extract it when caches were not included.
- [ ] Run Crossref Diagnostics if network enrichment will be used.

## G. Completion

- [ ] Resolve unexpected missing, unindexed, orphaned, duplicate, or noncanonical records.
- [ ] Re-run `.\scripts\dev_check.ps1` if this is a development machine.
- [ ] Keep the original snapshot until normal daily use is verified.
- [ ] Create a new snapshot on the new computer after verification.
- [ ] Record the real clean-PC rehearsal as user-performed; do not infer it from automated checks.
