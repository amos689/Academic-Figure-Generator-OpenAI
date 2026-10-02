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

See the [project README](../README.md) for installation, upgrade instructions, supported
settings, and links to the official model documentation.

After pulling an upgrade, reinstall with `pip install -e .` from this directory in
your virtual environment. This version requires `openai>=3.23.0` for the current
model and quality parameter definitions.
