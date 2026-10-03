<p align="center">
  <img src="./logo.png" alt="Academic Figure Generator" width="144" height="144" />
</p>

<h1 align="center">Academic Figure Generator</h1>

<p align="center"><strong>OpenAI Edition</strong></p>
<p align="center">Turn research into figures, with an editable prompt at every step.</p>

<p align="center">
  <strong>English</strong> · <a href="./README.zh-CN.md">简体中文</a>
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> ·
  <a href="#workflow">Workflow</a> ·
  <a href="#configuration">Configuration</a> ·
  <a href="#codex-skills">Codex skills</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12%2B-3563E9?style=flat-square" alt="Python 3.12 or newer" />
  <img src="https://img.shields.io/badge/React-19-2D907D?style=flat-square" alt="React 19" />
  <img src="https://img.shields.io/badge/AI-OpenAI-252525?style=flat-square" alt="OpenAI APIs" />
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-E27057?style=flat-square" alt="MIT License" /></a>
</p>

A local research-figure workbench for turning papers and ideas into visual drafts. Bring a PDF, DOCX, or TXT document, generate structured figure prompts, refine the composition, and create or edit images through OpenAI.

The prompt is a first-class artifact: you can inspect and revise what the model is about to draw before committing to an image.

## Workflow

```mermaid
flowchart LR
    A["Paper or idea"] --> B["Structured prompt"]
    B --> C["Review and refine"]
    C --> D["Generate a figure"]
    D --> E["Edit or download"]
    E -. "Refine the prompt" .-> C
    classDef input fill:#EDF2FF,stroke:#3563E9,color:#243963;
    classDef review fill:#EEF7F3,stroke:#2D907D,color:#225544;
    class A,B,D,E input;
    class C review;
```

**Read the paper. Shape the prompt. Review the figure.** Each stage remains visible in the project workspace.

### Choose Your Entry Point

| Mode | Start with | Use it when |
| --- | --- | --- |
| **Paper workspace** | A PDF, DOCX, or TXT paper | You want prompts grounded in selected sections, with documents and figures kept together. |
| **Quick generation** | Your own image prompt | You already know the composition and want to generate a figure directly. |
| **Codex skills** | A paper or research description in your coding agent | You only need detailed figure prompts, without running the web application. |

### What You Can Do

| Capability | Current implementation |
| --- | --- |
| Paper-aware composition | Parse documents, select sections, request an overall framework or section-specific figures, and add your own instructions. |
| Editable prompts | Inspect the generated English prompt and save revisions before generating an image. |
| Visual direction | Nine bundled palette presets, a custom palette manager, aspect-ratio controls, and requests for styles such as pastel. |
| Figure generation | OpenAI image generation and editing; 1K, 2K, and 4K area-based size tiers in the project workspace. |
| Iterative editing | Submit an edit instruction against an existing image, then preview and download the result. |
| Structural drafts | Template mode requests an unlabeled base diagram for later annotation. |
| Local organization | SQLite project records, local uploads and image files, and generation-status updates in the interface. |

The web interface currently uses primarily Chinese labels. These documentation pages are available in both English and Chinese.

## Quick Start

### Requirements

- Python **3.12+**.
- Node.js **22.12+** and npm.
- An OpenAI API key with access to the configured text and image models.

The commands below target macOS and Linux. No external database, Redis, or worker service is required.

### 1. Get the Project

```bash
git clone https://github.com/amos689/Academic-Figure-Generator-OpenAI.git
cd Academic-Figure-Generator-OpenAI
```

### 2. Start the Backend

Set the key in the same terminal that starts the backend. The value below is a placeholder.

```bash
export OPENAI_API_KEY="your-openai-api-key"

cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

On first launch, the backend creates its local SQLite database and seeds the bundled palettes.

### 3. Start the Frontend

Open a second terminal at the repository root:

```bash
cd frontend
npm ci
npm run dev -- --host localhost --port 5173
```

Open **[localhost:5173](http://localhost:5173)**. Interactive API documentation is at **[localhost:8000/docs](http://localhost:8000/docs)**.

<details>
<summary>Windows / PowerShell</summary>

From the repository root, start the backend with:

```powershell
$env:OPENAI_API_KEY = "your-openai-api-key"
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Use the same frontend commands in a second terminal. If you use a newer Python installation, select that interpreter when creating the virtual environment.

</details>

### Make Your First Figure

1. Create a project and upload a paper.
2. Choose an overall framework or specific sections, then describe the figure you need.
3. Generate the prompts and review the scientific content, labels, layout, and palette.
4. Edit the prompt, choose an aspect ratio and size tier, then generate the image.
5. Inspect the result, submit any edit instructions, and download the PNG.

For a paper-independent starting point, open **Quick generation** (快捷生成). For a pastel layout, include a request such as:

> Create a modern ML framework figure on a white canvas, using muted pastel panels, clear arrows, and readable labels. Preserve the method's actual modules and relationships.

## Configuration

The default text and image calls both use OpenAI. There is no separate Anthropic or NanoBanana credential requirement.

| Setting | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | Empty | Required for backend prompt and image generation. |
| `OPENAI_API_BASE` | `https://api.openai.com/v1` | API endpoint. |
| `OPENAI_TEXT_MODEL` | `gpt-6-astra` | Structured figure-prompt generation through the Responses API. |
| `OPENAI_TEXT_REASONING_EFFORT` | `max` | Text reasoning effort. |
| `OPENAI_TEXT_MAX_OUTPUT_TOKENS` | `32768` | Shared budget for reasoning and final prompt output. |
| `OPENAI_IMAGE_MODEL` | `gpt-image-2.5-sunburst` | Image generation and editing through the Images API. |
| `OPENAI_IMAGE_QUALITY` | `max` | Image rendering quality. |

These are explicit project defaults, not aliases that automatically select future model releases. See the official [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) and [GPT Image 2.5 Sunburst](https://developers.openai.com/api/docs/models/gpt-image-2.5-sunburst) documentation for model capabilities.

**Configuration priority:** system environment → `backend/.env` → root `.env` → defaults in [config.py](./backend/app/config.py). If both local files exist, `backend/.env` wins.

For optional file-based configuration, use [.env.example](./.env.example) as a reference. Keep real credentials outside version control. Restart the backend after changing settings; the settings page displays configuration guidance and default values, not a live settings editor.

### Quality and Size

The defaults favor quality. Higher reasoning and image-quality settings can increase latency and usage; use `high` instead of `max` when a faster draft is sufficient.

The project workspace defaults to **2K**. Its 1K / 2K / 4K labels describe target pixel areas; the actual width and height depend on the selected aspect ratio. Dimensions are rounded to multiples of 16, with a maximum edge of 3840 pixels and a maximum area of 8,294,400 pixels. Larger sizes are subject to the image model's [documented limits](https://developers.openai.com/api/docs/guides/image-generation#size-and-quality-options).

### Upgrading an Existing Installation

Pull the updated code, reactivate the backend virtual environment, and run `python -m pip install -e .` again. Run `npm ci` from `frontend/` when its dependencies change.

Existing environment variables and `.env` values continue to override new defaults. Update or remove old model overrides, then restart the backend. When selecting a different model, choose reasoning and quality values supported by that model; for example, GPT Image 2 uses quality levels up to `high`.

## Data and Privacy

**Local storage does not mean offline generation.** Project records, uploaded documents, prompts, and generated images are stored on your machine. The backend sends selected extracted paper text and instructions to OpenAI for prompt generation, and sends prompts plus any reference image for image generation or editing.

| Data | Default location |
| --- | --- |
| Project and generation records | `backend/data/app.db` |
| Uploaded documents | `backend/data/uploads/` |
| Generated images | `backend/data/figures/` |

The repository ignores local `.env` files, `backend/data/`, virtual environments, and agent session records. You can override `DATA_DIR` and `DATABASE_PATH`; keep any alternative data locations outside version control as well.

This is a single-user local application without authentication. The quick-start commands bind the backend to the local machine.

## Codex Skills

Use the bundled skills when you want figure prompts without installing the web application.

| Skill | Focus |
| --- | --- |
| [Academic Figure Prompt](./academic-figure-prompt/SKILL.md) | Detailed English prompts for frameworks, architectures, modules, comparisons, and data-pattern figures. |
| [Modern ML / Pastel](./academic-figure-prompt-pastel/SKILL.md) | White canvases, soft pastel accents, compact panels, and modern ML-paper compositions. |

From the repository root:

```bash
mkdir -p ~/.codex/skills
cp -R academic-figure-prompt ~/.codex/skills/
cp -R academic-figure-prompt-pastel ~/.codex/skills/
```

If you have configured a custom `CODEX_HOME`, use its `skills/` directory instead. Ask Codex, for example:

```text
Read this paper and generate a detailed academic figure prompt.
modern ML figure prompt
pastel风格论文配图
```

Skill-only use generates prompt text in your coding agent. It does not start the backend or automatically call the project's image API.

## Under the Hood

| Layer | Technology |
| --- | --- |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS, Radix UI |
| Backend | FastAPI, Pydantic Settings, SQLAlchemy |
| Persistence | SQLite and local files |
| Paper parsing | PyMuPDF, python-docx, plain-text parsing |
| Prompt generation | OpenAI Responses API with a strict JSON schema |
| Image generation | OpenAI Images API, with background tasks and status endpoints |

Prompt generation is a synchronous HTTP operation; image generation runs in a backend background task. The web interface polls for status. An SSE endpoint is also available for API clients.

```text
Academic-Figure-Generator-OpenAI/
  backend/app/api/v1/           HTTP endpoints
  backend/app/services/        Document, prompt, and image services
  backend/app/config.py        Model and application defaults
  backend/tests/               Configuration and API-contract tests
  frontend/src/pages/          Project, generation, palette, and settings views
  academic-figure-prompt/      General figure-prompt skill
  academic-figure-prompt-pastel/  Modern ML / pastel skill
  README.md                    English documentation
  README.zh-CN.md               Chinese documentation
```

## Development

Backend checks, from `backend/` with its virtual environment activated:

```bash
python -m pip install -e ".[dev]"
pytest -q
```

Frontend build, from `frontend/`:

```bash
npm run build
```

See the [backend notes](./backend/README.md) and [frontend notes](./frontend/README.md) for implementation entry points. To propose a change, [open an issue](https://github.com/amos689/Academic-Figure-Generator-OpenAI/issues) with the intended workflow, or submit a focused pull request with the relevant checks.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| API key missing | Export the key in the backend's terminal, or configure a local `.env`, then restart. |
| Model unavailable | Check model access for the configured OpenAI account and endpoint. Explicit model overrides remain active after upgrades. |
| Prompt generation reaches its token budget | Increase `OPENAI_TEXT_MAX_OUTPUT_TOKENS`, request fewer figures, or lower the reasoning effort. |
| PDF produces little or no text | Use a text-based PDF, or extract OCR text externally and upload it as TXT. The default parser does not OCR scanned pages. |
| Frontend cannot reach the backend | Check port 8000. For another endpoint, set `VITE_API_BASE_URL` in `frontend/.env` and allow the frontend origin in `CORS_ORIGINS`. |
| A figure contains incorrect labels or relationships | Correct the prompt or submit an edit instruction, then inspect the new image. |

Generated figures are raster drafts. Review scientific relationships, notation, and any numeric content before using them in a publication; this project does not export editable vector diagrams.

## Acknowledgements

This project is developed from [LigphiDonk/academic-figure-generator](https://github.com/LigphiDonk/academic-figure-generator). We thank the original author for all contributions to the project's design, implementation, and open-source release.

## License

[MIT](./LICENSE).
