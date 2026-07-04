# BluePrintReboot Roadmap

This roadmap keeps v1.0.0-foundation focused on stabilization and release confidence. It is not a frontend migration plan for the current release.

## Phase 1: Streamlit Stabilization

- Keep BluePrintReboot local-first, single-user, and Streamlit-based.
- Stabilize the core reading loop: add paper, read PDF, edit metadata/tags, write notes and structured blocks, link to projects, retrieve later.
- Improve fresh install reliability, smoke checks, documentation, and backup/restore confidence.
- Reduce version and tag confusion before introducing larger platform changes.

## Phase 2: FastAPI Read-Only Backend

- Add a read-only API only after the core data model and file layout are stable.
- Expose library, metadata, notes, tags, projects, and health information without changing write paths.
- Use the API to validate boundaries and data contracts before any frontend migration.

## Phase 3: Frontend Migration

- Begin frontend migration only after the core data model, library workflow, and smoke checks are stable.
- Preserve existing Streamlit behavior until replacement workflows are proven.
- Treat PDF reading, metadata editing, notes, tags, projects, and maintenance views as required parity areas.

## Phase 4: Packaging / Launcher / Installer

- Reduce fresh-install friction with a clearer launcher or packaging approach.
- Keep local data paths transparent and user-controlled.
- Preserve PowerShell-friendly setup and repair paths.

## Phase 5: Optional AI-Assisted Features

- Add AI assistance only where it improves the core loop.
- Keep user data local unless the user explicitly chooses otherwise.
- Prefer reviewable suggestions for summaries, tags, relations, and retrieval over automatic irreversible changes.
