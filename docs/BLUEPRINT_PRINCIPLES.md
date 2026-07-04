# BluePrintReboot Principles

## Core Loop

BluePrintReboot exists to make one local research loop reliable:

1. Add a paper to the managed `papers/` library.
2. Read the PDF in the Streamlit app.
3. Edit metadata, status, priority, and tags.
4. Write Markdown notes and structured note blocks.
5. Link papers and useful note blocks to projects.
6. Retrieve papers, notes, tags, and project context later.

Every new feature should improve this loop directly, make it easier to trust the data behind it, or reduce maintenance risk around it.

## What Belongs In The App

The app should keep supporting:

- local PDF library management under `papers/`;
- stable `paper_id` identity and predictable local storage;
- metadata editing and optional metadata enrichment;
- tags, tag governance, and search/filter workflows;
- Markdown notes and structured note blocks while reading;
- lightweight project linking;
- library health checks, backup snapshots, and restore documentation;
- non-destructive maintenance workflows with preview and confirmation.

The app should stay understandable to a single user maintaining a personal research library.

## What Should Be Postponed

Postpone work that does not stabilize the core loop or maintenance reliability, including:

- FastAPI or frontend migration before the Streamlit workflow is stable;
- multi-user accounts, permissions, or hosted service assumptions;
- automated destructive restore;
- advanced AI workflows that are not grounded in local user-controlled data;
- visual graph features that do not yet improve daily retrieval;
- large architecture rewrites that make the current app harder to ship.

These ideas may still belong on the long-term roadmap, but they should not distract from the foundation release.

## Local-First Data

BluePrintReboot is local-first and user-controlled:

- Runtime library data lives on the user's machine.
- GitHub stores application code, not the personal paper library.
- `papers/`, `data/`, `notes/`, `exports/`, and extracted text caches are user data and should not be rewritten casually.
- Network features must remain optional for the core reading and organization workflow.
- Maintenance tools should prefer read-only checks, previews, explicit confirmations, and reversible manual procedures.

## Feature Test

Before adding or accepting a feature, ask:

- Does this improve adding, reading, annotating, organizing, linking, or retrieving papers?
- Does this improve confidence in local data integrity, backup, restore, or release readiness?
- Can it be implemented without weakening the current Streamlit workflow?

If the answer is no, defer it.
