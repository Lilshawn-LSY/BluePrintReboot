# Mandatory Regression Validation Checklist

Required before and after Codex-assisted release work, including `v1.0.6-missing-pdf-repair-workflow`. Use a disposable or non-sensitive workspace for manual checks. This checklist locks the current baseline; it does not approve unrelated product behavior.

## 1. Fresh Runtime

- [ ] Clone the repository into a new directory, or confirm the working tree is clean before validation begins.
- [ ] Create and activate a virtual environment.
- [ ] Install base dependencies with `python -m pip install -r requirements.txt`.
- [ ] Optionally install `requirements-optional.txt` only when validating optional extraction support.
- [ ] Confirm `.venv/`, `papers/`, `notes/`, `data/paper_index.csv`, `config.yaml`, and `.streamlit/secrets.toml` are not staged for Git.

## 2. Automated Checks

- [ ] Run `python scripts/smoke_check.py` and confirm zero failures.
- [ ] Run `python -m pytest -q` and confirm the full suite passes.

## 3. Streamlit Baseline

- [ ] Run `streamlit run app.py` and confirm the app launches.
- [ ] Open Dashboard and confirm it renders without errors.
- [ ] Run a Library scan with non-sensitive sample PDFs and confirm the paper listing renders.
- [ ] Open Paper Detail for a sample paper.
- [ ] Open Reader Workspace for a sample paper, save a disposable note edit, reload, and confirm it persists.
- [ ] Open Tag Manager and confirm canonical, alias, unknown, and unused tag views render.
- [ ] Open Project Workspace and confirm project listing/linking controls render.
- [ ] Open Settings and run Library Health Check.
- [ ] If external note import is present, open the import preview with a disposable Markdown/text or Google Docs-exported `.docx` note and confirm no import is applied before explicit confirmation.

## 4. Final Safety

- [ ] Re-run `git status --short`.
- [ ] Confirm no private user data, local secrets, PDFs, personal notes, or runtime index files are staged or committed.
- [ ] Record the smoke-check summary, pytest result, platform, Python version, and Streamlit version in the release notes or release handoff.
