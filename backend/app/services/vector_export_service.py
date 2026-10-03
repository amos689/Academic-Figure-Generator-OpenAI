"""Offline editable SVG, native draw.io, and live-text vector PDF exports."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, replace
from typing import TypedDict
from xml.etree import ElementTree as ET

import pymupdf

from app.schemas.figure_spec import ExportFormat, FigureSpec, StylePreset
from app.services.figure_layout_service import (
    Bounds,
    EdgeLayout,
    FigureLayout,
    TextBlock,
    get_font,
    layout_figure,
    measure_text,
    text_positions,
)

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


@dataclass(frozen=True)
class VectorExportResult:
    data: bytes
    media_type: str
    extension: str
    width_px: int
    height_px: int


class VectorRenderResult(TypedDict):
    data: bytes
    width: int
    height: int
    media_type: str
    extension: str


@dataclass(frozen=True)
class _Palette:
    text: str
    stroke: str
    group_fill: str
    group_stroke: str
    input_fill: str
    process_fill: str
    output_fill: str
    note_fill: str
    radius: float
    background: str = "#ffffff"
    arrow: str | None = None

    def node_fill(self, role: str) -> str:
        return getattr(self, f"{role}_fill")


_PALETTES = {
    "classic": _Palette(
        "#222222", "#46515a", "#fafafa", "#7b858e", "#e1f1fa", "#edf5ed", "#f8e6ed", "#fff4d6", 3
    ),
    "pastel": _Palette(
        "#29333b", "#68747c", "#fcfcfd", "#b0b7c0", "#dcecfb", "#dcf2e8", "#f5dfea", "#fff1ce", 8
    ),
}


def _resolve_palette(style_preset: StylePreset, colors: dict[str, str] | None) -> _Palette:
    palette = _PALETTES[style_preset]
    if colors is None:
        return palette
    roles = {
        "primary": "input_fill",
        "secondary": "process_fill",
        "tertiary": "output_fill",
        "text": "text",
        "fill": "background",
        "section_bg": "group_fill",
        "border": "stroke",
        "arrow": "arrow",
    }
    if not isinstance(colors, dict) or colors.keys() - roles.keys():
        raise ValueError("palette must contain only the application's eight color roles")
    overrides = {}
    for role, color in colors.items():
        if not isinstance(color, str) or not re.fullmatch(
            r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", color
        ):
            raise ValueError("palette colors must be #RGB or #RRGGBB hex values")
        normalized = "#" + "".join(char * 2 for char in color[1:]) if len(color) == 4 else color
        overrides[roles[role]] = normalized.lower()
    if "border" in colors:
        overrides["group_stroke"] = overrides["stroke"]
    if "fill" in colors:
        overrides["note_fill"] = overrides["background"]
    background = overrides.get("background", palette.background)
    strength = 0.14 if style_preset == "pastel" else 0.22
    # Accent colors describe semantic roles, not opaque backgrounds behind dark labels.
    for role in ("input_fill", "process_fill", "output_fill"):
        if role in overrides:
            accent = overrides[role]
            components = [
                round(
                    int(accent[i : i + 2], 16) * strength
                    + int(background[i : i + 2], 16) * (1 - strength)
                )
                for i in (1, 3, 5)
            ]
            overrides[role] = "#" + "".join(f"{value:02x}" for value in components)
    return replace(palette, **overrides)


def _number(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".") if value else "0"


def _font_family(block: TextBlock) -> str:
    return "Helvetica" if block.font_name == "helv" else "Droid Sans Fallback"


def _spec_json(layout: FigureLayout) -> str:
    return json.dumps(
        layout.spec.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _svg_element(parent: ET.Element, tag: str, **attributes: str) -> ET.Element:
    return ET.SubElement(parent, f"{{{SVG_NS}}}{tag}", attributes)


def _svg_rect(parent: ET.Element, bounds: Bounds, **attributes: str) -> ET.Element:
    return _svg_element(
        parent,
        "rect",
        x=_number(bounds.x),
        y=_number(bounds.y),
        width=_number(bounds.width),
        height=_number(bounds.height),
        **attributes,
    )


def _svg_text(parent: ET.Element, block: TextBlock, color: str) -> None:
    family = (
        "Helvetica, Arial, sans-serif"
        if block.font_name == "helv"
        else "Droid Sans Fallback, Noto Sans CJK SC, sans-serif"
    )
    text = _svg_element(
        parent,
        "text",
        **{
            "font-family": family,
            "font-size": _number(block.font_size),
            "fill": color,
            "aria-label": block.text,
            "data-font": block.font_name,
            "xml:space": "preserve",
        },
    )
    for line, x, y in text_positions(block):
        span = _svg_element(text, "tspan", x=_number(x), y=_number(y))
        if line:
            # Preserve measured width even when an SVG editor substitutes a local font.
            span.set("textLength", _number(measure_text(line, block.font_name, block.font_size)))
            span.set("lengthAdjust", "spacingAndGlyphs")
        span.text = line


def _arrow(edge: EdgeLayout, scale: float) -> tuple[tuple[float, float], ...]:
    end, previous = edge.points[-1], edge.points[-2]
    length = math.dist(end, previous)
    ux, uy = (end[0] - previous[0]) / length, (end[1] - previous[1]) / length
    size = min(9 * scale, length * 0.8)
    return (
        end,
        (end[0] - ux * size - uy * size / 2, end[1] - uy * size + ux * size / 2),
        (end[0] - ux * size + uy * size / 2, end[1] - uy * size - ux * size / 2),
    )


def _svg(layout: FigureLayout, palette: _Palette) -> bytes:
    root = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "version": "1.1",
            "width": str(layout.width_px),
            "height": str(layout.height_px),
            "viewBox": f"0 0 {layout.width_px} {layout.height_px}",
            "role": "img",
            "aria-labelledby": "figure-title figure-description",
            "data-style": layout.style_preset,
        },
    )
    _svg_element(root, "title", id="figure-title").text = layout.spec.title or "Figure"
    _svg_element(root, "desc", id="figure-description").text = layout.spec.caption
    _svg_element(root, "metadata", id="figure-spec").text = _spec_json(layout)
    _svg_rect(root, Bounds(0, 0, layout.width_px, layout.height_px), fill=palette.background)
    group_elements = {}
    for group in layout.groups:
        element = _svg_element(root, "g", id=f"group-{group.id}", **{"data-kind": "group"})
        group_elements[group.id] = element
        _svg_rect(
            element,
            group.bounds,
            fill=palette.group_fill,
            stroke=palette.group_stroke,
            rx=_number(palette.radius * layout.scale),
            **{
                "stroke-width": _number(layout.scale),
                "stroke-dasharray": f"{_number(5 * layout.scale)} {_number(4 * layout.scale)}",
            },
        )
        _svg_text(element, group.label, palette.text)
    for node in layout.nodes:
        parent = group_elements[node.group_id] if node.group_id else root
        element = _svg_element(
            parent,
            "g",
            id=f"node-{node.id}",
            **{
                "data-kind": "node",
                "data-role": node.role,
            },
        )
        _svg_rect(
            element,
            node.bounds,
            fill=palette.node_fill(node.role),
            stroke=palette.stroke,
            rx=_number(palette.radius * layout.scale),
            **{"stroke-width": _number(1.4 * layout.scale)},
        )
        _svg_text(element, node.label, palette.text)
    for edge in layout.edges:
        element = _svg_element(
            root,
            "g",
            id=f"edge-{edge.id}",
            **{
                "data-kind": "edge",
                "data-source": edge.source,
                "data-target": edge.target,
                "data-edge-kind": edge.kind,
            },
        )
        path = "M " + " L ".join(f"{_number(x)} {_number(y)}" for x, y in edge.points)
        attributes = {"stroke-width": _number(1.5 * layout.scale), "stroke-linejoin": "round"}
        if edge.kind != "data":
            dash = 6 if edge.kind == "control" else 2
            attributes["stroke-dasharray"] = (
                f"{_number(dash * layout.scale)} {_number(4 * layout.scale)}"
            )
        _svg_element(
            element,
            "path",
            d=path,
            fill="none",
            stroke=palette.arrow or palette.stroke,
            **attributes,
        )
        _svg_element(
            element,
            "polygon",
            points=" ".join(f"{_number(x)},{_number(y)}" for x, y in _arrow(edge, layout.scale)),
            fill=palette.arrow or palette.stroke,
        )
        if edge.label:
            _svg_rect(
                element,
                edge.label.bounds.padded(4 * layout.scale),
                fill=palette.background,
                rx=_number(2 * layout.scale),
            )
            _svg_text(element, edge.label, palette.text)
    for block in (layout.title, layout.caption):
        if block:
            _svg_text(root, block, palette.text)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _rgb(hex_color: str) -> tuple[float, float, float]:
    return tuple(int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5))


def _pdf_rect(
    page: pymupdf.Page,
    bounds: Bounds,
    fill: str,
    stroke: str | None = None,
    width: float = 1,
    dashes: str | None = None,
    radius: float = 0,
) -> None:
    page.draw_rect(
        pymupdf.Rect(bounds.x, bounds.y, bounds.right, bounds.bottom),
        fill=_rgb(fill),
        color=_rgb(stroke) if stroke else None,
        width=width,
        dashes=dashes,
        radius=min(0.5, radius / min(bounds.width, bounds.height)) if radius else None,
    )


def _pdf(layout: FigureLayout, palette: _Palette) -> bytes:
    with pymupdf.open() as document:
        page = document.new_page(width=layout.width_px, height=layout.height_px)
        _pdf_rect(page, Bounds(0, 0, layout.width_px, layout.height_px), palette.background)
        blocks = []
        for group in layout.groups:
            _pdf_rect(
                page,
                group.bounds,
                palette.group_fill,
                palette.group_stroke,
                layout.scale,
                f"[{5 * layout.scale} {4 * layout.scale}] 0",
                radius=palette.radius * layout.scale,
            )
            blocks.append(group.label)
        for edge in layout.edges:
            dash = 6 if edge.kind == "control" else 2
            page.draw_polyline(
                list(edge.points),
                color=_rgb(palette.arrow or palette.stroke),
                width=1.5 * layout.scale,
                dashes=None
                if edge.kind == "data"
                else f"[{dash * layout.scale} {4 * layout.scale}] 0",
            )
            page.draw_polyline(
                list(_arrow(edge, layout.scale)),
                color=None,
                fill=_rgb(palette.arrow or palette.stroke),
                closePath=True,
            )
            if edge.label:
                _pdf_rect(
                    page,
                    edge.label.bounds.padded(4 * layout.scale),
                    palette.background,
                    radius=2 * layout.scale,
                )
                blocks.append(edge.label)
        for node in layout.nodes:
            _pdf_rect(
                page,
                node.bounds,
                palette.node_fill(node.role),
                palette.stroke,
                1.4 * layout.scale,
                radius=palette.radius * layout.scale,
            )
            blocks.append(node.label)
        blocks.extend(block for block in (layout.title, layout.caption) if block)
        writer = pymupdf.TextWriter(page.rect)
        for block in blocks:
            for line, x, y in text_positions(block):
                if line:
                    writer.append(
                        (x, y),
                        line,
                        font=get_font(block.font_name),
                        fontsize=block.font_size,
                        language="",
                    )
        writer.write_text(page, color=_rgb(palette.text))
        document.set_metadata(
            {
                "title": layout.spec.title,
                "subject": layout.spec.caption,
                "creator": "Academic Figure Generator",
            }
        )
        attachment = document.embfile_add("figure-spec.json", _spec_json(layout).encode("utf-8"))
        # Remove automatic wall-clock metadata so repeated exports are reproducible.
        document.xref_set_key(attachment, "Params/CreationDate", "null")
        document.xref_set_key(attachment, "Params/ModDate", "null")
        document.subset_fonts()
        return document.tobytes(garbage=4, deflate=True, no_new_id=True)


def _geometry(cell: ET.Element, bounds: Bounds) -> ET.Element:
    return ET.SubElement(
        cell,
        "mxGeometry",
        {
            "x": _number(bounds.x),
            "y": _number(bounds.y),
            "width": _number(bounds.width),
            "height": _number(bounds.height),
            "as": "geometry",
        },
    )


def _midpoint(edge: EdgeLayout) -> tuple[float, float]:
    distances = [math.dist(a, b) for a, b in zip(edge.points, edge.points[1:])]
    remaining = sum(distances) / 2
    for (a, b), distance in zip(zip(edge.points, edge.points[1:]), distances, strict=True):
        if remaining <= distance:
            fraction = remaining / distance
            return a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction
        remaining -= distance
    return edge.points[-1]


def _drawio(layout: FigureLayout, palette: _Palette) -> bytes:
    root = ET.Element("mxfile", {"host": "app.diagrams.net", "compressed": "false"})
    diagram = ET.SubElement(
        root, "diagram", {"id": "figure", "name": layout.spec.title or "Figure"}
    )
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "grid": "0",
            "page": "1",
            "pageScale": "1",
            "pageWidth": str(layout.width_px),
            "pageHeight": str(layout.height_px),
            "math": "0",
            "figureSpec": _spec_json(layout),
            "stylePreset": layout.style_preset,
            "background": palette.background,
        },
    )
    cells = ET.SubElement(model, "root")
    ET.SubElement(cells, "mxCell", {"id": "0"})
    ET.SubElement(cells, "mxCell", {"id": "1", "parent": "0"})
    base_style = (
        f"html=0;whiteSpace=wrap;overflow=fill;fontColor={palette.text};"
        f"strokeWidth={_number(1.4 * layout.scale)};shadow=0;"
    )
    groups = {group.id: group for group in layout.groups}
    nodes = {node.id: node for node in layout.nodes}
    for group in layout.groups:
        style = (
            "swimlane;" + base_style + f"fillColor={palette.group_fill};"
            f"swimlaneFillColor={palette.group_fill};strokeColor={palette.group_stroke};"
            f"startSize={_number(group.label.bounds.bottom - group.bounds.y + 16 * layout.scale)};"
            f"fontSize={_number(group.label.font_size)};fontFamily={_font_family(group.label)};"
            "horizontal=1;align=center;verticalAlign=middle;collapsible=0;container=1;"
        )
        cell = ET.SubElement(
            cells,
            "mxCell",
            {
                "id": f"group-{group.id}",
                "value": "\n".join(group.label.lines),
                "style": style,
                "vertex": "1",
                "connectable": "0",
                "parent": "1",
                "specId": group.id,
            },
        )
        _geometry(cell, group.bounds)
    source_items = {item.id: item for item in [*layout.spec.nodes, *layout.spec.edges]}
    for node in layout.nodes:
        style = (
            base_style + "shape=rectangle;rounded=1;absoluteArcSize=1;"
            f"arcSize={_number(2 * palette.radius * layout.scale)};"
            f"fillColor={palette.node_fill(node.role)};strokeColor={palette.stroke};"
            f"fontSize={_number(node.label.font_size)};fontFamily={_font_family(node.label)};"
            f"align=center;verticalAlign=middle;spacing={_number(12 * layout.scale)};"
        )
        cell = ET.SubElement(
            cells,
            "mxCell",
            {
                "id": f"node-{node.id}",
                "value": "\n".join(node.label.lines),
                "style": style,
                "vertex": "1",
                "parent": f"group-{node.group_id}" if node.group_id else "1",
                "specId": node.id,
                "role": node.role,
                "originalLabel": node.label.text,
                "sourceRefs": json.dumps(
                    [ref.model_dump() for ref in source_items[node.id].sources]
                ),
            },
        )
        parent = groups[node.group_id].bounds if node.group_id else Bounds(0, 0, 0, 0)
        _geometry(cell, node.bounds.transform(dx=-parent.x, dy=-parent.y))
    for edge in layout.edges:
        source, target = nodes[edge.source].bounds, nodes[edge.target].bounds
        style = (
            base_style + "edgeStyle=none;noEdgeStyle=1;rounded=0;endArrow=block;endFill=1;"
            f"strokeColor={palette.arrow or palette.stroke};"
            f"labelBackgroundColor={palette.background};"
            f"exitX={_number((edge.points[0][0] - source.x) / source.width)};"
            f"exitY={_number((edge.points[0][1] - source.y) / source.height)};"
            f"entryX={_number((edge.points[-1][0] - target.x) / target.width)};"
            f"entryY={_number((edge.points[-1][1] - target.y) / target.height)};"
            "exitPerimeter=0;entryPerimeter=0;"
        )
        if edge.kind != "data":
            style += "dashed=1;dashPattern=" + ("6 4;" if edge.kind == "control" else "2 4;")
        if edge.label:
            style += (
                f"fontSize={_number(edge.label.font_size)};fontFamily={_font_family(edge.label)};"
            )
        cell = ET.SubElement(
            cells,
            "mxCell",
            {
                "id": f"edge-{edge.id}",
                "value": "\n".join(edge.label.lines) if edge.label else "",
                "style": style,
                "edge": "1",
                "parent": "1",
                "source": f"node-{edge.source}",
                "target": f"node-{edge.target}",
                "specId": edge.id,
                "kind": edge.kind,
                "sourceRefs": json.dumps(
                    [ref.model_dump() for ref in source_items[edge.id].sources]
                ),
            },
        )
        geometry = ET.SubElement(
            cell, "mxGeometry", {"x": "0", "y": "0", "relative": "1", "as": "geometry"}
        )
        waypoints = ET.SubElement(geometry, "Array", {"as": "points"})
        for x, y in edge.points[1:-1]:
            ET.SubElement(waypoints, "mxPoint", {"x": _number(x), "y": _number(y)})
        if edge.label:
            midpoint = _midpoint(edge)
            center = edge.label.bounds.center
            ET.SubElement(
                geometry,
                "mxPoint",
                {
                    "x": _number(center[0] - midpoint[0]),
                    "y": _number(center[1] - midpoint[1]),
                    "as": "offset",
                },
            )
    for name, block in (("title", layout.title), ("caption", layout.caption)):
        if block:
            style = (
                base_style + "text;strokeColor=none;fillColor=none;align=left;"
                "verticalAlign=top;spacing=0;"
                f"fontSize={_number(block.font_size)};fontFamily={_font_family(block)};"
            )
            cell = ET.SubElement(
                cells,
                "mxCell",
                {
                    "id": f"figure-{name}",
                    "value": "\n".join(block.lines),
                    "vertex": "1",
                    "parent": "1",
                    "style": style,
                },
            )
            _geometry(cell, block.bounds)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


class VectorExportService:
    def export(
        self,
        spec: FigureSpec | dict,
        *,
        format: ExportFormat,
        width: int = 1600,
        style_preset: StylePreset = "classic",
        palette: dict[str, str] | None = None,
    ) -> VectorExportResult:
        """Return an artifact in memory; callers own persistence and job orchestration."""
        exporters = {
            "svg": (_svg, "image/svg+xml"),
            "pdf": (_pdf, "application/pdf"),
            "drawio": (_drawio, "application/vnd.jgraph.mxfile"),
        }
        if not isinstance(format, str) or format not in exporters:
            raise ValueError("format must be 'svg', 'pdf', or 'drawio'")
        layout = layout_figure(spec, width=width, style_preset=style_preset)
        resolved_palette = _resolve_palette(style_preset, palette)
        renderer, media_type = exporters[format]
        return VectorExportResult(
            renderer(layout, resolved_palette),
            media_type,
            format,
            layout.width_px,
            layout.height_px,
        )

    def render(
        self,
        spec: FigureSpec | dict,
        format: ExportFormat = "svg",
        width: int = 1600,
        style_preset: StylePreset = "classic",
        palette: dict[str, str] | None = None,
    ) -> VectorRenderResult:
        """Integration adapter with the job layer's data/width/height dictionary contract."""
        result = self.export(
            spec, format=format, width=width, style_preset=style_preset, palette=palette
        )
        return {
            "data": result.data,
            "width": result.width_px,
            "height": result.height_px,
            "media_type": result.media_type,
            "extension": result.extension,
        }


def export_figure(
    spec: FigureSpec | dict,
    *,
    format: ExportFormat,
    width: int = 1600,
    style_preset: StylePreset = "classic",
    palette: dict[str, str] | None = None,
) -> VectorExportResult:
    return VectorExportService().export(
        spec, format=format, width=width, style_preset=style_preset, palette=palette
    )
