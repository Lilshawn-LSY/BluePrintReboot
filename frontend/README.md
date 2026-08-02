# BluePrintReboot frontend

The v1.5.5 frontend is a desktop-first local application built with Vinext/Next.js, React, and TypeScript. The Reader now adds a Paper-local structured Note Block workspace with explicit create/edit/save/cancel, conflict-safe drafts, and explicit links to existing writable Projects. Project Detail renders typed Note Block summaries, orphan/unavailable states, stable source navigation, and confirmed unlink. Metadata, Reading Note, Note Block, Project, and link command states remain independent. There is no autosave, combined save, Note Block delete/reorder, Project delete/unarchive, Tag write, or Settings write.

## Local development

Start FastAPI from the repository root, then start the frontend:

```powershell
.\scripts\run_api.ps1
.\scripts\run_frontend.ps1
```

The frontend uses a strictly allowlisted same-origin server bridge to `http://127.0.0.1:8000` by default. In addition to bounded GETs and the two Reader commands, the bridge permits only POST `/projects`, PATCH `/projects/{project_id}`, POST `/projects/{project_id}/archive`, POST `/projects/{project_id}/paper-links`, and DELETE `/projects/{project_id}/paper-links/{link_id}`. Copy `.env.example` to `.env.local` only when the API address needs to change.

## Commands

```powershell
npm run dev
npm run build
npm test
npm run lint
```

The shell remains navigable when FastAPI is offline and displays explicit unavailable states. Failed and conflicting Project commands never erase the current draft. Archived Project detail remains readable but has no Project edit, archive, add-link, or unlink controls. The Paper picker comes from the real bounded Paper collection and never fabricates records.
