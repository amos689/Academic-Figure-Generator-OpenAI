# README Animation

The English and Chinese GIFs walk through the [retrieval example](../../examples/showcase/README.md): source text, style choices, generated prompt, Image API request, and the finished PNG.

The terminal-style pacing follows [paper-preflight](https://github.com/amos689/paper-preflight). This renderer is implemented for the figure workflow and uses the saved example's text, metadata, and original image. It condenses the waiting time; the recorded durations are shown alongside the two API steps.

## Build

From the repository root, after installing the backend dependencies:

```bash
uv run --project backend --locked python docs/demo/make_gif.py
```

No server, API key, network access, or additional generation is needed. Output:

- `docs/demo/demo.gif`: English
- `docs/demo/demo.zh-CN.gif`: Chinese

Use `--lang en` or `--lang zh-CN` to build one version. The script finds standard fonts on macOS, Linux, and Windows. Supply `--font`, `--mono-font`, and `--zh-font` when fonts live elsewhere; Chinese rendering needs a CJK font.

The original PNG is unchanged. GIF playback scales it to fit the frame and uses a shared 256-color palette. The README links the full-resolution PNG for inspection.
