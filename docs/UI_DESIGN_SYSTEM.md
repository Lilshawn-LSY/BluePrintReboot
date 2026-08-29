# BluePrint UI Design System

## Purpose and scope

This document defines the shared desktop research-workspace foundation for
BluePrintReboot v1.6.5. It guides the application shell, navigation,
information exposure, density, and interaction language. It does not authorize
a backend contract change, a color-palette redesign, or a page-specific
workflow redesign.

The executable source of truth for numeric values and shared classes is
`frontend/app/globals.css` and the components under `frontend/app/components/`.
This document explains how to use those primitives consistently.

## v1.6.5 visual-language grammar

BluePrint is a scientific notebook, technical drafting sheet, and local desktop
research tool. Its identity comes from information structure, calm density,
typographic roles, and a clear hierarchy of rules—not from decorative cards,
gradients, soft shadows, or generic dashboard styling.

- Use the canvas for ordinary reading, lists, metadata, and section context.
  Reserve white surfaces for actual work: editors, forms, inspectors, drawers,
  and PDF/document areas.
- Prefer aligned rows, tables, list rules, and section boundaries to enclosing
  every content group in a bordered panel. A boundary remains appropriate when
  it describes an input surface, selected inspector, modal, drawer, or another
  functional containment relationship.
- The shared structural tokens are `--rule-faint` for quiet row separation,
  `--rule` for ordinary control and inspector boundaries, and `--rule-strong`
  for major table, toolbar, workspace, and section structure. `--border`
  aliases the default rule for compatible controls.
- Use `--radius-sm` for controls and working surfaces. `--radius-md` is still
  deliberately small and should be reserved for the few bounded surfaces that
  benefit from it. Shadows indicate an actual overlay or floating surface;
  ordinary panels and collection surfaces are flat.
- Human-facing titles, abstracts, notes, and prose use the readable sans
  family. The mono family is reserved for structural labels, table headings,
  compact counts, page/zoom values, dates where helpful, and technical
  identifiers such as DOI or arXiv. It must not become the default reading
  face.
- Avoid all-caps marketing eyebrows. When compact context notation is useful,
  use a quiet mono label with an accent rule rather than a repeated promotional
  label.
- Ordinary domain metadata is a quiet inline label. Taxonomy values may use a
  compact chip. Strong badges are reserved for exceptional or actionable states
  such as Missing PDF, Conflict, Offline, Failed, or Archived. This is a
  visual distinction only; it never changes the underlying state semantics.
- Selection uses a restrained surface change plus an inset accent rule. Hover
  changes color, a rule, or a subtle background only. Do not use lift, scale,
  or decorative motion.

Page archetypes express the same grammar in different proportions: Dashboard
is a compact workbench; Library and Tags are catalogue/index surfaces;
Project Detail is a dossier; Settings is a quiet utility surface; and Reader
is an instrument workspace with the strongest alignment, hairline separation,
and least decorative chrome. The optional drafting-grid motif is intentionally
not used behind prose, editable content, or PDF pages.

## Application shell and navigation

Normal application pages use the shared left sidebar and retain the established
primary destinations: Dashboard, Library, Projects, Tags, and Settings. The
expanded sidebar remains the normal working width. Its explicit toggle changes
it to an icon rail; icon labels remain available through accessible names and
tooltips. The normal-page collapsed preference is session-scoped and survives
route navigation and reloads in that browser session.

Reader is a workspace exception. It does not reserve the expanded sidebar
column. A narrow left-edge reveal zone opens the normal sidebar as a fixed
overlay, so the PDF never resizes or shifts. The revealed navigation includes
an explicit close control and a pin/unpin control. Reader overlay state is
separate from the normal-page collapsed preference and must never overwrite it.

Do not add navigation destinations, global search, command palettes, sync
controls, or other controls without an implemented product capability.

## Breadcrumbs and top chrome

Top-level pages do not display breadcrumbs. The active sidebar item already
provides that location context.

Nested object pages use the shared `Breadcrumbs` component:

- `Library / <paper identity>` for Paper Detail.
- `Library / <paper identity> / Reader` for Reader.
- `Projects / <project name>` for Project Detail.
- `Tags / <tag name>` when a tag-detail route exists.

Breadcrumb identities must be compact, navigable where meaningful, and allowed
to truncate rather than force a large layout. When a breadcrumb provides the
parent route, do not also add a standalone "Back to …" link.

The shell does not spend persistent top-chrome space on a version label or a
duplicate local-workspace label. Product version, API contract version, and
other maintenance data belong primarily in Settings diagnostics.

Settings may sit in a visually secondary, lower navigation group when the
shell has enough height. This changes emphasis, not route availability or
keyboard access.

## Information hierarchy

Every UI decision should place information in one of four tiers.

| Tier | Meaning | Typical examples |
| --- | --- | --- |
| Primary | Required to complete the current task; visible by default. | Paper title, author, year, project name. |
| Contextual | Helps understand or choose. | Abstract, journal, tags, reading status. |
| Operational | Temporary state beside the active operation. | Saving, Saved, Extracting, Failed, Conflict. |
| Diagnostic | Implementation or maintenance detail. | UUIDs, raw ISO timestamps, cache provider/version, storage internals, API versions. |

Do not surface diagnostic data as ordinary content merely because it is
available in an API response. Put it in Settings or a clearly advanced,
diagnostic context. Existing safety errors remain visible and actionable.

## Status taxonomy

Use status presentation according to its meaning, not according to its API
field name.

- **Domain state** is persistent and meaningful to a person: Unread, Reading,
  Finished, Active, Archived, or priority. It may appear normally.
- **Operational state** is temporary: Saving, Extracting, Conflict, Failed, or
  a reload requirement. Keep it adjacent to the control or operation it
  describes, with an accessible live announcement where appropriate.
- **System health** is diagnostic: Healthy, Clean, Cached, Ready, or internal
  service state. Keep ordinary healthy state quiet on task surfaces; surface
  abnormal or actionable state clearly. Settings is the intended health and
  diagnostics surface.

Do not change the meaning of backend states while changing their display.

Avoid duplicate state: show a save state beside the editor or command it
describes, not again in a parent context. Likewise, quiet ordinary system
health such as an active lifecycle state belongs out of persistent workspace
chrome; exceptional, actionable, or unavailable state remains visible close to
the affected work.

### Explicit-save draft states

For a user-authored explicit-save surface, use exactly this visible vocabulary:
**Saved**, **Unsaved changes**, **Saving...**, **Save failed**, **Changed
elsewhere**, and **Offline**. Do not make revision hashes, `409`, stale
revision, or reload terminology the primary label. A local draft remains until
the matching server response is confirmed; an edit during a request remains
Unsaved changes after the earlier snapshot succeeds. Changed elsewhere keeps
the local draft and latest server value separate and must provide an explicit
keep-my-draft/use-latest path. A save status belongs next to its editor/action
and uses the shared `SaveStatus` presentation.

## Layout archetypes

Future page work follows one of these three structures.

### Collection

Library, Projects, and Tags are high-density collection surfaces:

```text
Header
Toolbar / actions
Collection (list or table)
Optional inspector or context surface
```

### Detail

Paper Detail, Project Detail, and comparable objects prioritize inspection:

```text
Breadcrumb
Object header + primary action
Main information
Context / secondary information
```

Use the shared `page-stack--detail` modifier for a bounded detail reading
width (about 1200–1400px). Project Detail starts with a compact metadata row,
not a large fact-card strip: status, priority, updated time, linked-material
counts, and project tags belong together near the identity. Linked research
material appears ahead of editing and lower-frequency management.

### Workspace

Reader prioritizes the active work area:

```text
Compact workspace chrome and toolbars
Maximum main workspace area
Optional contextual panels
```

Do not use this foundation pass to turn one archetype into another or to
redesign the existing Library, Reader panel, Projects, Tags, Dashboard, or
Settings workflows.

Dashboard uses the shared `page-stack--dashboard` modifier (about
1200–1350px) for a readable working surface. Broad collection surfaces keep
the default shell width. Reader remains unrestricted because its PDF workspace
is the active surface.

### Workspace information hierarchy patterns

Collection creation and management controls are progressive disclosures. A
Projects or Tags collection leads with items to review; a create form appears
only after its explicit action, except when a locally preserved draft needs to
be recovered. Object details lead with the object and its related research
material. Forms that create or manage links are secondary to linked Paper and
Note Block cards.

When a temporary collection disclosure closes, focus returns to the action
that opened it. A selected-item inspector returns focus to the selected row's
control when dismissed. This keeps the browse → inspect → continue loop fully
keyboard operable without inventing modal behavior where a stacked layout is
already sufficient.

Diagnostic information does not share the default task surface. Settings may
describe real workspace/application information and link to Diagnostics;
verbose health, integrity, count, API, and backup details belong in that
dedicated diagnostic context. Attention states should link directly there.

Abstracts and other extracted prose use a bounded readable content column
(about 65–80 characters). Display adapters may join extraction soft-wrapped
lines, but must preserve blank-line paragraph boundaries and never write the
normalized value back to persistent metadata.

## Spacing, typography, and controls

Use the shared spacing scale from `globals.css`. The canonical increments are
4px (`--space-1`), 8px (`--space-2`), 12px (`--space-3`), 16px
(`--space-4`), 24px (`--space-6`), 32px (`--space-8`), and 48px
(`--space-12`). `--space-5` intentionally aliases `--space-4` and
`--space-10` intentionally aliases `--space-12` for existing component
compatibility; new work should choose canonical tokens rather than introduce
arbitrary values.

- Use 4–8px for inline and micro separation, 12–16px for compact controls and
  related content, 24px for grouped content, 32px for sections, and 48px only
  for major separation.
- Page titles use `--font-size-xl`; section titles use `--font-size-md`; body
  copy uses `--font-size-base`; helper and metadata copy use
  `--font-size-sm` or `--font-size-xs`.
- Tables use compact 12px cell padding (`--space-3`). Preserve readable
  headers and horizontal scrolling rather than forcing data to wrap badly.
- Standard controls use `--control-height` (36px); compact shell controls use
  `--control-height-compact` (32px). Reuse `reader-control`, its secondary
  variant, and the existing semantic button patterns rather than creating a
  second control system.
- Use `--rule-faint`, `--rule`, and `--rule-strong` according to structural
  importance. `--radius-sm` is 3px and `--radius-md` is 4px: keep the
  interface precise without making controls harsh. Focus must remain plainly
  visible through the shared focus ring. Disabled controls must retain their
  label and visibly communicate that they cannot be used.

Primary actions are the one action that advances the current task. Secondary
actions are neutral alternatives. Destructive or irreversible actions retain a
distinct danger treatment and their existing confirmation requirements.

Project Detail exposes Edit Project as its ordinary primary action. Reload and
Archive are lower-frequency recovery/destructive actions and may share a
compact secondary disclosure, while remaining keyboard-discoverable. Linked
Paper and Note Block rows reserve their visible space for identity, compact
citation/context, relationship, exceptional target state, and navigation;
unlink is a labelled secondary row action and keeps its confirmation behavior.
Ordinary rows target roughly 56–72px where their content permits. Two-line
title clamping is acceptable when the full label remains exposed accessibly.

## Copy and edit behavior

Use a page title and, at most, one concise user-facing sentence. Omit section
descriptions when the section title and content are self-explanatory. Prefer
plain product language over implementation language such as “contract,”
“command,” “deterministic,” “revision-checked,” “allowlisted,” “read model,”
or “stored record.” Safety and error messages may explain necessary constraints
in direct, user-facing terms.

Do not introduce a global read/edit mode. Editor surfaces may keep directly
editable controls, but informational fields should not turn into inputs merely
for visual consistency. Preserve explicit Save, reload, conflict, and
revision-safety behavior.

## Reader interaction patterns

Reader top chrome is a single compact desktop row where practical. Breadcrumbs
provide Paper identity and expose a truncated Paper title through the existing
full-title tooltip; do not add a second visible title heading. A visually
hidden document heading may preserve semantic hierarchy. Tags and Full Text
remain immediate utility controls. Ordinary active lifecycle state is quiet;
archived, unavailable, conflict, and other exceptional state remains visible
where relevant.

The Reader keeps compact Paper context at the top of the research panel. Its
persistent modes are **Note**, **Blocks**, and **Details**. Switching modes
hides inactive work without destroying its editor, selection, draft, preview,
conflict, or link-management state. The Note mode is the default, and tabs
retain semantic roles, visible focus, and ordinary keyboard focus order.

Paper context is informational: author, year, DOI/arXiv when present, panel
collapse, and a meaningful restored-draft notice. Paper Note `SaveStatus`
belongs only beside the Paper Note editor; metadata `SaveStatus` belongs only
in Details. The Paper Note formatting toolbar uses compact icon or typographic
controls with an accessible name and title for every icon-only action. Its
selection-preservation behavior is part of the control contract.

On desktop, the research panel is session-resizable from 320px to 520px. A
pointer resize must be paired with an accessible range control and reset
action. Tags and Full Text open as overlay utility drawers by default: an
overlay does not add a grid column or reduce the PDF stage width. Opening a
drawer moves focus into it; Escape and its close control return focus to the
initiating control.

PDF controls provide previous/next page, zoom, fit width, fit page, and manual
zoom. Fit width uses the usable PDF stage width; fit page considers both stage
dimensions. Manual zoom leaves fit mode cleanly. Logical PDF/text-layer
geometry remains independent of backing-canvas high-DPI rendering.

The utility drawer header names the currently open utility and includes Close.
Do not repeat a full Tags/Full Text tab switcher inside the drawer unless a
future workflow has a material reason for one. Its overlay, focus management,
Escape behavior, and PDF-position preservation remain unchanged.

When a browser-local draft is restored, show a compact live `Draft restored`
notice or the existing unsaved state. Normal in-app navigation does not
interrupt work with a confirmation when that draft is safely preserved.
Explicit discard, deliberate replacement with a saved version, and destructive
operations retain their confirmation semantics.

Collection toolbars use the shared `Toolbar` structure. Prefer structured
controls for known values, including searchable canonical-tag suggestions and
reading-status selects. Text search may debounce before refresh, every filter
change resets pagination, and a collection title remains a normal navigation
link with a separate Inspect action for contextual inspection.

## Accessibility and responsiveness

Maintain semantic headings, labelled navigation, keyboard-reachable controls,
visible focus, and live status feedback for active operations. Icon-only
controls require accessible names. Collapsed navigation must remain operable
without hover; Reader hover reveal always has explicit open, close, and pin
controls as alternatives.

The primary target is a desktop research workspace. At narrower widths,
collections may scroll horizontally and normal navigation may compact, but
content, controls, and all navigation destinations must remain accessible.
Respect reduced-motion preferences and do not make hover the sole way to reach
an action.
