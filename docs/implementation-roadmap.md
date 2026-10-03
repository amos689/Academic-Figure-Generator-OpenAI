# Research Workbench Upgrade

Status: all three stages implemented, verified, and published to `main`.
Approved scope: all three stages, with incremental, substantive commits.

## Stage A: Reliable Core and Real Examples

- [x] Contain storage paths, bound uploads, and stop serving the entire data directory.
- [x] Reject cross-origin mutation requests and sanitize error/log output.
- [x] Introduce database migrations without losing existing projects or figures.
- [x] Persist jobs, commit before dispatch, limit concurrency, and detect interrupted work.
- [x] Connect prompt editing, palette selection, and uncropped image previews.
- [x] Produce public examples through the application, retain inputs and actual settings.
- [x] Add bilingual README animations for the user-selected retrieval figure and its generation process.

## Stage B: Research Workflow

- [x] Preserve document tables, section identifiers, and relevant long-document context.
- [x] Generate source-linked figure specifications and validate their quote references.
- [x] Integrate explicit classic/pastel styles and consistent per-project direction.
- [x] Store prompt revisions, image ancestry, favorites, selections, and provenance.
- [x] Show effective non-secret configuration, key source, duration, and available usage.
- [x] Rebuild the workspace as typed components with English/Chinese UI.
- [x] Add deterministic quality checks, fixed evaluation fixtures, and CI coverage.

## Stage C: Editing and Export

- [x] Support reference uploads and drawn edit masks with accurate capability wording.
- [x] Validate editable FigureSpec, including labels, groups, links, and source references.
- [x] Render framework/flow diagrams into editable SVG and vector PDF.
- [x] Evaluate and, if verified, support native draw.io export.
- [x] Store export history and verify exported text, geometry, and downloads.

## Release Gates

- [x] Backend unit/integration tests, frontend checks, and clean-install checks pass.
- [x] Browser verification covers desktop/mobile, both languages, and error recovery.
- [x] Real generation and masked editing are verified; the selected original image is documented publicly.
- [x] Secret scanning covers the publication tree and outgoing commits.
- [x] Remote branch matches the release; GitHub contributor attribution is verified.

Key precedence stays system environment, backend `.env`, root `.env`, then code defaults.
Keep OpenAI as the only hosted AI provider and preserve quality-first defaults.
Never automatically resubmit a billed request whose outcome is unknown. Preserve
upstream authorship.

The README uses the user-selected generated retrieval figure, not upstream example
images. Other generated drafts and the masked edit remain local QA artifacts.
See [verification notes](verification.md) for the checks and known limits.
