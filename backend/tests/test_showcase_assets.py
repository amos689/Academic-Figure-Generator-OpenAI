"""The README example stays connected to its published source and settings."""

import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image, ImageChops, ImageColor

from app.schemas.figure_spec import FigureSpec
from app.schemas.prompt import PromptGenerateRequest
from app.services.style_service import compose_image_prompt

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "examples/showcase/mae"


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
    assert record["source"]["venue"] == "CVPR 2022"
    assert record["source"]["url"].startswith("https://openaccess.thecvf.com/content/CVPR2022/")
    assert record["source"]["selected_section_titles"] == ["3. Approach"]
    assert record["source"]["coverage_ratio"] == 1.0
    request = PromptGenerateRequest.model_validate_json((CASE / "request.json").read_text())
    assert request.section_indices == record["source"]["selected_sections"]
    assert request.style_preset == image_info["style_preset"] == "pastel"
    elements = [*spec.nodes, *spec.edges]
    assert set(prompt_info["element_source_sections"]) == {item.id for item in elements}
    assert all(
        indices == request.section_indices
        for indices in prompt_info["element_source_sections"].values()
    )
    # The public graph keeps the topology; verbatim paper excerpts stay in the local project.
    assert prompt_info["source_quotes_included"] is False
    assert all(not item.sources for item in elements)
    assert (CASE / record["source"]["summary_file"]).is_file()
    with Image.open(CASE / image_info["file"]) as image:
        assert image.size == (image_info["width"], image_info["height"])
        assert image.format == "PNG"
    original_context = (CASE / image_info["prompt_file"]).read_text().strip()
    parent = image_info["file"]
    for key in ("image_refinement", "image_correction"):
        edit = record[key]
        assert edit["reference_file"] == parent
        assert edit["operation"] == "edit"
        instruction = (CASE / edit["instruction_file"]).read_text().strip()
        assert (CASE / edit["prompt_file"]).read_text().strip() == (
            f"{instruction}\n\nOriginal prompt context:\n{original_context}"
        )
        with Image.open(CASE / edit["file"]) as image:
            assert image.size == (edit["width"], edit["height"]) == (3840, 2160)
        parent = edit["file"]
    with Image.open(CASE / record["image_correction"]["mask_file"]) as mask:
        assert mask.size == (3840, 2160)
        assert mask.mode == "RGBA"
    layout = record["local_finishing"]
    assert layout["operation"] == "deterministic_layout"
    assert parent in layout["reference_files"]
    assert layout["file"] == record["selected_image"]
    assert (CASE / layout["script"]).is_file()
    assert layout["additional_api_calls"] == 0
    with Image.open(CASE / record["selected_image"]) as image:
        assert image.size == (layout["width"], layout["height"]) == (4800, 1920)


@pytest.fixture(scope="module")
def composition():
    spec = importlib.util.spec_from_file_location("layout_mae", ROOT / "docs/demo/layout_mae.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_showcase_layout_is_repeatable_and_connectors_reach_their_ports(composition):
    first = composition.render()
    second = composition.render()
    assert first.size == composition.SIZE == (4800, 1920)
    assert ImageChops.difference(first, second).getbbox() is None
    color = ImageColor.getrgb(composition.LINE)
    for source, target in composition.DIRECT_EDGES:
        start, end = composition.PORTS[source][2], composition.PORTS[target][0]
        assert end > start
        assert first.getpixel((start, composition.CY)) == color
        assert first.getpixel((end, composition.CY)) == color
    assert first.getpixel((2935, composition.PORTS["mask"][3])) == color
    assert first.getpixel((2935, composition.PORTS["merge"][1])) == color


def test_showcase_operator_text_keeps_explicit_padding(composition):
    layout = composition.Layout()
    with Image.open(CASE / "refined.png") as refined, Image.open(CASE / "repair-base.png") as base:
        layout.build(refined.convert("RGB"), base.convert("RGB"))
    for name in ("sampling", "projection"):
        x, y, right, bottom = composition.PORTS[name]
        lines = [
            b
            for b in layout.text_bounds
            if x <= (b[0] + b[2]) / 2 <= right and y <= (b[1] + b[3]) / 2 <= bottom
        ]
        assert len(lines) >= 3
        assert all(
            b[0] >= x + 24 and b[2] <= right - 24 and b[1] >= y + 24 and b[3] <= bottom - 24
            for b in lines
        )


def test_showcase_operator_adapts_to_font_metrics(composition):
    layout = composition.Layout()
    layout.box((0, 0, 310, 200), "Linear projection\n+ encoder\npositions", size=56, padding=24)
    assert len(layout.text_bounds) == 3
    assert all(
        b[0] >= 24 and b[2] <= 286 and b[1] >= 24 and b[3] <= 176 for b in layout.text_bounds
    )


def test_showcase_rejects_text_touching_a_connector(composition):
    layout = composition.Layout()
    layout.text((2965, 593), "Repeat x12", 27, anchor="lm")
    layout.line([(2935, 501), (2935, 725)])
    layout.validate_clearance()
    layout.text((2740, 615), "Repeat x12", 31, anchor="lm")
    layout.line([(2748, 548), (2748, 1052)])
    with pytest.raises(ValueError, match="too close to a connector"):
        layout.validate_clearance()


def test_showcase_subscripts_use_positioned_digits(composition, monkeypatch):
    layout = composition.Layout()
    runs = []
    monkeypatch.setattr(
        layout, "text", lambda xy, text, size, **kwargs: runs.append((xy, text, size))
    )
    layout.indexed_label((3070, 1510), "Prediction \u0177", "10")
    assert runs[0][1:] == ("Prediction \u0177", 34)
    assert runs[1][1:] == ("10", 23)
    assert runs[1][0][1] == runs[0][0][1] + 11


@pytest.mark.parametrize("filename", ["demo.gif", "demo.zh-CN.gif"])
def test_readme_animation_is_small_and_loops(filename):
    path = ROOT / "docs/demo" / filename
    assert path.stat().st_size < 2 * 1024 * 1024
    duration = 0
    result_frames = []
    with Image.open(path) as gif:
        assert gif.is_animated
        assert gif.info["loop"] == 0
        assert gif.size == (1280, 860)
        opening = gif.convert("RGB")
        for index in range(gif.n_frames):
            gif.seek(index)
            duration += gif.info["duration"]
            if min(gif.convert("RGB").getpixel((0, 100))) >= 240:
                result_frames.append(index)
        assert gif.info["duration"] >= 10000
        assert result_frames == [0, gif.n_frames - 1]
        assert ImageChops.difference(opening, gif.convert("RGB")).getbbox() is None
    assert 25000 <= duration <= 40000


@pytest.mark.parametrize("filename", ["README.md", "README.zh-CN.md"])
def test_readme_uses_the_published_paper_example(filename):
    readme = (ROOT / filename).read_text()
    assert "./examples/showcase/mae/figure.png" in readme
    assert "./examples/showcase/mae/prompt.txt" in readme
    assert "openaccess.thecvf.com/content/CVPR2022/" in readme
    assert "showcase/retrieval" not in readme
