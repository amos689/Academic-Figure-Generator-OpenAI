# Academic Figure Generator (Backend)

FastAPI service for the typed workbench: documents, prompt revisions, FigureSpec,
image generation and editing, and editable SVG, PDF, and draw.io exports.

Project setup and configuration: [English](../README.md) | [简体中文](../README.zh-CN.md).

## Development

Use Python 3.12+ and uv. From this directory:

```bash
uv sync --locked --extra dev
DEBUG=true uv run --no-sync uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Run the same sync command after pulling dependency updates. The API is served at
`/api/v1`; `DEBUG=true` enables [the API reference](http://localhost:8000/docs).

## Jobs and Migrations

Document parsing, prompt generation, images, FigureSpec generation, and exports use
SQLite-backed jobs. The in-process runner starts with FastAPI; run one backend
worker per database and set `MAX_CONCURRENT_JOBS` for task concurrency. The jobs API
supports status polling, cancelling queued jobs, and retrying failed or interrupted
attempts. Jobs left running at restart become `interrupted`.

Startup applies the packaged Alembic migrations automatically. Before upgrading an
existing database, it saves a SQLite snapshot in `migration-backups/` beside the
database. A database already at the current revision needs no new snapshot.

## Source Map

| Path | Responsibility |
| --- | --- |
| `app/api/v1/`, `app/schemas/` | Workbench endpoints and typed request/response contracts |
| `app/services/job_service.py`, `job_handlers.py` | Persistent job lifecycle and task dispatch |
| `app/services/document_service.py`, `context_service.py` | Parsing, sections, and source context |
| `app/services/prompt_generation_service.py`, `image_generation_service.py` | Prompt revisions and image workflows |
| `app/services/figure_layout_service.py`, `vector_export_service.py` | Offline layout and editable vector exports |
| `app/core/database.py`, `app/migrations/` | SQLite setup, backups, and schema upgrades |
| `tests/` | API, jobs, migrations, parsing, and export regression tests |

## Checks

```bash
uv run --no-sync pytest -q
uv run --no-sync ruff check app tests
```

Tests use temporary databases and mocked provider calls; no live API calls are needed.
