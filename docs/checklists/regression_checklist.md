# Mandatory Regression Validation Checklist

Required before and after Codex-assisted release work, including the `v1.0.16-roadmap-release-evidence-sync` documentation pass. Use a disposable or non-sensitive workspace for manual checks. This checklist locks the current `v1.0.15-pdf-profile-extraction-repair` app baseline; it does not approve unrelated product behavior.

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
- [ ] Confirm running duplicate PDF hash review does not merge records, delete PDFs, remove index rows, or mutate notes/project links.
- [ ] With a disposable note file whose stem is not in `paper_index.csv`, confirm orphan note review shows `orphan note file` and preserve/reattach/export guidance.
- [ ] With a disposable note-block JSON file whose stem is not in `paper_index.csv`, confirm orphan note block review shows `orphan note block file` and does not offer deletion.
- [ ] With a disposable project link targeting a missing paper or missing note block, confirm orphan project link review shows `orphan project link` with a reason.
- [ ] Remove one disposable orphan project link only after explicit confirmation and confirm papers, PDFs, notes, note blocks, and index rows are unchanged.
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

## 5. Final Safety

- [ ] Re-run `git status --short`.
- [ ] Confirm no private user data, local secrets, PDFs, personal notes, runtime index files, caches, backup archives, or exports are staged or committed.
- [ ] Record the smoke-check summary, pytest result, platform, Python version, and Streamlit version in the release notes or release handoff.
