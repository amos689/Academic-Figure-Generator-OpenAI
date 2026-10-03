# Research Workbench Upgrade

Status: in progress. Approved scope: all three stages, with incremental, substantive commits.

## Stage A: Reliable Core and Real Examples

- [ ] Contain storage paths, bound uploads, and stop serving the entire data directory.
- [ ] Reject cross-origin mutation requests and sanitize error/log output.
- [ ] Introduce database migrations without losing existing projects or figures.
- [ ] Persist jobs, commit before dispatch, limit concurrency, and detect interrupted work.
- [ ] Connect prompt editing, palette selection, and uncropped image previews.
- [ ] Produce public examples through the application, retain inputs and actual settings.
- [ ] Add bilingual README galleries and editing comparisons with publication approval.

## Stage B: Research Workflow

- [ ] Preserve document tables, section identifiers, and relevant long-document context.
- [ ] Generate source-linked figure specifications and validate semantic references.
- [ ] Integrate explicit classic/pastel styles and consistent per-project direction.
- [ ] Store prompt revisions, image ancestry, favorites, selections, and provenance.
- [ ] Show effective non-secret configuration, key source, duration, and usage.
- [ ] Rebuild the workspace as typed components with English/Chinese UI.
- [ ] Add deterministic quality checks, fixed evaluation fixtures, and CI coverage.

## Stage C: Editing and Export

- [ ] Support reference uploads and drawn edit masks with accurate capability wording.
- [ ] Validate editable FigureSpec, including labels, groups, links, and source references.
- [ ] Render framework/flow diagrams into editable SVG and vector PDF.
- [ ] Evaluate and, if verified, support native draw.io export.
- [ ] Store export history and verify exported text, geometry, and downloads.

## Release Gates

- [ ] Backend unit/integration tests, frontend checks, and clean-install checks pass.
- [ ] Browser verification covers desktop/mobile, both languages, and error recovery.
- [ ] Real public demo generation and edit outputs are inspected and documented.
- [ ] Secret scanning covers the publication tree and outgoing commits.
- [ ] Remote branch matches the release; GitHub contributor attribution is verified.

Key precedence stays system environment, backend `.env`, root `.env`, then code defaults.
Keep OpenAI as the only hosted AI provider and preserve quality-first defaults.
Never automatically resubmit a billed request whose outcome is unknown. Do not rewrite
upstream authorship or create empty commits to change contribution statistics.
