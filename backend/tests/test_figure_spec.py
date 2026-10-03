from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.schemas.figure_spec import (
    MAX_EDGES,
    MAX_GROUPS,
    MAX_NODES,
    MAX_SOURCES,
    FigureSpec,
    validate_export_options,
)


@pytest.fixture
def spec_dict():
    return {
        "version": 1,
        "title": "Encoder & decoder",
        "caption": "A comparison with n < 4 and accuracy > 90%.",
        "direction": "LR",
        "nodes": [
            {
                "id": "input",
                "label": "Input",
                "role": "input",
                "sources": [{"section_index": 0, "quote": "input tokens"}],
            },
            {"id": "encoder", "label": "Encoder", "group_id": "model"},
        ],
        "edges": [{"id": "tokens", "source": "input", "target": "encoder"}],
        "groups": [{"id": "model", "label": "Model"}],
    }


def test_v1_round_trip_preserves_sources_and_defaults(spec_dict):
    spec = FigureSpec.model_validate(spec_dict)
    assert spec.nodes[0].sources[0].quote == "input tokens"
    assert spec.nodes[1].role == "process"
    assert spec.edges[0].kind == "data"
    assert spec.edges[0].label == ""
    assert FigureSpec.model_validate_json(spec.model_dump_json()) == spec


@pytest.mark.parametrize(
    "path,value",
    [
        (("version",), True),
        (("version",), 1.0),
        (("version",), "1"),
        (("version",), 2),
        (("direction",), "RL"),
        (("nodes", 0, "role"), "image"),
        (("edges", 0, "kind"), "html"),
        (("nodes", 0, "id"), "bad id"),
        (("nodes", 0, "id"), "../../file"),
        (("nodes", 0, "id"), "1"),
        (("nodes", 0, "id"), "a" * 65),
        (("nodes", 0, "label"), " \t\n"),
        (("nodes", 0, "label"), 15),
        (("nodes", 0, "label"), "a" * 241),
        (("title",), "a" * 241),
        (("caption",), "a" * 4001),
        (("edges", 0, "source"), "missing"),
        (("edges", 0, "target"), "model"),
        (("nodes", 0, "group_id"), "missing"),
        (("nodes", 1, "id"), "input"),
        (("edges", 0, "id"), "input"),
        (("groups", 0, "id"), "input"),
        (("nodes", 0, "sources", 0, "section_index"), -1),
        (("nodes", 0, "sources", 0, "section_index"), True),
        (("nodes", 0, "sources", 0, "section_index"), "0"),
        (("nodes", 0, "sources", 0, "section_index"), 100_001),
        (("nodes", 0, "sources", 0, "quote"), ""),
        (("nodes", 0, "sources", 0, "quote"), "a" * 2001),
    ],
)
def test_malformed_fields_are_rejected(spec_dict, path, value):
    target = spec_dict
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValidationError):
        FigureSpec.model_validate(spec_dict)


@pytest.mark.parametrize(
    "payload",
    [
        "<script>alert(1)</script>",
        "<svg/onload=alert(1)>",
        "<img src=x onerror=alert(1)>",
        "<b>bold</b>",
        "<script",
        "<?xml version='1.0'?>",
        "<!DOCTYPE svg>",
        "&lt;script&gt;alert(1)&lt;/script&gt;",
        "javascript:alert(1)",
        "DATA:image/svg+xml;base64,abc",
        "null\x00byte",
        "bell\x07",
        "\ud800",
        "\uffff",
    ],
)
@pytest.mark.parametrize("field", ["title", "caption", "node", "edge", "group", "quote"])
def test_markup_and_xml_controls_are_forbidden_everywhere(spec_dict, payload, field):
    target, key = {
        "title": (spec_dict, "title"),
        "caption": (spec_dict, "caption"),
        "node": (spec_dict["nodes"][0], "label"),
        "edge": (spec_dict["edges"][0], "label"),
        "group": (spec_dict["groups"][0], "label"),
        "quote": (spec_dict["nodes"][0]["sources"][0], "quote"),
    }[field]
    target[key] = payload
    with pytest.raises(ValidationError):
        FigureSpec.model_validate(spec_dict)


@pytest.mark.parametrize(
    "target,field",
    [
        ("root", "svg"),
        ("node", "html"),
        ("node", "x"),
        ("node", "bounds"),
        ("edge", "path"),
        ("group", "style"),
        ("source", "url"),
    ],
)
def test_extra_geometry_or_markup_fields_are_forbidden(spec_dict, target, field):
    targets = {
        "root": spec_dict,
        "node": spec_dict["nodes"][0],
        "edge": spec_dict["edges"][0],
        "group": spec_dict["groups"][0],
        "source": spec_dict["nodes"][0]["sources"][0],
    }
    targets[target][field] = "unexpected"
    with pytest.raises(ValidationError, match="Extra inputs"):
        FigureSpec.model_validate(spec_dict)


def test_collection_and_aggregate_text_limits(spec_dict):
    variants = [
        {**spec_dict, "nodes": []},
        {**spec_dict, "nodes": [{"id": f"n{i}", "label": "N"} for i in range(MAX_NODES + 1)]},
        {**spec_dict, "edges": [spec_dict["edges"][0]] * (MAX_EDGES + 1)},
        {**spec_dict, "groups": [spec_dict["groups"][0]] * (MAX_GROUPS + 1)},
    ]
    too_many_sources = deepcopy(spec_dict)
    too_many_sources["nodes"][0]["sources"] *= MAX_SOURCES + 1
    variants.append(too_many_sources)
    for variant in variants:
        with pytest.raises(ValidationError):
            FigureSpec.model_validate(variant)
    with pytest.raises(ValidationError, match="total figure text"):
        FigureSpec.model_validate(
            {
                "nodes": [
                    {
                        "id": f"n{i}",
                        "label": "Node",
                        "sources": [
                            {"section_index": 0, "quote": "x" * 2000} for _ in range(MAX_SOURCES)
                        ],
                    }
                    for i in range(4)
                ]
            }
        )


def test_document_aware_source_validation(spec_dict):
    spec = FigureSpec.model_validate(spec_dict, context={"section_texts": ["Our input\ntokens."]})
    spec.validate_source_references(["Our input tokens."])
    with pytest.raises(ValueError, match="does not exist"):
        spec.validate_source_references([])
    with pytest.raises(ValueError, match="absent"):
        spec.validate_source_references(["Different evidence."])
    with pytest.raises(ValueError, match="sequence"):
        spec.validate_source_references("input tokens")
    with pytest.raises(ValidationError, match="absent"):
        FigureSpec.model_validate(spec_dict, context={"section_texts": ["Different evidence."]})


@pytest.mark.parametrize("width", [639, 4097, 0, True, "640", 640.0, float("nan")])
def test_width_bounds_and_type(width):
    with pytest.raises(ValueError, match="width"):
        validate_export_options(width, "classic")


def test_valid_export_options_and_unknown_style():
    validate_export_options(640, "classic")
    validate_export_options(4096, "pastel")
    with pytest.raises(ValueError, match="style_preset"):
        validate_export_options(1600, "custom")


def test_revalidate_mutated_models(spec_dict):
    spec = FigureSpec.model_validate(spec_dict)
    spec.nodes[0].label = "<script>bad</script>"
    with pytest.raises(ValidationError):
        FigureSpec.model_validate(spec)


def test_schema_supports_installed_openai_strict_json_helper():
    from openai.lib._pydantic import to_strict_json_schema

    schema = to_strict_json_schema(FigureSpec)
    for model in [schema, *schema["$defs"].values()]:
        assert model["additionalProperties"] is False
        assert set(model["required"]) == set(model["properties"])
