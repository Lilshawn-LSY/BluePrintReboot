# Development Workflow

## Roles

- Shawn: product owner and final reviewer.
- ChatGPT: planning, review, prompts, and release reasoning.
- Codex: implementation and test execution.
- GitHub: source of truth for code, reviews, pull requests, releases, and tags.

## Setup

Python-only setup remains available for a Streamlit-only machine:

```powershell
.\scripts\dev_setup.ps1
```

For the complete repository, install Python and lock-file-pinned frontend dependencies together:

```powershell
.\scripts\dev_setup.ps1 -IncludeFrontend -NodeHome "C:\Users\Public\tools\node-v24.18.0-win-x64"
```

If Python is already configured, run only the deterministic frontend setup:

```powershell
.\scripts\frontend_setup.ps1 -NodeHome "C:\Users\Public\tools\node-v24.18.0-win-x64"
```

The shared resolver selects Node in this order: explicit `-NodeHome`, `BLUEPRINT_NODE_HOME`, then `node.exe` plus `npm.cmd` on `PATH`. Both executables are required and Node must be at least 22.13.0. The scripts do not download Node or permanently change `PATH`. Frontend setup always uses `npm ci`, never `npm install`.

## Canonical validation

The default check is the release-qualified full-stack gate:

```powershell
.\scripts\dev_check.ps1 -NodeHome "C:\Users\Public\tools\node-v24.18.0-win-x64"
```

It runs, in order, `python scripts/smoke_check.py`, full `python -m pytest`, `npm run lint`, and `npm test` (one frontend build followed by rendered-shell and bridge tests). Add `-WriteEvidence` to write the ignored, machine-readable `artifacts/validation-summary.json`.

Use `-PythonOnly` only when frontend validation is deliberately unavailable:

```powershell
.\scripts\dev_check.ps1 -PythonOnly
```

This is explicitly a **PARTIAL VALIDATION** result and is not release-qualified. `-SmokeOnly` is also partial. A normal full check never silently skips missing Node or frontend dependencies.

## Standard flow

Implement the bounded change on a review branch. Before review, run the full gate, inspect `git diff`, and run `git diff --check` plus `git status --short`. Commit, push, merge, and tag only with explicit approval.

GitHub Actions mirrors the gate with independent Python 3.12 and Node 22.13.1 jobs. Neither job requires a live personal library or a running local API.

## Launch checks

Start Streamlit with `.\scripts\run_app.ps1`. For the read-only web shell, start `.\scripts\run_api.ps1`, then in another window run:

```powershell
.\scripts\run_frontend.ps1 -NodeHome "C:\Users\Public\tools\node-v24.18.0-win-x64"
```

Manual browser checks remain separate from automated validation and must not be marked complete unless performed.

## Restore guidance

Use `docs/checklists/new_pc_restore_checklist.md` for clean-PC setup and restore rehearsal. The old project-level `backup_guideline.txt` is superseded by that checklist. Restore remains manual and should use a copied snapshot plus a disposable target; validation scripts do not mutate personal library data.
