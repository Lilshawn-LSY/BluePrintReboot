# Reader Frontend Parity Checklist

This is the acceptance contract for a future frontend adapter. v1.0.26 freezes behavior; it does not authorize FastAPI, React, Next.js, or PDF.js implementation.

## Reader invariants

- [ ] Save is always explicit. Metadata changes never save dirty body text.
- [x] Draft, baseline, and pending operations survive metadata-triggered reruns only while the same paper remains active.
- [ ] Keep draft preserves exact unsaved content; Discard changes and reload restores the last persisted note.
- [ ] Canonical title/author/year/DOI/tag changes converge with the Reading Note header. Clean notes refresh atomically; dirty drafts keep their body, remain dirty, and receive a pending non-destructive header refresh. Explicit Save writes the latest canonical header and body, then applies saved widget/baseline state only during the next pre-widget initialization.
- [x] Switching papers discards the previous paper's unsaved draft without writing it; returning loads its last explicitly saved note. Browser refresh and process restart do the same. No persistent per-paper draft store or navigation confirmation is required.
- [ ] Archived papers remain explicitly viewable in Reader without moving or deleting PDFs.
- [ ] Missing/large/external PDF guidance, active-paper isolation, project links, structured blocks, imports, extraction/profile state, and confirmation feedback remain equivalent.
- [ ] Streamlit may rerun and rerender the PDF after widget interaction. Avoidable application-triggered reruns stay removed; deeper renderer isolation is deferred to PDF.js.

## Lifecycle invariants

- [ ] No automatic duplicate merge or PDF deletion.
- [ ] Missing-PDF reconnect preserves `paper_id` and linked user state.
- [ ] Archive is reversible metadata-only visibility, orthogonal to reading status.
- [ ] Critical corrupt state is never silently reset, deleted, or replaced with an empty store.
- [ ] Only rebuildable caches may be explicitly quarantined, and only after a verified exact-byte recovery copy.
- [ ] Restore verifies retained bytes and refuses destination conflicts.
- [ ] Every action that removes an active file or record requires explicit confirmation.

## May redesign

Layout, components, state container, dialogs, feedback presentation, and PDF renderer may change when the invariants above have adapter-level parity tests. Public read contracts may be exposed unchanged through future read-only endpoints.

## Deferred

Write APIs, autosave, annotations, cloud/multi-user features, database migration, OCR, semantic/LLM tagging, `paper_id` redesign, note-format changes, automatic duplicate operations, and installer packaging remain out of scope.

## Validation gate

The user reported v1.0.26 manual validation Sections A through H passed. The prior `StreamlitAPIException` is fixed, Save convergence passed, and paper-navigation discard was explicitly accepted. G4 is closed after this contract alignment.
