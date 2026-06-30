from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.core.exceptions import ExternalAPIException
from app.services.openai_prompt_service import OpenAIPromptService


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _figure(prompt: str | None = None) -> dict:
    return {
        "figure_number": 1,
        "title": "Overall Framework",
        "suggested_figure_type": "overall_framework",
        "suggested_aspect_ratio": "16:9",
        "prompt": prompt or ("A detailed academic figure prompt. " * 30),
        "source_section_titles": ["Method"],
        "rationale": "Best summarizes the proposed method.",
    }


@pytest.mark.asyncio
async def test_generate_figure_prompts_uses_responses_structured_outputs(monkeypatch):
    calls: list[dict] = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(output_text=json.dumps({"figures": [_figure()]}))

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    service = OpenAIPromptService()
    result = await service.generate_figure_prompts(
        sections=[{"title": "Method", "content": "We propose a model."}],
        color_scheme={"primary": "#0072B2"},
        paper_field="machine learning",
        max_figures=1,
    )

    assert result["figures"][0]["title"] == "Overall Framework"
    assert result["model"] == "gpt-5.5"
    call = calls[0]
    assert call["model"] == "gpt-5.5"
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True


def test_invalid_json_response_fails():
    service = OpenAIPromptService()

    with pytest.raises(ExternalAPIException) as exc_info:
        service._parse_figures_response("not json")

    assert "Invalid JSON" in exc_info.value.detail


def test_empty_figures_response_fails():
    service = OpenAIPromptService()

    with pytest.raises(ExternalAPIException) as exc_info:
        service._parse_figures_response(json.dumps({"figures": []}))

    assert "No valid figure prompts" in exc_info.value.detail
