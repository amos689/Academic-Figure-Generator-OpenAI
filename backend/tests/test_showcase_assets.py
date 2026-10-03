"""The README example stays connected to its published source and settings."""

import json
from pathlib import Path

import pytest
from PIL import Image

from app.schemas.figure_spec import FigureSpec
from app.services.document_service import DocumentService
from app.services.style_service import compose_image_prompt

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "examples/showcase/retrieval"


def test_showcase_record_matches_published_artifacts():
    record = json.loads((CASE / "manifest.json").read_text())
    prompt_info = record["prompt_generation"]
    image_info = record["image_generation"]
    prompt = (CASE / prompt_info["file"]).read_text().rstrip("\n")
    assert len(prompt) == prompt_info["characters"]
    assert (CASE / image_info["prompt_file"]).read_text().rstrip("\n") == compose_image_prompt(
        prompt, image_info["style_preset"], image_info["palette"]
    )
    spec = FigureSpec.model_validate_json((CASE / prompt_info["figure_spec"]).read_text())
    assert len(spec.nodes) == prompt_info["nodes"]
    assert len(spec.edges) == prompt_info["edges"]
    document = DocumentService().parse_txt((CASE / record["source"]["file"]).read_bytes())
    spec.validate_source_references([section["content"] for section in document["sections"]])
    assert record["source"]["selected_sections"] == list(range(len(document["sections"])))
    with Image.open(CASE / image_info["file"]) as image:
        assert image.size == (image_info["width"], image_info["height"])
        assert image.format == "PNG"


@pytest.mark.parametrize("filename", ["demo.gif", "demo.zh-CN.gif"])
def test_readme_animation_is_small_and_loops(filename):
    path = ROOT / "docs/demo" / filename
    assert path.stat().st_size < 2 * 1024 * 1024
    duration = 0
    with Image.open(path) as gif:
        assert gif.is_animated
        assert gif.info["loop"] == 0
        assert gif.size == (1280, 860)
        for index in range(gif.n_frames):
            gif.seek(index)
            duration += gif.info["duration"]
        assert gif.info["duration"] >= 10000
    assert 25000 <= duration <= 40000
