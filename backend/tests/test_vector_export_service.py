from __future__ import annotations

import json
import math
from copy import deepcopy
from itertools import combinations
from xml.etree import ElementTree as ET

import pymupdf
import pytest
from pydantic import ValidationError

from app.services.figure_layout_service import (
    Bounds,
    FigureLayoutError,
    _clear,
    _route,
    layout_figure,
    measure_text,
    text_positions,
)
from app.services.vector_export_service import SVG_NS, VectorExportService, export_figure

NS = {"svg": SVG_NS}


@pytest.fixture
def graph():
    return {
        "version": 1,
        "title": "Editable pipeline",
        "caption": "A & B; n < 4; a > 0.",
        "direction": "LR",
        "nodes": [
            {
                "id": "input",
                "label": "Input tokens",
                "role": "input",
                "sources": [{"section_index": 0, "quote": "token sequence"}],
            },
            {"id": "encoder", "label": "Feature encoder", "group_id": "model"},
            {"id": "head", "label": "Prediction head", "group_id": "model"},
            {"id": "output", "label": "Output scores", "role": "output"},
            {"id": "note", "label": "Frozen weights", "role": "note"},
        ],
        "groups": [{"id": "model", "label": "Trainable model"}],
        "edges": [
            {"id": "e1", "source": "input", "target": "encoder", "label": "tokens"},
            {"id": "e2", "source": "encoder", "target": "head", "label": "features"},
            {"id": "e3", "source": "head", "target": "output", "label": "scores"},
            {"id": "e4", "source": "note", "target": "encoder", "kind": "control"},
            {"id": "e5", "source": "input", "target": "output", "kind": "skip"},
        ],
    }


def assert_contains(outer: Bounds, inner: Bounds):
    assert outer.x - 0.001 <= inner.x <= inner.right <= outer.right + 0.001
    assert outer.y - 0.001 <= inner.y <= inner.bottom <= outer.bottom + 0.001


@pytest.mark.parametrize("direction", ["LR", "TB"])
@pytest.mark.parametrize("style", ["classic", "pastel"])
@pytest.mark.parametrize("width", [640, 1600, 4096])
def test_layout_bounds_groups_labels_and_determinism(graph, direction, style, width):
    graph["direction"] = direction
    layout = layout_figure(graph, width=width, style_preset=style)
    assert layout == layout_figure(deepcopy(graph), width=width, style_preset=style)
    assert layout.width_px == width
    canvas = Bounds(0, 0, width, layout.height_px)
    groups = {group.id: group for group in layout.groups}
    for node in layout.nodes:
        assert_contains(canvas, node.bounds)
        assert_contains(node.bounds, node.label.bounds)
        if node.group_id:
            assert_contains(groups[node.group_id].bounds, node.bounds)
            assert not node.bounds.overlaps(groups[node.group_id].label.bounds)
    for a, b in combinations(layout.nodes, 2):
        assert not a.bounds.overlaps(b.bounds)
    blocks = [node.label for node in layout.nodes] + [group.label for group in layout.groups]
    blocks += [edge.label for edge in layout.edges if edge.label]
    blocks += [block for block in (layout.title, layout.caption) if block]
    for block in blocks:
        assert_contains(canvas, block.bounds)
        for line, x, baseline in text_positions(block):
            assert x >= block.bounds.x - 0.001
            assert x + measure_text(line, block.font_name, block.font_size) <= (
                block.bounds.right + 0.001
            )
            assert block.bounds.y <= baseline <= block.bounds.bottom
    for edge in layout.edges:
        assert len(edge.points) >= 2
        for x, y in edge.points:
            assert math.isfinite(x) and math.isfinite(y)
            assert 0 <= x <= width and 0 <= y <= layout.height_px
        for a, b in zip(edge.points, edge.points[1:]):
            assert a[0] == b[0] or a[1] == b[1]
        if edge.label:
            assert all(not node.bounds.overlaps(edge.label.bounds) for node in layout.nodes)


@pytest.mark.parametrize("direction", ["LR", "TB"])
def test_primary_flow_and_group_containment(graph, direction):
    graph["direction"] = direction
    layout = layout_figure(graph)
    nodes = {node.id: node for node in layout.nodes}
    axis = 0 if direction == "LR" else 1
    centers = [nodes[key].bounds.center[axis] for key in ("input", "encoder", "head", "output")]
    assert centers == sorted(centers)


@pytest.mark.parametrize("format", ["svg", "pdf", "drawio"])
def test_real_editable_export_has_text_and_geometry(graph, format):
    result = VectorExportService().export(graph, format=format, width=1200)
    assert result.width_px == 1200 and result.height_px > 0
    assert result.extension == format
    if format == "svg":
        root = ET.fromstring(result.data)
        assert root.tag == f"{{{SVG_NS}}}svg"
        assert root.attrib["viewBox"] == f"0 0 1200 {result.height_px}"
        assert not root.findall(".//svg:image", NS)
        assert not root.findall(".//svg:foreignObject", NS)
        assert len(root.findall(".//svg:g[@data-kind='node']", NS)) == len(graph["nodes"])
        assert len(root.findall(".//svg:g[@data-kind='edge']/svg:path", NS)) == len(graph["edges"])
        assert root.find(".//svg:g[@id='group-model']/svg:g[@id='node-head']", NS) is not None
        labels = [text.attrib["aria-label"] for text in root.findall(".//svg:text", NS)]
        assert set(node["label"] for node in graph["nodes"]) <= set(labels)
        assert all(
            float(span.attrib["textLength"]) > 0
            for span in root.findall(".//svg:tspan[@textLength]", NS)
        )
        stored = json.loads(root.find("svg:metadata", NS).text)
    elif format == "pdf":
        with pymupdf.open(stream=result.data, filetype="pdf") as pdf:
            assert len(pdf) == 1
            assert pdf[0].rect.width == 1200
            assert not pdf[0].get_images(full=True)
            assert len(pdf[0].get_drawings()) >= len(graph["nodes"]) + len(graph["edges"])
            text = pdf[0].get_text()
            assert all(node["label"] in text for node in graph["nodes"])
            assert "Trainable model" in text and "Editable pipeline" in text
            stored = json.loads(pdf.embfile_get("figure-spec.json"))
    else:
        root = ET.fromstring(result.data)
        assert root.tag == "mxfile"
        model = root.find("diagram/mxGraphModel")
        assert model is not None
        stored = json.loads(model.attrib["figureSpec"])
        cells = {cell.attrib["id"]: cell for cell in model.findall("root/mxCell")}
        assert len(cells) == len(model.findall("root/mxCell"))
        assert cells["node-head"].attrib["parent"] == "group-model"
        for node in graph["nodes"]:
            cell = cells[f"node-{node['id']}"]
            assert cell.attrib["vertex"] == "1"
            assert cell.attrib["value"] == node["label"]
            assert "html=0;" in cell.attrib["style"]
            geometry = cell.find("mxGeometry")
            assert float(geometry.attrib["width"]) > 0
            assert float(geometry.attrib["height"]) > 0
        for edge in graph["edges"]:
            cell = cells[f"edge-{edge['id']}"]
            assert cell.attrib["source"] == f"node-{edge['source']}"
            assert cell.attrib["target"] == f"node-{edge['target']}"
            assert cell.attrib["source"] in cells and cell.attrib["target"] in cells
            assert cell.find("mxGeometry").attrib["relative"] == "1"
        assert all(cell.attrib.get("parent", "0") in cells for cell in cells.values())
    assert stored["nodes"][0]["sources"] == graph["nodes"][0]["sources"]


@pytest.mark.parametrize("format", ["svg", "pdf", "drawio"])
def test_escaping_quotes_and_special_characters(graph, format):
    value = "R&D \"quoted\" 'literal' n < 3 > 1 & entity;"
    graph["nodes"][0]["label"] = value
    graph["nodes"][0]["sources"][0]["quote"] = value
    result = export_figure(graph, format=format)
    if format == "svg":
        root = ET.fromstring(result.data)
        node = root.find(".//svg:g[@id='node-input']/svg:text", NS)
        assert node.attrib["aria-label"] == value
        assert b"&amp;" in result.data and b"&lt;" in result.data
    elif format == "drawio":
        root = ET.fromstring(result.data)
        node = root.find(".//mxCell[@id='node-input']")
        assert node.attrib["originalLabel"] == value
        assert " ".join(node.attrib["value"].split()) == value
    else:
        with pymupdf.open(stream=result.data, filetype="pdf") as pdf:
            assert value in " ".join(pdf[0].get_text().split())


@pytest.mark.parametrize("format", ["svg", "pdf", "drawio"])
def test_unicode_live_text_and_long_unspaced_labels(format):
    graph = {
        "nodes": [
            {"id": "unicode", "label": "\u6a21\u5757 \u03b1 \u2192 \u03b2"},
            {"id": "long", "label": "W" * 240},
        ],
        "edges": [{"id": "connection", "source": "unicode", "target": "long"}],
    }
    layout = layout_figure(graph, width=640)
    assert len(next(node for node in layout.nodes if node.id == "long").label.lines) > 1
    result = export_figure(graph, format=format, width=640)
    if format == "pdf":
        with pymupdf.open(stream=result.data, filetype="pdf") as pdf:
            text = pdf[0].get_text()
            assert "\u6a21\u5757" in text and "\u03b1" in text and "\u03b2" in text
            assert text.count("W") == 240


@pytest.mark.parametrize("direction", ["LR", "TB"])
def test_cycles_self_loops_parallel_edges_disconnected_and_empty_groups(direction):
    graph = {
        "direction": direction,
        "nodes": [
            {"id": "a", "label": "A", "group_id": "group"},
            {"id": "b", "label": "B", "group_id": "group"},
            {"id": "c", "label": "Disconnected"},
        ],
        "groups": [{"id": "group", "label": "Cycle"}, {"id": "empty", "label": "Empty"}],
        "edges": [
            {"id": "ab", "source": "a", "target": "b", "label": "first"},
            {"id": "ab2", "source": "a", "target": "b", "label": "second"},
            {"id": "ba", "source": "b", "target": "a", "label": "feedback"},
            {"id": "aa", "source": "a", "target": "a", "label": "loop"},
        ],
    }
    layout = layout_figure(graph)
    assert len(layout.edges) == 4 and len(layout.groups) == 2
    assert all(edge.label for edge in layout.edges)
    for format in ("svg", "pdf", "drawio"):
        assert export_figure(graph, format=format).data


def test_order_independent_geometry_and_distinct_styles(graph):
    original = layout_figure(graph)
    reordered = deepcopy(graph)
    for key in ("nodes", "edges", "groups"):
        reordered[key].reverse()
    other = layout_figure(reordered)
    assert original.nodes == other.nodes and original.edges == other.edges
    assert original.groups == other.groups
    assert export_figure(graph, format="svg", style_preset="classic").data != (
        export_figure(graph, format="svg", style_preset="pastel").data
    )
    for format in ("svg", "drawio", "pdf"):
        assert export_figure(graph, format=format).data == export_figure(graph, format=format).data


@pytest.mark.parametrize("format", ["svg", "pdf", "drawio"])
def test_invalid_inputs_fail_without_raster_fallback(graph, format):
    with pytest.raises(ValidationError):
        export_figure({"image": "data:image/png;base64,AA"}, format=format)
    with pytest.raises(ValueError):
        export_figure(graph, format=format, width=500)
    with pytest.raises(ValueError):
        export_figure(graph, format=format, style_preset="unknown")
    with pytest.raises(ValidationError):
        export_figure({"nodes": [{"id": "n", "label": "<svg/>"}]}, format=format)
    with pytest.raises(FigureLayoutError, match="glyphs"):
        export_figure({"nodes": [{"id": "n", "label": "unsupported \U0010fffd"}]}, format=format)
    with pytest.raises(ValueError, match="format"):
        export_figure(graph, format="png")


@pytest.mark.parametrize("format", ["svg", "pdf", "drawio"])
def test_render_adapter_with_application_palette(graph, format):
    palette = {
        "primary": "#def",
        "secondary": "#dcefed",
        "tertiary": "#fbdfe9",
        "text": "#222",
        "fill": "#fff",
        "section_bg": "#fafafa",
        "border": "#444",
        "arrow": "#123456",
    }
    result = VectorExportService().render(graph, format, 640, "pastel", palette)
    assert set(result) == {"data", "width", "height", "media_type", "extension"}
    assert result["width"] == 640 and result["height"] > 0
    assert isinstance(result["data"], bytes)
    if format == "svg":
        root = ET.fromstring(result["data"])
        assert root.find(".//svg:g[@id='node-input']/svg:rect", NS).attrib["fill"] == "#ddeeff"
        assert root.find(".//svg:g[@id='edge-e1']/svg:path", NS).attrib["stroke"] == "#123456"


@pytest.mark.parametrize(
    "palette",
    [
        {"primary": "red;stroke:url(https://evil.example)"},
        {"primary": "#fff\n"},
        {"primary": 123},
        {"unknown": "#fff"},
        ["#fff"],
        {"primary": "<svg/>"},
    ],
)
def test_palette_cannot_inject_markup_or_css(graph, palette):
    with pytest.raises(ValueError, match="palette"):
        VectorExportService().render(graph, palette=palette)


def test_internal_label_stays_in_group_on_direct_connector(graph):
    layout = layout_figure(graph)
    group = layout.groups[0]
    edge = next(edge for edge in layout.edges if edge.id == "e2")
    assert len(edge.points) == 2
    assert_contains(group.bounds, edge.label.bounds)


def test_networkx_route_finds_path_through_opposing_u_shaped_obstacles():
    obstacles = [
        Bounds(-25, -25, 50, 5),
        Bounds(-25, -20, 5, 45),
        Bounds(20, -20, 5, 45),
        Bounds(75, 20, 50, 5),
        Bounds(75, -25, 5, 45),
        Bounds(120, -25, 5, 45),
    ]
    path = _route((0, 0), (100, 0), obstacles)
    assert path[0] == (0, 0) and path[-1] == (100, 0)
    assert len(path) > 4
    assert all(_clear(a, b, obstacles) for a, b in zip(path, path[1:]))


def test_routes_do_not_cross_node_interiors_and_labels_do_not_overlap(graph):
    for direction in ("LR", "TB"):
        graph["direction"] = direction
        layout = layout_figure(graph)
        node_interiors = [node.bounds.padded(-0.01) for node in layout.nodes]
        for edge in layout.edges:
            assert all(_clear(a, b, node_interiors) for a, b in zip(edge.points, edge.points[1:]))
        labels = [edge.label for edge in layout.edges if edge.label]
        assert all(not a.bounds.overlaps(b.bounds) for a, b in combinations(labels, 2))


def test_pdf_extracted_text_bounding_boxes_fit_canvas_and_nodes(graph):
    layout = layout_figure(graph, width=640)
    result = export_figure(graph, format="pdf", width=640)
    with pymupdf.open(stream=result.data, filetype="pdf") as pdf:
        for block in pdf[0].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    x0, y0, x1, y1 = span["bbox"]
                    bounds = Bounds(x0, y0, x1 - x0, y1 - y0)
                    assert_contains(Bounds(0, 0, result.width_px, result.height_px), bounds)
                    node = next((n for n in layout.nodes if span["text"] == n.label.text), None)
                    if node:
                        assert_contains(node.bounds, bounds)


def test_excessive_output_height_fails_clearly():
    graph = {"nodes": [{"id": f"n{i}", "label": "W" * 240} for i in range(100)]}
    with pytest.raises(FigureLayoutError, match="height"):
        layout_figure(graph, width=4096)


def test_native_text_apis_do_not_receive_null_language(graph, monkeypatch):
    original = pymupdf.mupdf.fz_text_language_from_string

    def checked_language(value):
        assert isinstance(value, str)
        return original(value)

    monkeypatch.setattr(pymupdf.mupdf, "fz_text_language_from_string", checked_language)
    assert export_figure(graph, format="pdf").data
