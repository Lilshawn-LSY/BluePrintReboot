# BluePrint UI Design System

## Purpose and scope

This document defines the shared desktop research-workspace foundation for
BluePrintReboot v1.6. It guides the application shell, navigation, information
exposure, density, and interaction language. It does not authorize a backend
contract change, a color-palette redesign, or a page-specific workflow redesign.

The executable source of truth for numeric values and shared classes is
`frontend/app/globals.css` and the components under `frontend/app/components/`.
This document explains how to use those primitives consistently.

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
(`--space-12`). Compatibility aliases may exist, but new work should choose
the canonical tokens rather than introducing arbitrary values.

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
- Use `--border`, `--radius-sm` (4px), and `--radius-md` (8px) consistently.
  Focus must remain plainly visible through the shared focus ring. Disabled
  controls must retain their label and visibly communicate that they cannot be
  used.

Primary actions are the one action that advances the current task. Secondary
actions are neutral alternatives. Destructive or irreversible actions retain a
distinct danger treatment and their existing confirmation requirements.

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
