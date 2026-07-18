# Release Checklist

## v1.3.0-reader-pdf-readonly-vertical-slice

- [x] `GET /papers/{paper_id}/pdf` resolves only an indexed paper and never accepts a filesystem path from the request.
- [x] PDF resolution remains inside the canonical managed papers directory and rejects missing, non-file, non-PDF, escaped, or otherwise unsafe paths without exposing an absolute path.
- [x] PDF delivery is GET-only, streamed as `application/pdf`, presented inline, and supports browser byte ranges through the response implementation.
- [x] The same-origin bridge allowlists only the exact PDF route, forwards Range, streams binary bytes, and preserves only safe PDF response headers.
- [x] Paper Detail exposes an Open Reader action based on stable `paper_id`, with an unavailable state when no managed PDF reference exists.
- [x] `/papers/{paper_id}/reader` provides title/citation context, back navigation, native PDF display, explicit loading/missing/offline/error states, and no write controls.
- [x] Notes and all write, metadata, PDF-maintenance, and recovery workflows remain in Streamlit.
- [x] Focused disposable-fixture API and frontend tests pass.
- [x] Current v1.3.0 smoke 90/0/0, final full pytest 496 passed, deterministic frontend setup, lint, build, 14 Node tests, and full release gate are recorded.
- [x] Disposable read-only API/frontend browser validation and API-offline recovery are recorded without private library metadata.
- [x] User-performed local-only FastAPI/frontend launch and listener validation passed with the expected v1.3.0 runtime diagnostics and no external listener.
- [x] User-performed real-library Papers, Paper Detail, Open Reader, correct managed PDF, title/citation, stable-identity URL, Back navigation, and no-write-control validation passed without retaining private metadata.
- [x] User-performed same-origin PDF bridge validation passed for HTTP 206, an exact 16-byte range body, safe representation headers, invalid-path rejection, and no filesystem-path exposure.
- [x] User-performed unknown-paper, FastAPI-offline navigation, restart recovery, and Reader/PDF recovery validation passed.
- [x] A separate user-performed Streamlit regression passed for Dashboard, Library, Paper Detail, Reader Workspace, existing PDF viewing, and existing note visibility without an application exception or mutation action.
- [x] Temporary frontend, FastAPI, and Streamlit processes were stopped; ports 3000, 8000, and 8501 were clear after validation.
- [ ] A relevant GitHub-hosted CI run is verified after an approved commit and push.
- [ ] A user performs the clean-PC restore rehearsal on a clean machine.
- [ ] Commit is created only after explicit instruction.
- [ ] The feature branch is pushed only after explicit instruction.
- [ ] Pull Request is created only after explicit instruction.
- [ ] Merge is performed only after explicit instruction.
- [ ] Tag is created only after explicit instruction.
- [ ] Release is published only after explicit instruction.

## v1.2.2-runtime-and-release-evidence-closure

- [x] Implementation uses Vinext's supported `--hostname 127.0.0.1` argument and keeps the frontend local-only.
- [x] The launcher prints the configured bind address, port, canonical browser URL `http://127.0.0.1:3000`, Node version, npm version, Node source, and a post-launch probe.
- [x] `push` and `pull_request` remain in the primary workflow, and `workflow_dispatch` is defined locally for deliberate execution after the workflow is committed and pushed.
- [x] Python and frontend remain separate jobs requiring smoke, pytest, `npm ci`, lint, and frontend build/tests.
- [x] v1.2.1 historical evidence uses one controlled status per verification item.
- [x] Numeric version surfaces, current release name, release-note index, roadmap/backlog, and tracker handoff identify v1.2.2.
- [x] Focused launcher and release-contract tests pass and are recorded in v1.2.2 release notes.
- [x] Canonical `npm ci` frontend setup and the full `dev_check.ps1 -WriteEvidence` gate pass.
- [x] Independent smoke, full pytest, frontend lint, and frontend build/Node-test results are recorded with actual v1.2.2 counts.
- [x] FastAPI listener, direct requests, canonical frontend launcher/listener, and bridge/query behavior are manually checked.
- [x] Dashboard, Library, and Papers are visibly checked in a browser.
- [x] One existing Paper Detail route is visibly checked in the v1.2.2 read-only shell without retaining private paper metadata.
- [x] FastAPI-offline unavailable states and sidebar navigation are visibly checked in a browser.
- [x] Separate Streamlit launch/basic regression is performed without mutating library data.
- [x] GitHub Actions run `29639358889` for commit `5710dfaf2ec8e9a0212bc68d74f11ce573d87fe1` concluded successfully with successful Python and frontend jobs.
- [ ] A user performs the clean-PC restore rehearsal on a clean machine.
- [x] Commit `e26ee8c` was created by the user.
- [x] The feature branch was pushed to origin by the user.
- [x] Pull Request #1 was created.
- [ ] Merge is performed only after explicit instruction.
- [ ] Tag is created only after explicit instruction.
- [ ] Release is published only after explicit instruction.

## v1.2.1-full-stack-validation-gate

- [x] The implemented baseline is reconciled: v1.0.26 Streamlit/read contracts, v1.1.0-v1.1.2 read-only FastAPI routes, and the v1.2.0 frontend shell are current architecture.
- [x] Shared Node resolution prefers `-NodeHome`, then `BLUEPRINT_NODE_HOME`, then `PATH`, and enforces Node 22.13.0 plus both required executables.
- [x] Frontend dependency setup requires `package-lock.json` and runs `npm ci`; Python-only setup remains usable.
- [x] Default `dev_check.ps1` includes smoke, full pytest, frontend lint, and frontend test/build without duplicate builds.
- [x] `-PythonOnly` and `-SmokeOnly` are prominent partial, non-release-qualified modes.
- [x] `-WriteEvidence` is opt-in, ignored, machine-readable, and excludes command output and private paths.
- [x] Bridge tests cover exact allowlisting, query forwarding, upstream 404, generic 503 mapping, network failure, and absence of write methods.
- [x] GitHub Actions has independent Python 3.12 and Node 22.13.1 jobs with lock-file caching and `npm ci`.
- [x] Exact local smoke, pytest, frontend lint, frontend build/test, diff, and status results are recorded in v1.2.1 release notes.
- [ ] Manual API/frontend/Streamlit launch checks are recorded only if actually performed.
- [ ] Commit, push, merge, tag, and release occur only after explicit instruction.

## v1.0.26-streamlit-finalization-api-contract-freeze

- [x] Clean v1.0.25 baseline recorded: smoke 49 passed/0 warnings/0 failed; pytest 396 passed.
- [x] Reader manual/suggested tags use the shared metadata coordinator and converge with Reading Note headers.
- [x] Dirty drafts remain unsaved, paper-scoped, and dirty through metadata refresh; explicit Save converges header and body.
- [x] Edit metadata, DOI, DOI-less, selected tags, and Crossref acceptance use the shared coordinator.
- [x] Five JSON-safe, non-mutating read contracts are frozen without API routes.
- [x] Snapshot/disposable-target readiness validation is read-only and rejects unsafe or non-empty targets.
- [x] Prior v1.0.24 Reader and v1.0.25 lifecycle manual completion is recorded from the user's report.
- [x] Focused architecture validation passed 145; focused Reader Save/navigation validation passed 64; final smoke passed 53/0/0; pytest passed 417; serialization and repository-data audit passed.
- [x] User reported focused v1.0.26 manual validation Sections A-H passed; Save convergence and paper-navigation discard are accepted; G4 is closed.
- [ ] Commit, push, merge, tag, and release occur only after explicit instruction.

## v1.0.25-lifecycle-and-recovery-closure

- [x] Required v1.0.24 checkpoint, branch, clean tree, version, and documents verified.
- [x] Baseline recorded: smoke 48 passed/0 warnings/0 failed; pytest 377 passed.
- [x] Lifecycle/recovery contract documents critical state, rebuildable cache, and application configuration policy.
- [x] Recovery copies preserve and verify bytes; quarantine/restore are contained, explicit, and non-overwriting.
- [x] Exact duplicate decisions are atomic, reversible, path/SHA-bound, and included in snapshots.
- [x] Archive is orthogonal metadata visibility and preserves PDFs, IDs, notes, blocks, links, cache, status, and priority.
- [x] Focused validation passed (85 tests); final smoke passed 49/0/0 and pytest passed 396.
- [x] User reported the v1.0.25 Streamlit lifecycle validation completed before v1.0.26 work.
- [x] User reported the v1.0.24 Reader validation completed before v1.0.26 work.
- [ ] Release tag or checkpoint commit occurs only after explicit instruction.

## v1.0.24-reader-validation-and-parity-closure

- [x] Clean v1.0.23 baseline recorded: smoke 46 passed/0 warnings/0 failed; pytest 374 passed.
- [x] Status and priority persist through one explicit Apply action; unchanged settings produce no write payload.
- [x] Safe redundant explicit reruns are removed and retained reruns are classified/documented.
- [x] Paper-scoped note state and renderer keys have focused automated coverage.
- [x] Reader frontend parity checklist covers Must preserve, May redesign, and Intentionally deferred behavior.
- [x] Final `dev_check.ps1` evidence is recorded in v1.0.24 release notes.
- [x] Codex disposable checks and not-performed browser checks are clearly separated.
- [x] User-reported Streamlit manual Reader smoke completion is recorded by the v1.0.26 request.
- [x] Git status confirms no runtime/user data, PDFs, notes, exports, caches, or secrets are included.
- [ ] Release tag or checkpoint commit occurs only after explicit instruction.

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
