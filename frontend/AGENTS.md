# Frontend UI Rules

For any frontend or UI change, read and follow
[`docs/UI_DESIGN_SYSTEM.md`](../docs/UI_DESIGN_SYSTEM.md) before editing.

- Preserve the typed same-origin API bridge and explicit-save/revision-safety
  behavior. UI work must not bypass an established client or command boundary.
- Reuse the shared shell, `PageHeader`, `Breadcrumbs`, `Section`, status, and
  token primitives before adding a parallel UI pattern.
- Keep normal-page sidebar preferences separate from Reader overlay behavior.
  Reader navigation must never resize the PDF workspace.
- Do not add destinations, fake controls, global search, synchronization, or
  command-palette behavior without an implemented product contract.
- Keep diagnostic data out of ordinary task surfaces. Put it in Settings or an
  explicitly advanced/diagnostic context when it is genuinely needed.
- Treat Page/Reader save, reload, conflict, and mutation-gate behavior as
  functional requirements, not styling details. Add focused frontend coverage
  for shared-shell behavior when changing it.
