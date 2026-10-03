# Frontend

React and TypeScript workbench for Academic Figure Generator, with English and
Chinese UI labels.

Project documentation: [English](../README.md) | [简体中文](../README.zh-CN.md).

## Run Locally

Use Node.js 24 and npm. Start the backend on port 8000, then run from this directory:

```bash
npm ci
npm run dev -- --host localhost --port 5173
```

Open [localhost:5173](http://localhost:5173).

The typed `workbenchApi` client defaults to `/api/v1`. Vite proxies `/api` to
`http://localhost:8000` during development. To use another backend, set
`VITE_API_BASE_URL` (including `/api/v1`) in `frontend/.env`, allow the frontend
origin in the backend's `CORS_ORIGINS`, and restart Vite.

## Workbench

Projects bring together document sections, prompt revisions, FigureSpec editing,
image history and mask editing, jobs, and vector exports. `useWorkspace` polls every
five seconds while work is active or a resource needs refreshing. Queued jobs can
be cancelled; failed or interrupted jobs can be retried from the jobs panel.

## Source Map

| Path | Responsibility |
| --- | --- |
| `src/pages/Projects.tsx` | Project creation and listing |
| `src/pages/ProjectWorkspace.tsx`, `src/components/workbench/` | Workspace views and editors |
| `src/pages/Generate.tsx`, `ColorSchemes.tsx`, `Settings.tsx` | Direct generation, palettes, effective settings and usage |
| `src/lib/api.ts`, `src/lib/types.ts` | Typed API client and workbench contracts |
| `src/hooks/useWorkspace.ts`, `useResource.ts`, `useAction.ts` | Loading, polling, and mutations |
| `src/lib/figureSpec.ts`, `promptDraft.ts`, `mask.ts` | Spec validation, draft recovery, and mask geometry |
| `src/lib/i18n.ts` | UI language state and translations |
| `tests/*.test.mjs` | Node unit tests |

## Checks

```bash
npm test
npm run lint
npm run build
```

Unit tests use Node's test runner without a browser or live backend. The build runs
TypeScript checks before producing `dist/`. For deployment, route `/api` to the
backend or configure `VITE_API_BASE_URL` before building.
