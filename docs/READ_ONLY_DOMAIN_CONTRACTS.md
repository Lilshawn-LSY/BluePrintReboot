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

At v1.1.0, paper lists, paper detail, Reader snapshots, PDF serving, notes, tags, projects, write actions, CORS, authentication, caching, background work, databases, and frontend work remained deferred.

## Implemented in v1.1.1

The Paper API adapts the frozen `PaperListItem` and `PaperDetail` builders through explicit strict Pydantic models:

| Route | Contract | Behavior |
|---|---|---|
| `GET /papers` | `PaginatedPaperList` containing `PaperListItem` values | Defaults to active papers, supports `active`/`archived`/`all`, and paginates with `limit`, `offset`, `total`, and `has_more`. |
| `GET /papers/{paper_id}` | `PaperDetail` | Returns active or archived detail by stable ID; unknown IDs return a structured 404. |

Collection ordering follows the established domain rule: case-insensitive title ascending, then `paper_id` ascending. Archive state comes only from the existing `is_archived` lifecycle field; absent archive values remain active, and reading `status` stays independent.

The HTTP mapper normalizes strings, years, tags, and booleans, rejects missing paper identity/title, strips path components from filenames, rejects unsafe absolute/traversal PDF paths, and allowlists every response field. It never receives or returns an arbitrary CSV row.

The frozen domain detail currently provides DOI, safe PDF/lifecycle state, project-link summaries, and note/cache/profile availability. Journal, abstract, keywords, and arXiv identifiers remain outside the v1.1.1 API rather than being read directly from storage; they require a deliberate future domain-contract extension.

## Extended in v1.1.2

`PaperDetail` now also contains `authors: list[str]`, `journal: str`, `abstract: str`, `keywords: list[str]`, and `arxiv_id: str`. `PaperListItem` is unchanged, so `GET /papers` remains a lightweight collection contract while `GET /papers/{paper_id}` carries rich citation metadata.

Canonical sources and precedence are:

| Public field | Canonical source | Normalization |
|---|---|---|
| `authors` | `paper_index.csv` `authors` column | Existing semicolon serialization becomes an ordered list; whitespace and empty entries are removed, and commas inside names are preserved. |
| `journal` | `paper_index.csv` `journal` column | Outer whitespace is removed; missing/None/NaN becomes `""`. |
| `abstract` | `paper_index.csv` `abstract` column | The complete stored value is preserved with outer whitespace removed; no summarization or truncation. |
| `keywords` | `paper_index.csv` `keywords` column | Existing comma serialization becomes an ordered list; whitespace and empty entries are removed. |
| `arxiv_id` | Existing Reading Note identity rule | A normalized explicit `arxiv_id` wins when present; otherwise the first identifier detected deterministically from stored DOI, filename, title, abstract, and keywords is used. |

Older indexes need no migration during reads: the read-only index snapshot supplies safe defaults for absent canonical columns. PaperTextProfile is a derived cache and is not a fallback for this contract. API reads do not call Crossref, OpenAlex, arXiv, PDF extraction, or any other network/enrichment path, and they do not parse extracted full text.
