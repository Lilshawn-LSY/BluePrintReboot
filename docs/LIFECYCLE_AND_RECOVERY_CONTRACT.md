# Lifecycle and Recovery Contract

BluePrintReboot is local-first and conservative: it never overwrites corrupt bytes, silently replaces critical user state with an empty store, or automatically deletes a corrupt file. Recovery operations are restricted to known app-owned paths inside the workspace.

| Storage class | Examples | Related writes when corrupt | Recovery-copy export | Quarantine | Automatic recreation | Manual repair | Backup snapshot | Future API diagnostics |
|---|---|---|---|---|---|---|---|---|
| Critical user state | projects, project links, note blocks, note-import history, lifecycle decisions, user-managed tag configuration | Blocked for the affected store | Allowed and the safe first action | Not allowed by default | Never | Required from a verified backup or repaired copy | Included | Class, relative path, diagnosis, and allowed actions only; never expose an absolute local path |
| Rebuildable cache | extracted-text text/metadata and PaperTextProfile cache | Cache write/rebuild is blocked until the corrupt target is explicitly quarantined | Allowed | Allowed only after explicit confirmation and verified copy | Allowed only after quarantine; no empty placeholder is created | Optional | Excluded as regenerable | Class, relative path, diagnosis, rebuildable state, and quarantine state only |
| Application configuration | bundled deterministic configuration, generated settings, user-managed settings/tag configuration | Block writes that depend on the affected file | Allowed | Only when an explicitly classified generated file is rebuildable; otherwise no | Bundled defaults may be reinstalled; generated files only after confirmed quarantine; user-managed files never | Required for user-managed configuration | User-managed configuration and relevant settings are included; bundled source configuration is versioned in Git | Class and relative path only; secrets and absolute paths are never exposed |

Recovery-copy export copies original bytes to `exports/recovery/` with a collision-safe UTC name and a manifest containing original and workspace-relative paths, storage class, byte size, SHA-256, timestamp, app version, and reason. It never modifies the source.

Quarantine is a reversible cache operation, not deletion. It requires confirmation, creates and verifies a recovery copy under `data/quarantine/`, and removes the active file only after verification. Failure leaves the active file intact. Restore requires confirmation, verifies the retained bytes, refuses to overwrite an active destination, and retains the quarantine copy.

Archive is an orthogonal metadata visibility state (`is_archived`, `archived_at`). It never changes `paper_id`, reading status or priority, paths, PDF bytes, notes, blocks, links, or caches, and never moves a file. Archived papers remain diagnosable and can be explicitly viewed, opened, and unarchived.

Exact duplicate ignores are atomic, reversible lifecycle decisions bound to both workspace-relative PDF path and SHA-256. A path or content change makes the decision inapplicable. Keep-for-review has no persistent effect. Automatic merge, file deletion, `paper_id` mutation, and automatic reconnect of healthy records remain out of scope.
