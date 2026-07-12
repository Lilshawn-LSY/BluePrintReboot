# Read-Only Domain Contracts

v1.0.26 freezes five plain-dictionary contracts in `services/library_read_model.py`. They contain JSON primitives only, use predictable empty-string/list/false defaults, expose workspace-safe relative paths, and never serialize pandas, `Path`, Streamlit state, exceptions, or absolute private paths. Builders read current state without creating, migrating, or saving files.

| Contract | Future adapter | Stable purpose |
|---|---|---|
| `HealthSummary` | `GET /health` | Overall healthy/degraded/blocked state and stable blocking, warning, corruption, quarantine, missing, and duplicate counts. |
| `LibraryStatus` | `GET /library/status` | Active/archived/missing/duplicate/corrupt/quarantine counts, degraded flag, and generic workspace warnings. |
| `PaperListItem` | `GET /papers` | List-only identity, citation summary, reading state, tags, archive/missing flags, and compact health labels. |
| `PaperDetail` | `GET /papers/{paper_id}` | List fields plus filename, safe relative PDF path, DOI, project-link summaries, note/cache/profile availability, lifecycle state, and recoverable warnings. |
| `ReaderSnapshot` | `GET /papers/{paper_id}/reader` | Paper detail, resolved PDF state, persisted note content/availability, canonical header values, content hash/size baseline, warnings, and unavailable reason. |

These remain domain builders rather than HTTP code. The FastAPI adapter calls them instead of reparsing CSV/JSON or importing `ui_streamlit`. Mutable session drafts are deliberately excluded.

## Implemented in v1.1.0

The initial local read-only API implements exactly:

| Route | Response contract | Behavior |
|---|---|---|
| `GET /health` | `HealthSummary` | Returns HTTP 200 for valid healthy, degraded, and blocked domain states. |
| `GET /library/status` | `LibraryStatus` | Returns HTTP 200 whenever a valid status contract is available, including degraded state. |

Both routes use strict Pydantic response schemas with undeclared fields forbidden. A genuine builder/storage failure becomes a generic HTTP 503 response without exception, path, environment, contact, or configuration details.

Paper lists, paper detail, Reader snapshots, PDF serving, notes, tags, projects, write actions, CORS, authentication, caching, background work, databases, and frontend work remain deferred.
