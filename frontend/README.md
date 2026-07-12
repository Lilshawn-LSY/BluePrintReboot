# BluePrintReboot frontend

The v1.2.0 frontend is a desktop-first read-only application shell built with Vinext/Next.js, React, and TypeScript. It runs alongside the existing Streamlit application, which remains the primary interface for write operations, Reader Workspace, PDF rendering, and maintenance actions.

## Local development

Start FastAPI from the repository root, then start the frontend:

```powershell
.\scripts\run_api.ps1
.\scripts\run_frontend.ps1
```

The frontend uses a same-origin server bridge to `http://127.0.0.1:8000` by default. Copy `.env.example` to `.env.local` only when the API address needs to change.

## Commands

```powershell
npm run dev
npm run build
npm test
npm run lint
```

The shell remains navigable when FastAPI is offline and displays explicit unavailable states. Projects, Tags, and Settings are honest placeholders until their domain APIs exist.
