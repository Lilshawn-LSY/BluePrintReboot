# Release Checklist

## v1.0.23-reader-state-machine-closure

- [x] Clean v1.0.22 baseline recorded: smoke 46 passed/0 warnings/0 failed; pytest 362 passed.
- [x] Reader note states, events, invariants, and transition precedence are documented.
- [x] Dirty Reload preserves the exact draft and offers Keep draft / Discard changes and reload.
- [x] Header refresh preserves the latest dirty body and does not mark later edits saved.
- [x] Whole-draft replacement precedes append, protects newer edits, and pending events are idempotent.
- [x] Paper-scoped state and non-note rerun preservation have automated coverage.
- [x] Final `dev_check.ps1` result is recorded in v1.0.23 release notes.
- [x] Streamlit manual smoke is performed or clearly recorded as not performed.
- [x] Git status confirms no runtime/user data, PDFs, notes, exports, caches, or secrets are included.
- [ ] Release tag is created and pushed only after explicit approval.

## v1.0.22-note-durability-and-validation-closure

- [x] Baseline `dev_check.ps1` recorded: smoke 46 passed/0 warnings/0 failed; pytest 356 passed.
- [x] Reading Note creation, save, and header refresh use shared same-directory atomic UTF-8 writes.
- [x] Replacement-failure tests prove old note bytes survive and temporary files are removed.
- [x] Existing-note creation remains non-overwriting, and Reader save baselines remain unchanged.
- [x] Read-only snapshot verification checks manifest policy, safe paths, presence, size, SHA-256, and counts using disposable ZIP fixtures.
- [x] Final `dev_check.ps1` result is recorded in v1.0.22 release notes.
- [x] Reader save/reload/pending-header-refresh manual smoke is completed and recorded, or clearly marked not performed.
- [x] Backup create plus read-only verifier smoke is completed and recorded.
- [x] Git status confirms no runtime/user data, PDFs, notes, exports, caches, or secrets are included.
- [ ] Release tag is created and pushed only after explicit approval.

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
