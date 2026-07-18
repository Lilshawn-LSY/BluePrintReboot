# Mandatory Regression Validation Checklist

Required before and after Codex-assisted release work, including `v1.3.0-reader-pdf-readonly-vertical-slice`. Use disposable fixtures for automated checks and non-mutating access for approved runtime checks.

## v1.3.0 Reader/PDF Read-only Vertical Slice

- [x] Use only disposable index/PDF fixtures to test valid bytes, ranges, unknown papers, missing files, non-PDF paths, traversal, outside-root paths, and unavailable files.
- [x] Confirm the pre-existing health, library status, papers, and paper-detail response shapes remain unchanged and no write route is added.
- [x] Confirm the bridge allowlists only the exact PDF GET route, streams binary data, forwards Range, preserves safe response headers, and maps unavailable upstreams safely.
- [x] Confirm Paper Detail uses stable `paper_id` for Open Reader and the Reader uses only the same-origin PDF URL.
- [x] Confirm Reader source contracts include explicit loading, unknown, missing, unavailable, native-viewer fallback, archived, success, sidebar, and back-navigation behavior.
- [x] Confirm Reader contains no note editor, autosave, annotation, highlighting, tag/project/metadata write, upload, delete, or replacement action.
- [x] Run current v1.3.0 smoke 90/0/0 and final full pytest 496 passed.
- [x] Run deterministic `npm ci`, frontend lint, production build, 14 Node tests, and the full `dev_check.ps1 -WriteEvidence` gate.
- [x] Start disposable FastAPI fixtures and the frontend on IPv4 loopback only; inspect Papers, Paper Detail, Reader, native PDF display, stable-identity URL, and Back navigation without reading or retaining real metadata.
- [x] User-performed real-library validation confirms Papers, one existing Paper Detail, Open Reader, the correct managed PDF, title/citation context, stable-identity URL, Back navigation, and the absence of write controls without retaining private metadata.
- [x] User-performed same-origin bridge validation confirms HTTP 206, an exact 16-byte range body, safe headers, invalid-path rejection, and no filesystem-path exposure.
- [x] Confirm an unknown paper displays an explicit non-crashing state.
- [x] Stop FastAPI and confirm explicit Reader unavailable behavior and usable navigation; restart FastAPI and confirm Reader/PDF recovery.
- [x] Start Streamlit separately and confirm Dashboard, Library, Paper Detail, Reader Workspace, existing PDF viewing, and existing note visibility without an application exception or mutation action.
- [x] Stop all temporary services and confirm ports 3000, 8000, and 8501 are clear.
- [x] Run `git diff --check` and inspect status; no private data, runtime files, PDFs, notes, caches, dependencies, or evidence artifacts are included.

Current v1.3.0 results are recorded in `docs/release_notes/v1.3.0.md`; historical release counts must not be reused as current evidence.

## v1.2.2 Runtime and Release Evidence Closure

- [x] Run `.\scripts\frontend_setup.ps1 -NodeHome "C:\Users\Public\tools\node-v24.18.0-win-x64"` and confirm it uses `npm ci` without rewriting the dependency graph.
- [x] Run `.\scripts\dev_check.ps1 -NodeHome "C:\Users\Public\tools\node-v24.18.0-win-x64" -WriteEvidence` and record actual smoke, full pytest, frontend lint, and frontend test/build results.
- [x] Inspect `artifacts/validation-summary.json` for schema/timestamp, Git state, runtime versions, four phase states, and full scope; confirm it contains no private paths, environment values, or command output.
- [x] Run focused launcher, workflow, version, release-note, and tracker-handoff contracts.
- [x] Run `git diff --check` and `git status --short`; confirm no user data, dependency directory, cache, or evidence artifact is staged.
- [x] Start FastAPI before the portable-Node frontend and open exactly `http://127.0.0.1:3000`.
- [x] Inspect local-only listener addresses; check Dashboard, Library, Papers, bridge/query behavior, API-offline navigation, API recovery, and separate Streamlit launch.
- [x] Check one existing Paper Detail route in the v1.2.2 read-only shell without recording private paper metadata.
- [ ] Record GitHub Actions as verified only with a relevant hosted conclusion and run URL.

Automated and manual v1.2.2 results are recorded in `docs/release_notes/v1.2.2.md`; v1.2.1 counts are historical and must not be reused as current evidence.

## v1.0.26 Focused Manual Validation

The user reported Sections A through H passed. The prior `StreamlitAPIException` is fixed, Save convergence passed, and navigation discard is accepted.

- [x] Manual tag on a saved note updates index, Reader metadata, and Reading Note header.
- [x] Selected suggested tag on a saved note does the same.
- [x] Manual tag and suggested tag on a dirty draft preserve the exact unsaved body, keep the draft dirty, and never write it before Save.
- [x] Same-paper metadata reruns preserve the dirty draft; switching papers discards it without writing, and returning reloads the saved note.
- [x] Save after pending metadata refresh persists the latest canonical header and latest body without a widget-state exception.
- [x] Browser refresh and application restart restore only explicitly saved content.
- [x] Edit metadata and Metadata Assist still converge canonical note headers.
- [x] Active paper selection and PDF viewing remain usable; Streamlit full rerenders are accepted behavior.

Manual evidence: user-reported Sections A-H passed; detailed tester/date/browser fields not supplied in repository.

## v1.0.25 Manual Lifecycle Validation

- [x] Export a corrupt critical-state recovery copy and confirm the original bytes remain unchanged and no quarantine action is offered.
- [x] Export and explicitly quarantine a disposable corrupt cache; confirm no empty cache is recreated.
- [x] Restore the verified quarantine copy, then confirm a destination conflict refuses overwrite.
- [x] Ignore one unindexed same-hash duplicate, confirm it moves to informational records, then Unignore it.
- [x] Archive and unarchive a disposable paper; confirm status, priority, `paper_id`, PDF path/bytes, note, blocks, links, and caches do not change.
- [x] Confirm archived papers are hidden by default, explicitly viewable/openable, and still included in Health Check.

## 1. Fresh Runtime

- [ ] Clone the repository into a new directory, or confirm the working tree is clean before validation begins.
- [ ] Create and activate a virtual environment.
- [ ] Install base dependencies with `python -m pip install -r requirements.txt`.
- [ ] Optionally install `requirements-optional.txt` only when validating optional extraction support.
- [ ] Confirm `.venv/`, `papers/`, `notes/`, `data/paper_index.csv`, `config.yaml`, `.streamlit/secrets.toml`, and personal backup/export archives are not staged for Git.

## 2. Automated Checks

- [ ] Run `.\scripts\dev_check.ps1 -NodeHome <portable-node-directory>` and confirm the full Python and frontend gate completes successfully.
- [ ] Treat `.\scripts\dev_check.ps1 -PythonOnly` as partial validation, never as release qualification.
- [ ] If the script cannot be used, run `python scripts/smoke_check.py` and confirm zero failures.
- [ ] If the script cannot be used, run `python -m pytest -q` and confirm the full suite passes.
- [ ] If the script cannot be used, run `npm run lint` and `npm test` from `frontend/` with Node 22.13.0 or newer.
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

Completion was reported by the user before v1.0.26 work. Detailed tester/date/browser fields were not supplied in this repository.

- [x] Initial disk load shows Saved.
- [x] Editing the note shows Unsaved changes; explicit Save returns it to Saved.
- [x] Dirty Reload preserves the exact draft and presents Keep/Discard choices.
- [x] Keep draft preserves the exact unsaved text.
- [x] Discard changes and reload restores disk text and updates the baseline.
- [x] Metadata-header refresh preserves the latest body; a dirty refreshed draft remains dirty until Save.
- [x] Same-paper reruns preserve the active draft; switching papers discards the previous unsaved draft and returning reloads saved disk text.
- [x] Tag, reading settings Apply, toolbar, project-link, profile, and structured-block actions preserve the active paper draft.
- [x] Browser refresh and application restart restore only explicitly saved text.
- [x] Reading status and priority update together only after **Apply reading settings**; unchanged Apply performs no write.
- [x] PDF renderer selection remains stable for each paper.
- [x] PDF viewing remains usable after Reader actions; any full rerender is recorded as accepted Streamlit behavior.
- [x] Missing-PDF and large-PDF guidance remain clear and non-destructive.

Manual evidence: user-reported complete before v1.0.26; detailed fields not supplied in repository.

## 11. Final Safety

- [ ] Create a disposable Backup Snapshot and run `.\.venv\Scripts\python.exe scripts\verify_snapshot.py <snapshot.zip>`; confirm it passes without extracting files.
- [ ] Confirm Reading Note creation, explicit save, and metadata-header refresh use atomic replacement and preserve the old file on simulated replacement failure.
- [ ] Re-run `git status --short`.
- [ ] Confirm no private user data, local secrets, PDFs, personal notes, runtime index files, caches, backup archives, or exports are staged or committed.
- [ ] Record the smoke-check summary, pytest result, platform, Python version, and Streamlit version in the release notes or release handoff.
