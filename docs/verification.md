# Workbench Verification

Local verification completed on 2026-10-04.

| Area | Result |
| --- | --- |
| Backend | 434 tests passed; Ruff checks passed. |
| Frontend | 19 unit tests, ESLint, TypeScript, and production build passed. |
| Clean installs | Locked backend install and a separate `npm ci` installation both passed their checks. |
| Database upgrade | A copy of the legacy database migrated with all prior field values retained, a pre-migration backup, and a successful SQLite integrity check. |
| Mocked browser workflow | Prompt conflicts and restoration, explicit section selection, palette inheritance, queued cancellation, manual retry, image comparison, mask pixels, exports, and unknown-outcome handling passed. |
| Live local UI | English/Chinese navigation, 390 px mobile and desktop layouts, effective configuration, real completed jobs, image inspection, and PDF download verified. The downloaded PDF matches the stored export. |
| OpenAI integration | Two prompt requests, two image generations, and one masked image edit completed. No extra provider calls were made to build the README animation. |
| Vector output | SVG, PDF, and native draw.io exports completed. PDF text and vector paths remain editable; source metadata is retained. |
| Public example | Source text, both prompt stages, FigureSpec, settings, token usage, and the selected original PNG are published together. |
| README animation | Both languages render and loop; all local documentation links resolve. Desktop and mobile previews were inspected. |
| Runtime logs | Redaction preserves Uvicorn access-log fields; the restarted local servers return healthy responses without formatter errors. |

The image model's output still needs scientific and visual review. The selected
example has a corpus-routing issue and a short stray blue line. It is retained as
generated; the FigureSpec describes the intended connectivity separately.

The masked edit and the second generated example were tested but are not part of
the public gallery. The user selected the original retrieval image for the README.

Current tests do not measure aesthetic quality or prove that every source quote
supports a generated claim. Public multi-user deployment and distributed workers
are outside this release.
