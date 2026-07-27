# BluePrintReboot frontend

The v1.5.1 frontend is a desktop-first local application built with Vinext/Next.js, React, and TypeScript. Its Reader exposes separate explicit saves for seven bibliographic fields and the persisted Reading Note while the established Streamlit interface remains available for the complete local workflow and maintenance actions.

## Local development

Start FastAPI from the repository root, then start the frontend:

```powershell
.\scripts\run_api.ps1
.\scripts\run_frontend.ps1
```

The frontend uses a strictly allowlisted same-origin server bridge to `http://127.0.0.1:8000` by default. The bridge permits the existing GET routes plus only metadata PATCH and Reading Note PUT. Copy `.env.example` to `.env.local` only when the API address needs to change.

## Commands

```powershell
npm run dev
npm run build
npm test
npm run lint
```

The shell remains navigable when FastAPI is offline and displays explicit unavailable states. Projects, Tags, and Settings are honest placeholders until their domain APIs exist.
