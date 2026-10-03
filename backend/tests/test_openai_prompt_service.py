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
        "figure_spec": None,
    }


@pytest.mark.asyncio
async def test_generate_figure_prompts_uses_responses_structured_outputs(monkeypatch):
    calls: list[dict] = []

    class FakeResponses:
        def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(
                status="completed", output_text=json.dumps({"figures": [_figure()]})
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

        def close(self):
            calls.append({"closed": True})

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    service = OpenAIPromptService()
    result = await service.generate_figure_prompts(
        sections=[{"title": "Method", "content": "We propose a model."}],
        color_scheme={"primary": "#0072B2"},
        paper_field="machine learning",
        max_figures=1,
    )

    assert result["figures"][0]["title"] == "Overall Framework"
    assert result["model"] == "gpt-6-astra"
    call = calls[0]
    assert call["model"] == "gpt-6-astra"
    assert call["reasoning"] == {"effort": "max"}
    assert call["max_output_tokens"] == 32768
    assert call["service_tier"] == "default"
    assert calls[-1] == {"closed": True}
    assert call["text"]["format"]["type"] == "json_schema"
    assert call["text"]["format"]["strict"] is True
    assert not {"temperature", "top_p", "top_logprobs"}.intersection(call)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("reason", "expected_error"),
    [
        ("max_output_tokens", "OPENAI_TEXT_MAX_OUTPUT_TOKENS"),
        ("content_filter", "Incomplete prompt generation: content_filter"),
    ],
)
async def test_incomplete_response_is_not_accepted(monkeypatch, reason, expected_error):
    class FakeResponses:
        def create(self, **kwargs):
            return SimpleNamespace(
                status="incomplete",
                incomplete_details=SimpleNamespace(reason=reason),
                output_text=json.dumps({"figures": [_figure()]}),
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

        def close(self):
            pass

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    with pytest.raises(ExternalAPIException) as exc_info:
        await OpenAIPromptService().generate_figure_prompts(
            sections=[{"title": "Method", "content": "We propose a model."}],
            color_scheme={"primary": "#0072B2"},
        )

    assert expected_error in exc_info.value.detail


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


def test_schema_checks_all_fields_and_pastel_skill():
    service = OpenAIPromptService(style_preset="pastel")
    assert "pastel" in service.skill_content.lower()
    assert "untrusted source data" in service._build_instructions()
    invalid = _figure()
    invalid["suggested_aspect_ratio"] = "500:1"
    with pytest.raises(ExternalAPIException):
        service._parse_figures_response(json.dumps({"figures": [invalid]}))


async def test_generated_spec_evidence_must_exist(monkeypatch):
    figure = _figure()
    figure["figure_spec"] = {
        "version": 1,
        "title": "Framework",
        "nodes": [
            {
                "id": "input",
                "label": "Input",
                "sources": [{"section_index": 0, "quote": "Invented evidence"}],
            }
        ],
        "edges": [],
        "groups": [],
    }
    service = OpenAIPromptService()
    monkeypatch.setattr(service, "_create_response", lambda _: json.dumps({"figures": [figure]}))
    with pytest.raises(ExternalAPIException, match="absent from supplied context"):
        await service.generate_figure_prompts(
            [{"title": "Methods", "content": "Real evidence only."}], {}
        )
    figure["figure_spec"]["nodes"][0]["sources"][0]["quote"] = "Real evidence only."
    result = await service.generate_figure_prompts(
        [{"title": "Methods", "content": "Real evidence only."}], {}
    )
    assert result["generation_metadata"]["context_coverage"]["coverage_ratio"] == 1
