# Phase 2 Requirements: Research Workbench

Status: implemented behavior and explicit limits. This replaces the earlier
export-only proposal; it is not a claim that every release gate has been met.
See the [API contract](./workbench-api-contract.md) for request/response fields,
the [technical design](./phase2-technical-design.md) for implementation details,
and the [roadmap](./implementation-roadmap.md) for release planning.
Existing upstream attribution and the [MIT license](../LICENSE) remain unchanged.

## Scope

The application is a single-user, local research-figure workbench: import source
documents, select evidence, generate and revise prompts, generate/edit raster
images, and export reviewed semantic diagrams. OpenAI is the only hosted AI
provider integrated into the current runtime. Document parsing, vector exports,
and fixture evaluation run locally without model calls.

There is no Celery/Redis queue, MinIO object store, Claude provider, or automatic
vision-critic pipeline. Historical names such as `claude_model` are compatibility
fields, not descriptions of the current provider.

## Implemented Workflow

| Area | Required behavior in the current workbench |
| --- | --- |
| Documents | Accept bounded PDF, DOCX, and TXT uploads; persist parse status and a durable job; expose ordered source sections. DOCX paragraphs and tables retain document order. |
| Context | Select a document and its sections explicitly in the UI. Allocate a deterministic character budget across selected sections, favoring methods, results, and tables; spread excerpts through long sections instead of taking every section's prefix. Preserve original indices, exact excerpts, and coverage/truncation metadata. |
| Prompts | Generate source-linked prompts and supported FigureSpecs with classic/pastel styles, project palettes, and quality/draft profiles. Allow text/spec review, revision history, and restore-as-new-revision. |
| Images | Generate raster images from saved prompts; inspect uncropped previews, compare versions, mark favorites/selections, and inspect saved generation provenance. Edits create a child image with its parent recorded. |
| Editing | Accept a reference image and optional drawn/uploaded mask. Validate the image and mask before a provider call. The mask guides generation; unmasked pixels may still change. |
| Exports | Render reviewed FigureSpec v1 diagrams into editable SVG, native draw.io, and vector PDF with live text. Keep export history tied to the submitted prompt revision and spec snapshot. |
| Configuration | Show effective non-secret settings, key presence/source, and available usage metadata. Connectivity checks are explicit, non-generative model-access requests, not background generation. |

The bilingual frontend provides these workflows through typed workbench panels.
FigureSpec editing is structured text/JSON editing with validation, not a
freeform SVG or draw.io canvas editor.

## Reliability Requirements

- Persist job inputs and resource records before dispatch. Track `queued`,
  `running`, `succeeded`, `failed`, `interrupted`, and `cancelled` states in SQLite.
- Recover persisted running jobs as interrupted after restart. Do not silently
  repeat a possibly billed request. Cancellation applies only before a job starts;
  failed/interrupted attempts require an explicit retry.
- Use request idempotency to avoid duplicate submission, not to claim exactly-once
  execution at the provider. An unknown provider outcome still needs user review.
- Run one backend web worker per database. A nonblocking file lock guards the
  database's worker lifecycle; bounded job concurrency is not multi-worker support.
- Run document parsing and vector rendering in a spawned process pool, including
  PyMuPDF text extraction and font work. Do not share PyMuPDF operations through
  worker threads.
- Save prompt changes using revisions and compare-and-swap (CAS). Stale
  `expected_revision` values return 409. Restore creates a new revision, and a
  text-only edit invalidates the old FigureSpec when the text changes.
- Preserve existing database rows through migrations and keep a pre-upgrade
  SQLite backup when a migration is needed. Local storage uses contained paths
  and atomic file replacement; it is not a transactional object store.

## Evidence And Quality Boundaries

Source indices are zero-based identifiers from the parsed document. Selecting or
truncating context must not renumber them. Excerpts and table rows are source text,
not generated summaries; coverage describes included text, not scientific coverage.
A bounded context may omit sections or important details and must be identified as
truncated. No OCR is implemented: image-only documents need a text-based source.

Generated nodes and edges must cite quotes present in the supplied context.
Document-backed save/export paths check supplied references against document
sections. These are whitespace-normalized lexical checks, **not entailment**:
an existing quote does not prove a label, causal edge, or numerical claim correct.
Schema-only validation also does not establish provenance. Users must review
claims, labels, connections, results, and source suitability before publication.

The [offline evaluation fixtures](../examples/evaluation/README.md) check exact
required labels/edges, source quotes/indices, and explicitly allowed numeric
wording. Their educational values are not measured research outcomes. Structural
and lexical checks are separate from aesthetics, which the evaluator marks
`not_evaluated`. No hosted evaluation API or model judge is involved; passing a
fixture is not a general factual or visual-quality certificate.

## Export Guarantees And Limits

- SVG contains editable text/shapes/connectors, draw.io contains native cells and
  connections, and PDF contains vector geometry and live text. These are rendered
  from FigureSpec, not raster images placed in differently named containers.
- The supported abstraction is a bounded node/edge/group framework or flow
  diagram. Arbitrary illustrations, photographs, plots, or generated raster
  images are not losslessly reconstructed into this abstraction.
- Semantic labels and connectivity come from the reviewed spec; geometry comes
  from the local layout engine. Unsupported glyphs or unrouteable/crowded layouts
  fail explicitly. External editors may substitute fonts or alter appearance.
- A missing FigureSpec must be supplied or separately generated/reviewed before
  export. Export itself makes no provider call. PDF is a publication format, not
  a native graph-editing or round-trip editing format.

## Local Security And Settings

There is **no user authentication or tenant isolation**. Bind the backend and
frontend to loopback. Do not expose them on a LAN, public host, or public tunnel.
Host/origin checks and CORS reduce browser-origin risks; they are not access control
for an untrusted client or protection for a public deployment.

Runtime settings resolve in this order: process environment, `backend/.env`, root
`.env`, then code defaults. Empty credential values do not hide a populated
lower-priority key. Settings are cached; restart after configuration changes.
The UI exposes key presence and provenance, never the key or a key prefix.
Provider diagnostics must not echo raw exceptions, request bodies, or credentials.
Source excerpts and reference images are sent to the configured provider only
when the associated generation operation is requested; this is local-first, not
an entirely offline application. Local data and exported source metadata may
contain unpublished material and require the user's publication review.

## Verification And Future Work

CI runs full backend `pytest` and `ruff check app tests`, plus frontend lockfile
installation (`npm ci`), build, and tests. Deterministic tests cover jobs/recovery,
revisions/CAS, parsing/context, upload/privacy boundaries, masks, source checks,
and actual vector artifacts. Provider calls are mocked; tests and fixture scoring
do not require paid calls. Visual review remains a separate release activity.

Not implemented or promised: public multi-user hosting, distributed workers,
automatic paid retries, OCR, semantic entailment checking, aesthetic scoring,
pixel-identical masked edits, arbitrary raster vectorization, embedded draw.io
editing, imported-export round trips, or PowerPoint export. New capabilities need
their own design and verification; no fixed cost or latency is guaranteed.
