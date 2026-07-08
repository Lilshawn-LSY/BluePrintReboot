# Release Checklist

## v1.0.21-reader-performance-polish

- [ ] Working tree is clean before release preparation begins.
- [ ] Confirm `.gitignore` still excludes runtime data: `data/`, `papers/`, `notes/`, `exports/`, `.venv/`, and caches.
- [ ] `python scripts\smoke_check.py` passes.
- [ ] `python -m pytest -q` passes.
- [ ] Repeated scan of unchanged indexed PDFs reuses stored hash metadata.
- [ ] Changed PDF size or modified time triggers a SHA-256 recompute.
- [ ] Reader note save, reload, skipped reload, and metadata header refresh feedback are smoke-tested.
- [ ] Metadata changes with an unsaved Reader draft do not overwrite draft body text.
- [ ] Duplicate and missing PDF repair remains explicit, deterministic, and confirmation-gated.
- [ ] Release notes include Reader UX changes, hash-performance changes, Streamlit feedback, validation commands, known limitations, and deferred items.
- [ ] Release tag is created and pushed only after explicit approval.

## v1.0.20-safety-release-foundation

- [ ] Working tree is clean before release preparation begins.
- [ ] Confirm `.gitignore` still excludes runtime data: `data/`, `papers/`, `notes/`, `exports/`, `.venv/`, and caches.
- [ ] `python scripts\smoke_check.py` passes.
- [ ] `python -m pytest -q` passes.
- [ ] Health Check surfaces corrupt JSON with path, issue, and recovery-safe next action in a disposable workspace.
- [ ] Health Check shows severity, meaning, and recommended next action for detected issue sections.
- [ ] Light Backup Snapshot manifest documents included files, excluded files, app version, checksums, counts, and cache exclusion policy.
- [ ] Full Backup Snapshot includes managed PDFs under `papers/` only after explicit confirmation.
- [ ] Backup snapshots exclude `.git`, `.venv`, `__pycache__`, package caches, secrets, logs, temporary files, and regenerable caches.
- [ ] Reader note editing, structured note blocks, and Reader PDF behavior are smoke-tested without UX changes.
- [ ] Release notes include changes, rationale, validation commands, manual smoke checklist, known limitations, and deferred items.
- [ ] Release tag is created and pushed only after explicit approval.

## v1.0.0-foundation

- [ ] Working tree is clean before release preparation begins.
- [ ] Dependencies install from a fresh virtual environment.
- [ ] `python -m pytest` passes.
- [ ] `python scripts/smoke_check.py` passes.
- [ ] `streamlit run app.py` launches.
- [ ] Dashboard opens.
- [ ] Library opens.
- [ ] Paper Detail opens.
- [ ] Reader Workspace opens.
- [ ] Settings opens.
- [ ] README version/status is updated.
- [ ] Release tag is created and pushed after explicit approval.
