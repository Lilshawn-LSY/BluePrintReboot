# Reader Note State Machine

Reading Note state is scoped to the active `paper_id` and stored in plain session-state values. It survives Streamlit reruns while that paper remains active. Switching papers deliberately discards the previous paper's volatile draft state; returning reloads its last explicitly saved note. Browser refresh and process restart likewise discard unsaved drafts. No transition autosaves or persistently stores a draft.

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
| Explicit Save | Refresh canonical metadata, atomically write the latest header and body, queue the saved text/baseline/success transition, and rerun. The next pre-widget initialization consumes it and becomes Saved. |
| Clean Reload | Load disk text into draft and baseline. |
| Dirty Reload request | Preserve the exact draft and show Keep draft / Discard changes and reload. |
| Keep draft | Clear the destructive request without changing draft or baseline. |
| Discard and reload | Consume the confirmation once, then load disk text into draft and baseline. |
| Header refresh on dirty draft | Refresh the latest draft header, preserve its body, and keep the saved baseline distinct. |
| Header refresh already saved to disk | Update the baseline to the saved refreshed text; later draft edits remain dirty. |
| Queued whole-draft update | Apply only when the draft still matches the value from which the update was produced. |
| Queued append | Append to the latest accepted draft after any accepted whole-draft update. |
| Same-paper metadata or non-note rerun | Preserve the active paper's draft, baseline, and pending events. |
| Switch Paper A to Paper B | Discard Paper A's volatile draft/baseline/pending note state without writing it, then load Paper B from disk. |
| Return to Paper A | Load Paper A's last explicitly saved Reading Note from disk. |
| Browser refresh or process restart | Start from explicitly persisted note text; unsaved draft state is not durable. |

All canonical metadata mutation paths use `services.paper_metadata_mutation`. The coordinator compares normalized values before writing, updates the index atomically, reloads the record, refreshes clean note headers, and queues dirty-draft convergence without importing Streamlit or saving the body.

## Transition Precedence

On each Reader rerun, pending events are handled once in this order, before the note `text_area` is instantiated:

1. Successful Save result: update draft widget value and baseline, clear obsolete header/reload state, and publish success feedback.
2. Accepted reload.
3. Safe saved header refresh; unsafe or unsaved refresh remains pending.
4. Whole-draft text replacement, only if no newer edit exists.
5. Markdown or structured-block append.

Consumed event keys are removed, making reruns idempotent. A dirty draft is replaced only after explicit discard confirmation. Save, Keep, and Discard clear obsolete destructive reload state.

## Reader Action and Rerun Contract

Streamlit performs a full script pass for ordinary widget interaction. "No explicit rerun" means the action relies on that current framework pass and does not call `st.rerun()` a second time.

| Action class | Examples | Explicit rerun contract |
|---|---|---|
| Draft-local | Toolbar note-block insertion | None when the note editor renders later in the same pass. |
| Draft-local with queued transition | Template insertion, block append, Reload/Keep/Discard, header refresh | One intentional rerun so the authoritative pending transition is consumed before redisplay. |
| Persistent note | Explicit Save | One intentional rerun. The Save pass only persists and queues paper-scoped results; the next pass updates the widget-backed draft and baseline before widget creation and shows success. External import also retains one rerun. |
| Persistent paper metadata | Manual/suggested tags; combined status/priority Apply | One intentional rerun after a successful write to reload the record and metadata header safely. Unchanged status/priority submits do not write or explicitly rerun. |
| Read-only diagnostic/cache | Tag preview, profile display/rebuild, renderer selection, extracted-text display | Preview/profile actions use the current pass. Extract/re-extract retains one rerun because cache status was computed before the action. Renderer selection has no application-triggered rerun, although Streamlit reruns the script. |
| Destructive or confirmation-gated | Extracted-cache delete, structured-block delete | One intentional rerun after confirm/cancel to remove stale confirmation UI and reload affected data. |
| Structured-block persistence | Edit/create block | One intentional rerun after save/create because the list/form was rendered from the old disk state. Opening Edit uses the current pass. |
| Navigation/project links | Same-paper reruns preserve active note state. Selecting a different paper discards the previous paper's unsaved note state, activates the target, and reloads its persisted note. No navigation confirmation or draft persistence is required. |

Avoidable explicit reruns removed in v1.0.24: toolbar draft insertion, PaperTextProfile rebuild, tag preview, and opening a structured-block edit form. The former separate status and priority write/rerun paths were replaced by one form-backed Apply action and at most one intentional reload.
