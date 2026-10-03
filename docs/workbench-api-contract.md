# Workbench API Contract

The `/api/v1` prefix and existing project/document/image download URLs stay compatible.
This document describes the approved target contract; implementation status is tracked
in [the roadmap](./implementation-roadmap.md).

## Jobs

`GET /jobs?project_id=...` returns a list. `GET /jobs/{id}` returns one job.
Fields: `id`, `project_id`, `kind`, `status`, `stage`, `resource_id`, `result`,
`error`, `created_at`, `started_at`, `finished_at`, `retry_of`.
Kinds: `document`, `prompt`, `image`, `spec`, `export`.
States: `queued`, `running`, `succeeded`, `failed`, `interrupted`, `cancelled`.
Result objects contain resource IDs, such as `prompt_ids`, `image_id`, or `export_id`.
`POST /jobs/{id}/cancel` cancels queued work only. Running image calls cannot be recalled.
`POST /jobs/{id}/retry` explicitly creates another attempt for failed/interrupted work.
All job-creating JSON requests accept an optional `idempotency_key`.

## Prompts and Documents

`POST /projects/{id}/prompt-jobs` creates a job (202). Body: `document_id`,
`section_indices`, `color_scheme`, `custom_colors`, `figure_types`, `user_request`,
`max_figures` (1-8), `template_mode`, `style_preset` (`classic` or `pastel`),
`profile` (`quality` or `draft`). The synchronous legacy prompt endpoint stays available.

Prompt responses additionally expose `generation_model`, `revision`, `figure_spec`,
`style_preset`, and `generation_metadata`. The legacy `claude_model` remains an alias.
`PUT /prompts/{id}` accepts `edited_prompt`, optional `figure_spec`, and
`expected_revision`; stale revisions return 409. `GET /prompts/{id}/revisions`
returns revision records (`id`, `revision`, `prompt_text`, `figure_spec`, `created_at`).
`POST /prompts/{id}/restore` accepts `revision` and creates a new revision.
`POST /prompts/{id}/spec-jobs` derives an editable structure for a legacy prompt.

Document upload returns a document record with a parse status. Parsing is tracked
through jobs. The frontend explicitly chooses a source document for prompt generation.

## Images

Existing image generation endpoints still return an image status (202), with `job_id`.
Requests additionally accept `style_preset`, `profile`, and `idempotency_key`.
Image responses add `job_id`, `parent_image_id`, `prompt_revision`, `generation_model`,
`quality`, `style_preset`, `generation_metadata`, `favorite`, and `selected`.
`PATCH /images/{id}` accepts `favorite` and/or `selected`.
Image edits use multipart `edit_instruction`, optional `reference_image`, and optional
`mask_image`. Masks must match the reference dimensions and contain transparency.
`GET /images/{id}/provenance` returns saved generation inputs/settings without credentials.

## Effective Configuration

`GET /configuration` returns `api_key_configured`, `api_key_source`, `api_base`,
`text_model`, `text_reasoning_effort`, `text_max_output_tokens`, `image_model`,
`image_quality`, `max_upload_size_mb`, `max_concurrent_jobs`, `styles`, `profiles`,
and `usage_summary`. Never return the key or its prefix. `GET /styles` returns presets.
`POST /configuration/check` explicitly checks API connectivity/model access.

## Editable Figures and Exports

FigureSpec v1 has `version: 1`, `title`, `caption`, `direction` (`LR` or `TB`),
`nodes`, `edges`, and `groups`. Nodes: `id`, `label`, `role` (`input`, `process`,
`output`, `note`), optional `group_id`, and `sources`. Edges: `id`, `source`,
`target`, `label`, `kind` (`data`, `control`, `skip`), and `sources`.
Groups: `id`, `label`. Source references: `section_index` and `quote`.
IDs are unique and every edge/group reference must resolve. No raw SVG or scripts.

`POST /prompts/{id}/exports` accepts `format` (`svg`, `pdf`, `drawio`), optional
`figure_spec`, and `width` (640-4096), returning a job (202). A missing specification
must be generated/reviewed first; raster files are not relabeled as editable vectors.
`GET /projects/{id}/exports` lists records: `id`, `prompt_id`, `format`, `created_at`,
`generation_status`, `width_px`, `height_px`, `job_id`, and `generation_error`.
`GET /exports/{id}/download` downloads the artifact.

All implementation paths must preserve source data and old database rows. Structured
diagram exports target framework/flow diagrams; they do not promise lossless conversion
of arbitrary illustrations. Any unsupported operation must fail clearly, not silently.
