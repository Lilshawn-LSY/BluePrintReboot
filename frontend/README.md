# BluePrintReboot frontend

The v1.6.5 frontend is a desktop-first local application built with Vinext/Next.js, React, and TypeScript. Its visual-language refinement uses rule-led, flat research-workspace surfaces; compact structural metadata; quiet ordinary status labels; and overlay-only depth while preserving explicit server saves and browser-local draft preservation. There is no server autosave, offline write queue/background sync, combined save, automatic/background or bulk enrichment/tagging, filesystem watcher, drag/drop, OCR, destructive tag deletion, ontology editing, Note Block delete/reorder, Project delete/unarchive, or Settings write.

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

The shell remains navigable when FastAPI is offline and displays explicit unavailable states. The shared task-facing save states are Saved, Unsaved changes, Saving..., Save failed, Changed elsewhere, and Offline; revision and HTTP details remain secondary. Archived Project detail remains readable but has no Project edit, archive, add-link, or unlink controls. The Paper picker comes from the real bounded Paper collection and never fabricates records.
