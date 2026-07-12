# Reader Frontend Parity Checklist

This is the minimum contract a future FastAPI/frontend Reader vertical slice must reproduce. It is a parity gate, not authorization to start that migration in v1.0.24.

## Must Preserve

- [ ] Stable `paper_id` identity and active-paper navigation across Reader actions.
- [ ] Local PDF visibility, native/default viewing behavior, explicit experimental fallback, missing-PDF messaging, external-path guidance, and large-PDF warnings/confirmation.
- [ ] Reading Note disk load using the existing filename and Markdown format.
- [ ] Explicit Save only; no autosave or silent write of an unsaved draft.
- [ ] Saved versus Unsaved changes state derived from draft and baseline.
- [ ] Dirty Reload with explicit Keep draft and Discard changes and reload decisions.
- [ ] Metadata-header refresh that preserves the latest body and keeps dirty drafts dirty until Save.
- [ ] Paper-scoped draft, baseline, pending-event, notice, and PDF-renderer isolation.
- [ ] Combined reading status and priority editing with deliberate persistence.
- [ ] Paper-local and canonical tag behavior without automatic promotion or retagging.
- [ ] Paper/project links and note-block/project links, including confirmation requirements.
- [ ] Structured note-block create, edit, delete, filter, and one-way append-to-Reading-Note behavior.
- [ ] External note import preview, explicit confirmation, duplicate-source guard, and optional structured-block creation.
- [ ] `PaperTextProfile`, extracted-text status/content, rebuild/extract controls, stale-cache warnings, and degraded extraction presentation.
- [ ] Clear success, warning, error, confirmation, missing-file, and degraded-state feedback.
- [ ] Local-first paths and privacy: no upload, cloud sync, background service, or inspection outside user-selected/local managed data.
- [ ] Browser refresh or process restart restores only explicitly saved note text; unsaved in-memory drafts are not represented as durable.

## May Redesign

- [ ] Layout, toolbar placement, responsive columns, typography, and visual hierarchy.
- [ ] PDF renderer implementation, provided native/fallback/missing/large-file behavior remains equivalent.
- [ ] Editor component and state container, provided explicit-save and destructive-reload invariants remain testable.
- [ ] Feedback components, dialogs, and confirmation presentation.
- [ ] How status, priority, tags, projects, blocks, profile, and extracted text are grouped or navigated.
- [ ] API boundaries and payload shapes after parity tests exist and local storage semantics remain authoritative.

## Intentionally Deferred

- FastAPI implementation and write endpoints.
- React, Next.js, PDF.js, custom PDF annotations, iframe messaging, or a new Streamlit component.
- Cloud sync, multi-user accounts, background processes, SQLite/database migration, OCR, external ontology, or LLM/API features.
- Autosave, automatic duplicate merge/deletion, archive semantics, corrupt-cache quarantine, or Tag Book expansion.
- Changes to `paper_id`, note filenames/Markdown, storage formats, or atomic persistence.

## Manual Parity Evidence Required

Before G4 can close, a user must record the current Streamlit manual smoke baseline for Save/Unsaved/Reload Keep/Discard/header refresh, paper isolation, non-note actions, browser refresh/application restart, and PDF usability after Reader actions. Automated tests and Codex disposable checks do not substitute for browser-level user validation.
