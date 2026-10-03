# Frontend

The React workspace for Academic Figure Generator, OpenAI Edition.

Project documentation: [English](../README.md) | [简体中文](../README.zh-CN.md).

## Run Locally

Use Node.js 22.12+ with npm. Start the backend on port 8000, then run from this directory:

```bash
npm ci
npm run dev -- --host localhost --port 5173
```

Open [localhost:5173](http://localhost:5173).

The default API base is `http://localhost:8000/api/v1`. To change it, set
`VITE_API_BASE_URL` in a local `frontend/.env` and restart Vite. Include the
`/api/v1` suffix, and allow the frontend origin in the backend's `CORS_ORIGINS`.
Never put an OpenAI API key in a `VITE_*` variable: Vite exposes those values to the browser.

## Source Map

| Path | Responsibility |
| --- | --- |
| `src/pages/Projects.tsx` | Project creation and listing |
| `src/pages/ProjectWorkspace.tsx` | Documents, section selection, prompts, generation, and editing |
| `src/pages/Generate.tsx` | Direct prompt-to-image workflow |
| `src/pages/ColorSchemes.tsx` | Palette management |
| `src/pages/Settings.tsx` | Configuration reference, not a live settings editor |
| `src/components/Layout.tsx` | Navigation, responsive sidebar, and project branding |
| `src/lib/api.ts` | Backend URL and shared HTTP client |
| `public/logo.png`, `public/favicon.png` | Browser-ready copies of the root project logo |

The UI currently uses primarily Chinese labels. Root documentation is bilingual.

## Checks

```bash
npm run build
npm run lint
```

The build runs TypeScript checks before producing `dist/`. Use `npm run preview`
to inspect that build locally; the backend must still be running for API operations.

Logo source and generation notes: [Branding](../docs/branding.md).
