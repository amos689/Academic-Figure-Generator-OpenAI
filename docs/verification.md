# Workbench Verification

Workbench release verification completed on 2026-10-04. The MAE showcase update is verified locally and approved for publication.

| Area | Result |
| --- | --- |
| Backend | 442 tests passed after the MAE update; Ruff checks passed. |
| Frontend | 19 unit tests, ESLint, TypeScript, and production build passed. |
| Clean installs | Locked backend install and a separate `npm ci` installation both passed their checks. |
| Database upgrade | A copy of the legacy database migrated with all prior field values retained, a pre-migration backup, and a successful SQLite integrity check. |
| Mocked browser workflow | Prompt conflicts and restoration, explicit section selection, palette inheritance, queued cancellation, manual retry, image comparison, mask pixels, exports, and unknown-outcome handling passed. |
| Live local UI | English/Chinese navigation, 390 px mobile and desktop layouts, effective configuration, real completed jobs, image inspection, and PDF download verified. The downloaded PDF matches the stored export. |
| OpenAI integration | The prior release completed two prompt requests, two image generations, and one masked edit. The MAE update adds one paper-grounded prompt, one image generation, and two reference-image edits. Local layout and GIF rendering make no provider calls. |
| Vector output | SVG, PDF, and native draw.io exports completed. PDF text and vector paths remain editable; source metadata is retained. |
| Public example | MAE (CVPR 2022), Section 3, replaces the educational retrieval example. The publication set includes the paper link, requests, prompts, graph, usage, saved image outputs, and the local wide-layout script. |
| README animation | Both languages render and loop in 31.44 seconds, ending with a 10.5-second view of the complete figure. Local documentation links resolve; desktop and mobile previews were inspected. |
| Runtime logs | Redaction preserves Uvicorn access-log fields; the restarted local servers return healthy responses without formatter errors. |
| Publication | The MAE update is approved for publication. Release files and outgoing commits are scanned for credentials and private local paths. |

The MAE figure was checked against the official paper's method section, including
visible-only encoding, shared mask tokens, positions for all decoder inputs, and
masked-only loss. The [render review](../examples/showcase/mae/visual-contract.md#render-review)
records the final 5:2 layout, connected ports, and label-padding checks. The bicycle prediction
is a method illustration, not an MAE inference result. Prior educational drafts
remain local and are no longer the README showcase.

Current tests do not measure aesthetic quality or prove that every source quote
supports a generated claim. Public multi-user deployment and distributed workers
are outside this release.
