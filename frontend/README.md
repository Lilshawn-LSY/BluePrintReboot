# BluePrintReboot frontend

The v1.5.2 frontend is a desktop-first local application built with Vinext/Next.js, React, and TypeScript. Projects, Project Detail, and Tags now consume real bounded local GET contracts. The Reader retains separate explicit saves for seven bibliographic fields and the persisted Reading Note while the established Streamlit interface remains available for the complete local workflow and maintenance actions.

## Local development

Start FastAPI from the repository root, then start the frontend:

```powershell
.\scripts\run_api.ps1
.\scripts\run_frontend.ps1
```

The frontend uses a strictly allowlisted same-origin server bridge to `http://127.0.0.1:8000` by default. The bridge permits the bounded Health, Library, Papers, Reader, Projects, and Tags GET routes plus only metadata PATCH and Reading Note PUT. Copy `.env.example` to `.env.local` only when the API address needs to change.

## Commands

```powershell
npm run dev
npm run build
npm test
npm run lint
```

The shell remains navigable when FastAPI is offline and displays explicit unavailable states. Projects and Tags distinguish offline, empty, corrupt/read-model, and retry states; Project Detail also distinguishes unknown identity and orphaned paper links. Settings remains an honest placeholder.
