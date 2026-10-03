# Phase 2 Technical Design: Implemented Workbench

This document describes the current implementation, not the former
Celery/MinIO/Claude reconstruction proposal. Product scope and limitations live in
[requirements](./phase2-requirements.md); field-level contracts live in the
[API contract](./workbench-api-contract.md). The
[roadmap](./implementation-roadmap.md) tracks release planning separately.
Preserve existing upstream attribution and the [MIT license](../LICENSE).

## Architecture

```text
React/TypeScript workbench (Vite, English/Chinese)
    -> FastAPI /api/v1 (one web worker, local use only)
        -> SQLAlchemy + SQLite: projects, documents, prompts/revisions,
           images, jobs, exports, presets
        -> LocalStorageService: uploads/, figures/, exports/
        -> persisted JobRunner (bounded asyncio consumers)
            -> spawned process pool: parse documents, render vector exports
            -> worker threads: synchronous OpenAI SDK calls
                -> configured OpenAI API base: text, image generation/edits
```

There is no broker, remote object store, distributed scheduler, or hosted
evaluation service. The frontend polls active jobs/resources and retains usable
panel data when another panel cannot load. Existing `/api/v1` routes and legacy
model fields remain compatible; `claude_model` is an alias for stored generation
model metadata, not an Anthropic integration.

## Startup, Persistence, And Jobs

[Application lifespan](../backend/app/main.py) acquires a nonblocking
`<DATABASE_PATH>.worker.lock`, runs packaged Alembic migrations, seeds presets,
and starts the job runner. A populated database needing migration receives a
SQLite backup first. Foreign keys and a busy timeout are enabled. Shutdown stops
the runner and offline process pool, disposes the engine, and releases the lock.

Use **one Uvicorn worker per SQLite database**. The file lock rejects a second
server using the same database; it is not a distributed lease. `MAX_CONCURRENT_JOBS`
bounds runner concurrency and the offline process pool, not web-worker count.

[JobService](../backend/app/services/job_service.py) persists operation kind,
payload, resource ID, status/stage, result/error, timing, and retry ancestry.
Submission commits the job and resource before the runner can claim it. Consumers
claim queued jobs using a conditional SQL update, then commit `running` before
executing a handler. Successful resource changes and job results are committed
together after execution.

```text
queued -> running -> succeeded | failed | interrupted
queued -> cancelled
failed | interrupted -> explicit new retry attempt
```

- Idempotency keys bind to a project/kind/payload hash. Identical submissions reuse
  the job; conflicting reuse returns 409. Retry uses one successor per attempt.
- Startup marks leftover `running` jobs `interrupted`; queued work remains eligible.
  Shutdown interruption likewise records uncertainty instead of resubmitting.
- Only queued jobs can be cancelled. A started provider call cannot be recalled;
  cancellation of its local task does not prove the remote request stopped.
- SDK automatic retries are disabled. Retrying a failed/interrupted paid operation
  is explicit, and the user must consider unknown provider outcomes. Local job
  durability is not an exactly-once provider or billing guarantee.
- Failures update the associated resource only when it still belongs to that
  attempt. Public errors are sanitized rather than persisting provider bodies.

[ProcessService](../backend/app/services/process_service.py) lazily creates a
`ProcessPoolExecutor` with the `spawn` multiprocessing context. Its supported
operations are document parsing and vector export. PyMuPDF parsing, font
measurement, and rendering stay inside these processes because its APIs must not
be shared across threads. Synchronous provider SDK calls use `asyncio.to_thread`
instead, so they do not block the event loop.

[LocalStorageService](../backend/app/services/local_storage_service.py) confines
resolved paths to resource directories and publishes files using temporary files
plus atomic replacement. Downloads resolve a database-owned resource; the whole
data directory is not mounted as static content. Files and SQLite are not one
atomic transaction: a crash can leave an unreferenced file. Backup, retention,
disk capacity, and recovery remain local operational responsibilities.

## Documents And Context

[DocumentService](../backend/app/services/document_service.py) preserves its
`parse(content: bytes, file_type: str) -> dict` interface and returns full text, sections, and page
count. PDF uses native extracted text and heuristic headings; TXT supports simple
section splitting. DOCX walks body paragraphs and tables in document order, with
table content and source locations retained. Uploads and ZIP/XML processing are
bounded; unsafe package paths, unsupported encryption, and unsafe XML constructs
are rejected. There is no OCR or faithful reconstruction of PDF page/table layout.
Documents without extractable text fail with a clear request for a text source.

[ContextService](../backend/app/services/context_service.py) exposes:

```text
ContextService.select(sections, section_indices=None, *, max_chars=32000) -> dict
```

`None` selects all sections; an empty selection selects none. The result contains
`text`, excerpt `sections`, `source_refs`, `coverage`, and `truncated`. Original
zero-based section indices remain stable. Exact quote spans and offsets refer to
parsed section content, not raw file-byte offsets. A deterministic weighted
allocation favors methods/results/tables, distributes excerpts through long
sections, and preserves selected table rows rather than slicing them mid-row.
Omission markers count toward the character budget. This is bounded extractive
selection, not token-exact budgeting, summarization, or guaranteed retention of
every important fact. Generation metadata records context coverage.

Prompt jobs retain the selected document/section IDs and model/style settings;
execution reloads the source document and rebuilds bounded context. A source that
is no longer available causes a failure, not fabricated fallback content.

## Revisions And Provenance

[PromptService](../backend/app/services/prompt_service.py) stores prompt text and
optional FigureSpec in revision snapshots. A save checks `expected_revision` and
performs a conditional `UPDATE ... WHERE revision = observed_revision`. A lost
race or stale token returns 409. Clients should always send the token: legacy
omission still guards the database update race but cannot detect every stale user
view. Restore copies a historical snapshot into a **new** revision.

A text change without an explicitly supplied replacement spec clears the prior
spec. The frontend keeps a dirty draft during polling and offers conflict
resolution rather than silently replacing it. Image jobs snapshot final prompt,
prompt revision, model, quality, style/palette, and reference/mask paths. Edits add
a child image; provider-returned dimensions, usage, and timing are stored when
available. Export jobs snapshot the revision, FigureSpec, format, width, and style.
Missing historical usage is unknown, not zero or an inferred monetary cost.

[Spec-generation jobs](../backend/app/services/spec_generation_service.py) snapshot
the source prompt revision. They apply a result only while that revision remains
current, using the same CAS update. A detected stale result is retained in the
job result with `applied: false`; it does not overwrite the newer prompt. A race
during the guarded save returns a conflict rather than forcing an overwrite.

## FigureSpec And Evidence

[FigureSpec v1](../backend/app/schemas/figure_spec.py) is a bounded semantic schema:
nodes, directed edges, groups, labels, LR/TB direction, and source references. IDs
are globally unique; edge/group references must resolve. It rejects raw markup,
scripts, executable URLs, extra fields, and invalid text. It does not accept
caller-supplied arbitrary SVG or geometry.

Generated nodes and edges require quotes from the original section indices in the
context actually supplied to generation. Legacy prompt-to-spec derivation uses
the owning document when present; otherwise the user-authored prompt is its sole
source section. Document-backed prompt saves and export submissions validate
provided quotes against the owning document's ordered sections.

Quote checking normalizes whitespace and tests substring presence. This is
**lexical validation, not entailment**: a valid quote may still be irrelevant to
the claim or fail to justify an edge. The schema permits empty source lists for
manually supplied specs, and validation without document text proves structure
only. Do not present a schema-valid export as verified science or treat coverage
metadata as proof that no evidence was omitted.

[Offline fixture evaluation](../examples/evaluation/README.md) is a separate,
pure service: `FigureEvaluationService().evaluate(spec, fixture) -> dict`.
Its `structural` and `grounding` reports cover exact required labels/edges, quote
indices/content, and explicitly approved source-supported numeric wording.
`aesthetic.status` is always `not_evaluated`. No network, model judge, hosted Evals
API, or rendered-image scoring is used. These original educational fixtures are
regression cases, not measurements of general model quality or semantic truth.

## Raster Editing And True Exports

[ImageService](../backend/app/services/image_service.py) uses the image-generation
endpoint for new images and the image-edit endpoint when a reference is supplied.
Missing reference files fail instead of silently switching operation. Decoding
validates PNG/JPEG/WebP bytes and bounded pixel dimensions. A mask must be PNG,
contain alpha transparency, and match the reference dimensions; the frontend
maps strokes to original image coordinates and exports transparent edit regions.
The mask is provider guidance: **there is no pixel-preservation guarantee outside
the masked area**, and no local compositing step that enforces one.

[ExportService](../backend/app/services/export_service.py) requires a validated
FigureSpec and queues a local export. It never derives vectors from raster pixels
or calls a model. [FigureLayoutService](../backend/app/services/figure_layout_service.py)
computes deterministic font-measured layout shared by
[VectorExportService](../backend/app/services/vector_export_service.py):

| Format | Actual output |
| --- | --- |
| SVG | Editable text, shapes, groups, and connector geometry; semantic spec in metadata. |
| draw.io | Native `mxGraphModel` cells, groups, vertices, and connected edges, not an embedded screenshot. |
| PDF | Vector shapes/paths and live text with font support; attached FigureSpec JSON. |

Framework/flow diagrams are the supported domain. Layout derives from the spec,
not a generated image's appearance. Unsupported fonts/glyphs, excessive layout
height, or impossible routing raise errors. Rendered exports still need visual
inspection, and external editors may substitute fonts. Exported spec metadata and
PDF attachments include source quotes: review them before sharing. No import or
bidirectional synchronization with externally edited artifacts is implemented.

## Trust Boundary And Configuration

The app has **no authentication, authorization by user, or tenant isolation**.
Run on loopback only; do not expose the backend or frontend to a LAN, public host,
or tunnel. Trusted-host validation, restricted CORS, mutation-origin checks,
bounded uploads, and resource/path checks are defense in depth for local use,
not a public-deployment security model. Originless clients are not authenticated.

[Settings](../backend/app/config.py) resolve normal runtime values in this order:
process environment, `backend/.env`, root `.env`, then code defaults. Explicit
constructor values override these sources for tests/programmatic use. Empty or
whitespace-only API keys do not mask a populated lower-priority credential.
Cached settings require a restart after file/environment changes.

The configuration endpoint is read-only and exposes key presence/source, never
the secret or its prefix. Its explicit access check retrieves configured model
metadata and does not generate content. Public errors/logs avoid raw provider
responses, request content, and credentials. Generation nevertheless sends selected
source/prompt content and reference/mask images to the configured provider; local
storage is not a promise that requested generation stays offline. Use private
environment configuration, not committed keys. Do not assume local data or backups
are encrypted or safe to publish.

## Verification And Extension Points

[CI](../.github/workflows/ci.yml) runs full backend pytest and Ruff over `app tests`,
and frontend `npm ci`, build, and tests. Backend tests exercise job recovery,
idempotency, revisions, migrations, privacy, process isolation, document/context
selection, source validation, masks, and real SVG/PDF/draw.io contents. Evaluation
fixtures run offline; provider integrations use mocks. Frontend checks cover
workbench state/helpers; browser and exported-artifact visual review remain
separate release gates.

Future public hosting needs authentication, authorization, deployment hardening,
and a different worker/storage design. OCR, semantic entailment checks, aesthetic
evaluation, exact-pixel editing, arbitrary raster reconstruction, a graphical
diagram editor, export round trips, and PPTX need separate designs and tests.
Do not add a distributed queue or remote storage as documentation-only features.
