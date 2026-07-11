# Reader Note State Machine

Reading Note state is isolated by `paper_id` and stored in plain session-state values. The transition helpers do not import Streamlit. Disk writes remain explicit and atomic; no transition autosaves a draft.

## Visible States

- **Saved** - draft and baseline are identical.
- **Unsaved changes** - draft differs from the last loaded or explicitly saved baseline.
- **Header refresh pending** - metadata changed and a header refresh awaits safe automatic application or explicit application to the current draft.
- **Discard confirmation pending** - Reload was requested for a dirty draft and requires an explicit Keep or Discard decision.

## Events and Results

| Event | Result |
|---|---|
| Initial disk load | Set draft and baseline to disk text for that paper. |
| User edit | Change only the draft; state becomes Unsaved changes. |
| Explicit Save | Atomically write the draft, then set baseline to the saved draft. |
| Clean Reload | Load disk text into draft and baseline. |
| Dirty Reload request | Preserve the exact draft and show Keep draft / Discard changes and reload. |
| Keep draft | Clear the destructive request without changing draft or baseline. |
| Discard and reload | Consume the confirmation once, then load disk text into draft and baseline. |
| Header refresh on dirty draft | Refresh the latest draft header, preserve its body, and keep the saved baseline distinct. |
| Header refresh already saved to disk | Update the baseline to the saved refreshed text; later draft edits remain dirty. |
| Queued whole-draft update | Apply only when the draft still matches the value from which the update was produced. |
| Queued append | Append to the latest accepted draft after any accepted whole-draft update. |
| Paper switch or non-note action | Preserve every paper-scoped draft, baseline, and pending event. |

## Transition Precedence

On each Reader rerun, pending events are handled once in this order:

1. Accepted reload.
2. Safe saved header refresh; unsafe or unsaved refresh remains pending.
3. Whole-draft text replacement, only if no newer edit exists.
4. Markdown or structured-block append.

Consumed event keys are removed, making reruns idempotent. A dirty draft is replaced only after explicit discard confirmation. Save, Keep, and Discard clear obsolete destructive reload state.
