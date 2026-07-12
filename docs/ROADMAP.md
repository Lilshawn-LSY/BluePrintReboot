# BluePrintReboot Roadmap

Last synced: 2026-07-12

v1.0.26 is the final Streamlit stabilization and architecture-boundary release before any FastAPI/frontend migration. The product remains local-first, single-user, and Streamlit-based.

## Implemented through v1.0.26

- v1.0.24 froze Reader note state, explicit Save/Reload behavior, rerun expectations, and initial frontend parity. The user subsequently reported its manual Reader matrix completed.
- v1.0.25 closed archive, corruption diagnosis, recovery-copy, cache quarantine/restore, exact duplicate decisions, backup coverage, and lifecycle read semantics. The user subsequently reported its manual lifecycle matrix completed.
- Actual use after those validations exposed Reader toolbar tag changes bypassing Reading Note header synchronization.
- v1.0.26 routes canonical metadata changes through one UI-independent coordinator, guarantees dirty-draft preservation and Save-time convergence, freezes `HealthSummary`, `LibraryStatus`, `PaperListItem`, `PaperDetail`, and `ReaderSnapshot`, and adds read-only disposable restore readiness checks.

## Decision gates

| Gate | Status | Required next evidence |
|---|---|---|
| G0: Automated baseline | Closed for v1.0.26 | Final smoke, pytest, platform, Python, Streamlit, serialization, diff, and data-hygiene results are recorded. |
| G1: Lifecycle safety | Closed for v1.0.25 | Preserve the completed lifecycle contract and regression coverage. |
| G4: Reader stability | Closed | User reported v1.0.26 Sections A-H passed, the Save exception fixed, convergence passed, and navigation discard accepted. |
| G5: Deterministic tags | Frozen | No governance expansion in v1.0.26. |
| G6: FastAPI readiness | No | Close v1.0.26 automated and focused manual validation, then release v1.0.26. |
| G7: Frontend readiness | No | Begin only after read-only adapters exist and parity tests consume the frozen contracts. |

## Next sequence

1. Close and release v1.0.26 with explicit approval.
2. Implement read-only FastAPI adapters for the frozen domain builders; add no write endpoints initially.
3. Build a frontend vertical slice against the Reader/lifecycle parity contracts. PDF.js-specific rendering and annotations remain deferred until that slice.

## Continuing constraints

No autosave, automatic duplicate merge/deletion, automatic critical-state repair, database migration, OCR, LLM tagging, cloud sync, `paper_id` redesign, or destructive automated restore. Keep setup/restore rehearsal explicit and disposable.
