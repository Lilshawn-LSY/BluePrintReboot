# Mandatory Regression Validation Checklist

Required before and after Codex-assisted release work, including `v1.0.25-lifecycle-and-recovery-closure`. Use a disposable or non-sensitive workspace for manual checks. This checklist locks the current Reader/PDF, lifecycle, storage-safety, and backup baseline; it does not approve unrelated product behavior.

## v1.0.25 Manual Lifecycle Validation

- [ ] Export a corrupt critical-state recovery copy and confirm the original bytes remain unchanged and no quarantine action is offered.
- [ ] Export and explicitly quarantine a disposable corrupt cache; confirm no empty cache is recreated.
- [ ] Restore the verified quarantine copy, then confirm a destination conflict refuses overwrite.
- [ ] Ignore one unindexed same-hash duplicate, confirm it moves to informational records, then Unignore it.
- [ ] Archive and unarchive a disposable paper; confirm status, priority, `paper_id`, PDF path/bytes, note, blocks, links, and caches do not change.
- [ ] Confirm archived papers are hidden by default, explicitly viewable/openable, and still included in Health Check.

## 1. Fresh Runtime

- [ ] Clone the repository into a new directory, or confirm the working tree is clean before validation begins.
- [ ] Create and activate a virtual environment.
- [ ] Install base dependencies with `python -m pip install -r requirements.txt`.
- [ ] Optionally install `requirements-optional.txt` only when validating optional extraction support.
- [ ] Confirm `.venv/`, `papers/`, `notes/`, `data/paper_index.csv`, `config.yaml`, `.streamlit/secrets.toml`, and personal backup/export archives are not staged for Git.

## 2. Automated Checks

- [ ] Run `.\scripts\dev_check.ps1` and confirm it completes successfully.
- [ ] If the script cannot be used, run `python scripts/smoke_check.py` and confirm zero failures.
- [ ] If the script cannot be used, run `python -m pytest -q` and confirm the full suite passes.
- [ ] Record the exact commands, command results, platform, Python version, and Streamlit version in the release notes or release handoff.

## 3. Streamlit Baseline

- [ ] Run `streamlit run app.py` or `.\scripts\run_app.ps1` and confirm the app launches.
- [ ] Open Dashboard and confirm it renders without errors.
- [ ] Run a Library scan with non-sensitive sample PDFs and confirm the paper listing renders.
- [ ] Open Paper Detail for a sample paper.
- [ ] Open Reader Workspace for a sample paper, save a disposable note edit, reload, and confirm it persists.
- [ ] Open Tag Manager and confirm canonical, alias, unknown, and unused tag views render.
- [ ] Open Project Workspace and confirm project listing/linking controls render.
- [ ] Open Settings and run Library Health Check.
- [ ] With disposable PDFs, confirm duplicate PDF hash review shows `indexed duplicate` for two indexed records with the same SHA-256.
- [ ] With a disposable indexed PDF and an unindexed copy, confirm duplicate PDF hash review shows `indexed + unindexed duplicate` and marks the unindexed file "Do not add to index yet; handle later."
- [ ] With two disposable unindexed copies, confirm duplicate PDF hash review shows `multiple unindexed duplicate`.
- [ ] Confirm duplicate PDF hash review never merges records or deletes PDFs automatically.
- [ ] With a disposable note file whose stem is not in `paper_index.csv`, confirm orphan note review shows `orphan note file` with export, reattach, and confirmed delete controls.
- [ ] With a disposable note-block JSON file whose stem is not in `paper_index.csv`, confirm orphan note block review shows `orphan note block file` with export, reattach, and confirmed delete controls.
- [ ] With a disposable project link targeting a missing paper or missing note block, confirm orphan project link review shows `orphan project link` with a reason.
- [ ] Unlink one disposable orphan project link only after explicit confirmation and confirm papers, PDFs, notes, note blocks, and index rows are unchanged.
- [ ] Exercise project, project-link, and note-block saves with disposable data and confirm JSON files remain valid after app reload.

## 4. v1.0.10 through v1.0.15 Focused Checks

- [ ] Confirm README Quick Start uses `.\scripts\dev_setup.ps1`, `.\scripts\dev_check.ps1`, and `.\scripts\run_app.ps1` as the preferred Windows path, with manual commands retained as fallback.
- [ ] With a disposable PDF containing DOI-like text, confirm **Scan papers (local sync)** does not populate DOI fields by default.
- [ ] From Paper Detail metadata assist, explicitly run DOI/Crossref lookup and confirm detected metadata is previewed before acceptance.
- [ ] Confirm a scan does not overwrite accepted manual DOI, title, authors, journal, tags, status, priority, notes, note blocks, project links, or extracted-text cache data.
- [ ] If external note import is present, open the import preview with a disposable Markdown/text or Google Docs-exported `.docx` note and confirm no import is applied before explicit confirmation.
- [ ] Import one disposable external note, then preview the same source again and confirm duplicate source import is blocked by default.
- [ ] Confirm duplicate external note import can proceed only after selecting the explicit force re-import control.
- [ ] Rebuild a `PaperTextProfile` for a disposable paper with cached extracted text and confirm the summary can show title, authors, DOI, abstract length, keywords, article type, section headings, note sections, and extraction warnings when available.
- [ ] With incomplete Crossref metadata and cached PDF profile text, confirm metadata gap-fill supplies blank preview fields such as abstract and keywords without automatically overwriting non-empty current metadata.
- [ ] Confirm PDF profile extraction is treated as readable-text front-matter extraction only; it does not claim OCR, image parsing, figure/table parsing, full methods/results extraction, or LLM/API tagging.
- [ ] In Paper Detail and Reader Workspace tag suggestions, confirm known canonical suggestions and generated candidate suggestions are visually separated.
- [ ] Confirm tag suggestion rows expose source visibility: category, source/source label, matched text, evidence/snippet, and reason where available.
- [ ] Confirm PDF-derived tag suggestions can identify `pdf_abstract`, `pdf_keywords`, or `pdf_section_headings` sources when profile data is available.
- [ ] Confirm rejected candidate phrases are non-selectable and remain separated from selectable suggestions.
- [ ] Confirm generated candidate tags are preview/select-only: leaving them unselected changes nothing; selecting one adds only a paper-local tag and does not promote it into the Tag Book automatically.

## 5. v1.0.17 Reader PDF Smoke Checks

- [ ] Open Reader Workspace for a disposable sample PDF and confirm **Native Streamlit PDF viewer** is selected by default.
- [ ] Confirm the HTML/base64 PDF viewer is labeled as an experimental fallback and is not selected by default.
- [ ] Select the experimental HTML/base64 fallback for a small disposable PDF and confirm the UI warns that it may fail depending on browser, Streamlit, file size, or security policy.
- [ ] Open a large disposable PDF above the configured threshold and confirm the Reader shows a large-PDF warning.
- [ ] With a large PDF selected, confirm the HTML/base64 fallback does not render automatically.
- [ ] With a large PDF selected, confirm HTML/base64 fallback renders only after explicit confirmation.
- [ ] Confirm the Reader exposes an external/local path option for opening the PDF outside the in-app viewer.
- [ ] Save a disposable Reading Note edit and confirm the same paper remains selected in Reader.
- [ ] Apply a manual or suggested Reader tag and confirm the same paper remains selected in Reader.
- [ ] Change reading status or priority and confirm the same paper remains selected in Reader.
- [ ] Link or unlink a paper/project or note-block/project relationship from the Reader context and confirm the app remains on the same Reader paper.
- [ ] Confirm no tag suggestion logic, PDF profile extraction behavior, metadata extraction behavior, data schema, FastAPI, or frontend architecture changes are introduced by this pass.

## 6. v1.0.18-v1.0.19 File Lifecycle And Orphan Hardening

- [ ] In Library Health Check, confirm same-hash duplicate groups expose indexed `paper_id`, filename, filepath, status, `pdf_sha256`, note-file count, note-block count, and project-link count where available.
- [ ] Select **Keep** for a disposable duplicate group and confirm no files or index rows change.
- [ ] Select **Ignore** for a disposable duplicate group and confirm no files or index rows change; the ignore state is session-only.
- [ ] For a disposable missing/renamed PDF row with a same-hash replacement under `papers/`, run reconnect and confirm the original `paper_id` remains unchanged while filename, filepath, and `pdf_sha256` update.
- [ ] Attempt a reconnect to a different SHA-256 replacement and confirm the mismatch is blocked until the explicit mismatch confirmation is selected.
- [ ] Remove a selected duplicate index row only after confirmation and confirm notes, note blocks, project links, PDFs, and extracted text remain on disk.
- [ ] After duplicate row removal, rerun Library Health Check and confirm any newly orphaned notes, blocks, or project links surface in the orphan repair sections.
- [ ] Export a disposable orphan Reading Note and confirm the export file contains recoverable note text.
- [ ] Reattach a disposable orphan Reading Note to an indexed paper and confirm the note content is preserved in the target note.
- [ ] Delete a disposable orphan Reading Note only after explicit confirmation.
- [ ] Export a disposable orphan note-block file and confirm the export file contains recoverable blocks.
- [ ] Reattach disposable orphan note blocks to an indexed paper and confirm block text, tags, and timestamps are preserved where possible.
- [ ] Delete a disposable orphan note-block file only after explicit confirmation.
- [ ] Export a disposable orphan project link and confirm the export contains project, target, paper, link type, note, and reason data.
- [ ] Reattach a disposable orphan project link to an indexed paper and confirm the link note is preserved.
- [ ] Unlink a disposable orphan project link only after explicit confirmation and confirm no paper, PDF, note, note-block, or index row is changed.
- [ ] Create disposable orphan extracted-text `.txt`/`.json` cache files and confirm Library Health Check reports `orphan extracted-text cache`.
- [ ] Trigger or unit-test extracted-text `.txt` cache replacement and confirm a failed/interrupted replacement preserves the previous cache file.
- [ ] Confirm destructive repair actions preserve user data by default and require explicit confirmation before removing an index row, note file, note-block file, or project link association.

## 7. v1.0.20 Storage, Health, And Backup Safety

- [ ] In a disposable workspace, corrupt one app-owned JSON file and confirm Health Check reports the affected path, issue, and recovery-safe action.
- [ ] Confirm corrupt JSON is not deleted, overwritten, or auto-repaired by running Health Check.
- [ ] Confirm Health Check issue sections show severity/category, meaning, and recommended next action.
- [ ] Create a light Backup Snapshot and inspect `manifest.json` for included files, excluded policy, checksums, counts, and app version.
- [ ] Confirm extracted-text and paper-profile caches are excluded from the snapshot and documented as regenerable.
- [ ] Confirm backup errors and health errors show concise main messages with developer details in expanders.

## 8. v1.0.21 Reader And Hash Performance Polish

- [ ] Re-run a scan with unchanged disposable PDFs and confirm existing rows are preserved without duplicate rows.
- [ ] Modify a disposable PDF and confirm the stored SHA-256, size, and modified time update after scan.
- [ ] With an unsaved Reader note draft, click **Reload** and confirm the exact draft is kept and Keep/Discard choices appear.
- [ ] Save a disposable Reader note and confirm the saved baseline can be reloaded.
- [ ] With an unsaved Reader note draft, edit metadata and confirm a header refresh is offered without overwriting the body text.
- [ ] Apply the pending header refresh explicitly and confirm user note body text remains.
- [ ] Confirm duplicate/missing PDF repair remains previewed, deterministic, and confirmation-gated.

## 9. v1.0.23 Reader Note State Machine

- [ ] Confirm the editor shows Saved for a clean draft and Unsaved changes after editing.
- [ ] Confirm Header refresh pending is visible when metadata refresh awaits explicit application.
- [ ] Choose Keep draft after dirty Reload and confirm the exact draft remains with no pending destructive action.
- [ ] Choose Discard changes and reload after dirty Reload and confirm disk text becomes both draft and baseline.
- [ ] Confirm tag, status, priority, profile, and project-link reruns preserve the active paper's dirty draft.
- [ ] Confirm no Reader action autosaves an unsaved draft.

## 10. v1.0.24 User-Performed Reader Validation

Record tester, date, browser, and result for each item. Leave unchecked when not performed.

- [ ] Initial disk load shows Saved.
- [ ] Editing the note shows Unsaved changes; explicit Save returns it to Saved.
- [ ] Dirty Reload preserves the exact draft and presents Keep/Discard choices.
- [ ] Keep draft preserves the exact unsaved text.
- [ ] Discard changes and reload restores disk text and updates the baseline.
- [ ] Metadata-header refresh preserves the latest body; a dirty refreshed draft remains dirty until Save.
- [ ] Paper A and Paper B drafts remain isolated when switching papers.
- [ ] Tag, reading settings Apply, toolbar, project-link, profile, and structured-block actions preserve the active paper draft.
- [ ] Browser refresh and application restart restore only explicitly saved text.
- [ ] Reading status and priority update together only after **Apply reading settings**; unchanged Apply performs no write.
- [ ] PDF renderer selection remains stable for each paper.
- [ ] PDF viewing remains usable after Reader actions; any full rerender is recorded as accepted Streamlit behavior.
- [ ] Missing-PDF and large-PDF guidance remain clear and non-destructive.

Manual evidence: tester __________ date __________ browser __________ result __________

## 11. Final Safety

- [ ] Create a disposable Backup Snapshot and run `.\.venv\Scripts\python.exe scripts\verify_snapshot.py <snapshot.zip>`; confirm it passes without extracting files.
- [ ] Confirm Reading Note creation, explicit save, and metadata-header refresh use atomic replacement and preserve the old file on simulated replacement failure.
- [ ] Re-run `git status --short`.
- [ ] Confirm no private user data, local secrets, PDFs, personal notes, runtime index files, caches, backup archives, or exports are staged or committed.
- [ ] Record the smoke-check summary, pytest result, platform, Python version, and Streamlit version in the release notes or release handoff.
