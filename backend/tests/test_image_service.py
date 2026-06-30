from __future__ import annotations

import base64
import sys
from types import SimpleNamespace

import pytest

from app.config import get_settings
from app.core.exceptions import ExternalAPIException
from app.services.image_service import ImageService


@pytest.fixture(autouse=True)
def clear_settings_cache(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _install_fake_openai(monkeypatch, calls: list[tuple[str, dict]]):
    encoded = base64.b64encode(b"fake-image").decode("ascii")

    class FakeImages:
        def generate(self, **kwargs):
            calls.append(("generate", kwargs))
            return {"data": [{"b64_json": encoded}]}

        def edit(self, **kwargs):
            calls.append(("edit", kwargs))
            return {"data": [{"b64_json": encoded}]}

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls.append(("client", kwargs))
            self.images = FakeImages()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))


def test_generate_image_uses_openai_generation(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _install_fake_openai(monkeypatch, calls)

    service = ImageService(api_key="test-key")
    result = service.generate_image(
        "draw an academic diagram",
        resolution="1K",
        aspect_ratio="16:9",
    )

    assert result["image_base64"]
    assert result["width"] % 16 == 0
    assert result["height"] % 16 == 0
    generate_call = [kwargs for name, kwargs in calls if name == "generate"][0]
    assert generate_call["model"] == "gpt-image-2"
    assert generate_call["prompt"] == "draw an academic diagram"
    assert "x" in generate_call["size"]


def test_edit_image_uses_openai_edit(monkeypatch):
    calls: list[tuple[str, dict]] = []
    _install_fake_openai(monkeypatch, calls)

    service = ImageService(api_key="test-key")
    service.generate_image(
        "original prompt",
        reference_image_bytes=b"reference",
        edit_instruction="make labels larger",
    )

    edit_call = [kwargs for name, kwargs in calls if name == "edit"][0]
    assert edit_call["model"] == "gpt-image-2"
    assert edit_call["image"] == ("reference.png", b"reference", "image/png")
    assert "make labels larger" in edit_call["prompt"]
    assert "original prompt" in edit_call["prompt"]


def test_missing_openai_key_fails(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    with pytest.raises(ExternalAPIException) as exc_info:
        ImageService()

    assert "OPENAI_API_KEY" in exc_info.value.detail


@pytest.mark.parametrize("resolution", ["1K", "2K", "4K"])
@pytest.mark.parametrize("aspect_ratio", ["1:1", "16:9", "9:16", "21:9"])
def test_openai_dimensions_respect_constraints(resolution: str, aspect_ratio: str):
    width, height = ImageService._calculate_dimensions(resolution, aspect_ratio)

    assert width % 16 == 0
    assert height % 16 == 0
    assert max(width, height) <= 3840
    assert width * height <= 8_294_400
    assert max(width / height, height / width) <= 3.0
