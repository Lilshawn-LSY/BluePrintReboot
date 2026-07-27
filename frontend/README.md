# BluePrintReboot frontend

The v1.5.3 frontend is a desktop-first local application built with Vinext/Next.js, React, and TypeScript. Settings now consumes one strict, bounded, read-only summary for application, workspace, lightweight data-integrity, and backup-readiness facts. Projects, Project Detail, and Tags retain their real local GET contracts, and the Reader retains separate explicit saves for seven bibliographic fields and the persisted Reading Note. The established Streamlit interface remains available for the complete local workflow and every maintenance action.

## Local development

Start FastAPI from the repository root, then start the frontend:

```powershell
.\scripts\run_api.ps1
.\scripts\run_frontend.ps1
```

The frontend uses a strictly allowlisted same-origin server bridge to `http://127.0.0.1:8000` by default. The bridge permits the bounded Health, Library, Papers, Reader, Projects, Tags, and exact Settings summary GET routes plus only metadata PATCH and Reading Note PUT. Copy `.env.example` to `.env.local` only when the API address needs to change.

## Commands

```powershell
npm run dev
npm run build
npm test
npm run lint
```

The shell remains navigable when FastAPI is offline and displays explicit unavailable states. Settings distinguishes verified zeroes from unavailable diagnostics, keeps partial section warnings visible, and offers only the shared GET retry. It contains no configuration, backup, restore, repair, debug, or data-removal controls.
