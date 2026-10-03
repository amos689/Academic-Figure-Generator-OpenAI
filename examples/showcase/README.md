# Evidence-First Retrieval

**English** · [简体中文](README.zh-CN.md)

![Pastel evidence-first retrieval figure](retrieval/figure.png)

This original educational example follows a question through lexical and semantic retrieval, a shared reranker, an evidence pack, and a cited answer. The source is a short text document written for this project's demonstration.

## Make a Figure Like This

1. Start the application, create a project, and upload [input.txt](retrieval/input.txt).
2. Select the document and all its sections. Choose **Pastel**, **Quality**, **ML TopConf (Seaborn Deep)**, and **Overall framework**, with one figure requested.
3. Paste the `user_request` from [request.json](retrieval/request.json) into the requirements field, then generate the prompt.
4. Review the English prompt and source-linked FigureSpec. This example uses the first prompt revision without manual edits.
5. Choose **16:9**, **4K**, and **Quality**, then generate and download the PNG.

To work from the same drawing instructions directly, paste [prompt.txt](retrieval/prompt.txt) into Direct generation and select the same style, palette, and image settings. New generations can differ in layout and detail.

## What Produced the Image

| Stage | Recorded settings | Duration |
| --- | --- | --- |
| Source selection | Four sections, full coverage | Local parsing |
| Prompt | `gpt-6-astra`, reasoning `max`, Standard processing | 374.517 s |
| Composition | Pastel skill, custom requirement, ML TopConf Deep palette | Included in prompt generation |
| Image | `gpt-image-2.5-sunburst`, quality `max`, 3840 × 2160 | 73.450 s |

The text model returns a 13,245-character drawing prompt plus a FigureSpec with nine nodes and twelve edges. The backend appends its rendering direction and exact palette before sending the final prompt to the Image API. This PNG is the initial text-to-image result, with no reference image or mask.

## Files

| File | Contents |
| --- | --- |
| [input.txt](retrieval/input.txt) | Complete source document |
| [request.json](retrieval/request.json) | Figure request and style choices |
| [prompt.txt](retrieval/prompt.txt) | English drawing prompt returned by the text model |
| [image-prompt.txt](retrieval/image-prompt.txt) | Complete prompt sent to the Image API, including rendering direction |
| [figure-spec.json](retrieval/figure-spec.json) | Semantic diagram and original source quotes |
| [manifest.json](retrieval/manifest.json) | Model names, quality, dimensions, elapsed time, and token usage |
| [figure.png](retrieval/figure.png) | Original 3840 × 2160 PNG |

The semantic FigureSpec and raster image are separate outputs. Inspect the rendered arrows before publication: in this example, a corpus connector and a short stray blue line still need attention. The original file is kept here so the demonstration matches the recorded output.

Animation source and build instructions: [docs/demo](../../docs/demo/README.md).
