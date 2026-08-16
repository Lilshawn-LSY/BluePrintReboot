# BluePrintReboot frontend

The v1.5.9 frontend is a desktop-first local application built with Vinext/Next.js, React, and TypeScript. Library adds a bounded PDF scan/import workflow for files already inside the managed `papers/` directory: scan is preview-only, only new safe relative-path candidates can be selected, and import reports a per-file result before an imported Paper is opened in the collection or Reader. Project Detail remains an explicit workspace for metadata/status/priority, Paper links, and typed existing Note Block links. The Reader includes independent Paper metadata, enrichment preview, Paper tag, Reading Note, and Note Block workflows. Enrichment remains a later explicit action after import; it never runs during scan/import. There is no autosave, combined save, automatic/background or bulk enrichment, filesystem watcher, drag/drop, OCR, canonical Tag CRUD, alias governance, bulk tagging, Note Block delete/reorder, Project delete/unarchive, or Settings write.

## Local development

Start FastAPI from the repository root, then start the frontend:

```powershell
.\scripts\run_api.ps1
.\scripts\run_frontend.ps1
```

The frontend uses a strictly allowlisted same-origin server bridge to `http://127.0.0.1:8000` by default. In addition to bounded GETs and the Reader commands, the bridge permits explicit Project metadata/archive, Paper-link, and Note Block-link commands only. Copy `.env.example` to `.env.local` only when the API address needs to change.

## Commands

```powershell
npm run dev
npm run build
npm test
npm run lint
```

The shell remains navigable when FastAPI is offline and displays explicit unavailable states. Failed and conflicting Project commands never erase the current draft. Archived Project detail remains readable but has no Project edit, archive, add-link, or unlink controls. The Paper picker comes from the real bounded Paper collection and never fabricates records.
