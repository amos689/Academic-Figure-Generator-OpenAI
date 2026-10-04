# README Animation

The English and Chinese GIFs walk through the [MAE paper example](../../examples/showcase/README.md): the published paper, selected method section, style choices, drawing prompt, Image API generation, and two reference-image edits. The sequence then holds on the complete finished figure, without detail-view slides or a layout-adjustment screen.

The terminal-style pacing follows [paper-preflight](https://github.com/amos689/paper-preflight). This renderer is implemented for the figure workflow and uses the saved example's text, metadata, and finished image. It condenses the waiting time; recorded durations appear alongside the API steps.

The first step displays a short method summary from `examples/showcase/mae/method-notes.txt`. The generation itself used Section 3 extracted from the official CVPR 2022 PDF. The source URL, selected section, and coverage are recorded in the manifest.

## Build

From the repository root, after installing the backend dependencies:

```bash
uv run --project backend --locked python docs/demo/layout_mae.py
uv run --project backend --locked python docs/demo/make_gif.py
```

No server, API key, network access, or additional generation is needed. Output:

- `docs/demo/demo.gif`: English
- `docs/demo/demo.zh-CN.gif`: Chinese

Use `--lang en` or `--lang zh-CN` to build one version. The script finds standard fonts on macOS, Linux, and Windows. Supply `--font`, `--mono-font`, and `--zh-font` when fonts live elsewhere; Chinese rendering needs a CJK font.

`layout_mae.py` reuses photographic patches and the loss formula from the saved edit outputs, lays out the operators on a 4800 × 1920 canvas, and draws connectors at exact node ports. It preserves the source files and writes `examples/showcase/mae/figure.png`. Operator labels are checked against their internal padding and connector clearance. Subscripts use positioned digits, avoiding font-dependent Unicode subscript glyphs. Supply `--font` to use a custom sans-serif font.

GIF playback scales this finished PNG to fit the frame and uses a shared 256-color palette. The README links the full-resolution PNG for inspection. Both scripts run locally without a server or provider request.
