# BluePrintReboot Backlog

Last synced: 2026-07-12

## v1.0.26 release closure

- [x] Fix Reader manual/suggested tag to Reading Note header divergence.
- [x] Consolidate canonical metadata mutation and partial-failure reporting behind a Streamlit-independent service.
- [x] Freeze JSON-safe read-only health, library, paper, detail, and Reader contracts without routes.
- [x] Add read-only snapshot plus disposable empty-target restore readiness validation.
- [x] Freeze Reader and lifecycle frontend acceptance criteria.
- [x] Run final automated validation and record evidence.
- [x] User reported focused v1.0.26 Sections A-H passed; Save convergence and navigation discard are accepted; G4 is closed.
- [ ] Commit, merge, tag, and release only after explicit approval.

The user reported the v1.0.24 Reader and v1.0.25 lifecycle manual matrices completed. Their implemented archive, recovery, quarantine, duplicate, and Reader state behavior is no longer future work. The later-discovered toolbar tag/header defect is the scoped v1.0.26 correctness fix.

## After v1.0.26

### Read-only FastAPI adapters

Adapt, without duplicating parsing, these frozen builders: `build_health_summary`, `build_library_status`, `build_paper_list_items`, `build_paper_detail`, and `build_reader_snapshot`. Start with conceptual `GET /health`, `/library/status`, `/papers`, `/papers/{paper_id}`, and `/papers/{paper_id}/reader`. No write endpoints.

### Frontend vertical slice

Reproduce the Reader/frontend parity checklist, then evaluate PDF.js. Keep explicit Save, dirty-draft isolation, metadata/header convergence, archived access, and lifecycle confirmations testable.

### Restore rehearsal and packaging

User performs a real clean-PC rehearsal using a copied snapshot and disposable target. Automated restore and installer packaging remain deferred.

### Deferred product work

OCR, semantic/LLM tagging, cloud sync, multi-user support, database migration, knowledge graphs, tag-governance expansion, automatic duplicate operations, `paper_id` redesign, and unrelated Streamlit redesign.
