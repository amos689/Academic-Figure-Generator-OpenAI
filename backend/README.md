# Academic Figure Generator (Backend)

FastAPI backend service for Academic Figure Generator.

Default AI configuration (verified against OpenAI documentation on 2026-10-02):

- Structured figure prompts: `gpt-6-astra` through the Responses API, with `reasoning.effort=max`.
- Image generation and editing: `gpt-image-2.5-sunburst` through the Images API, with `quality=max`.
- Prompt output budget: 32,768 tokens shared by reasoning and the final JSON response.

Configure `OPENAI_API_KEY` in your system environment. Settings resolve in this order:
system environment, local `.env` files, then defaults in `app/config.py`. Existing model
and quality overrides must be updated or removed to adopt the new defaults. Restart
the backend after changing settings.

See the project documentation in [English](../README.md) or [简体中文](../README.zh-CN.md)
for installation, upgrade instructions, supported settings, and data-privacy details.

After pulling an upgrade, reinstall with `pip install -e .` from this directory in
your virtual environment. This version requires `openai>=3.23.0` for the current
model and quality parameter definitions.

## Source Map

| Path | Responsibility |
| --- | --- |
| `app/config.py` | Environment and local-file configuration |
| `app/api/v1/` | Projects, documents, prompts, figures, and palettes |
| `app/services/openai_prompt_service.py` | Structured figure prompts using the Responses API |
| `app/services/image_service.py` | Image generation, editing, and size constraints |
| `app/services/document_service.py` | Document parsing and section extraction |
| `tests/` | Configuration, parsing, and mocked API checks |

## Development

From this directory with the virtual environment activated:

```bash
python -m pip install -e ".[dev]"
pytest -q
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open [the API reference](http://localhost:8000/docs) after starting the server.
The service stores data locally and has no user authentication. Keep it bound
to localhost unless you provide the required access controls separately.
