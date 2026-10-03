"""Deterministic, font-measured compound graph layout shared by vector exporters."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from functools import lru_cache

import networkx as nx
import pymupdf

from app.schemas.figure_spec import FigureSpec, StylePreset, validate_export_options

MAX_EXPORT_HEIGHT = 16_384
Point = tuple[float, float]


class FigureLayoutError(ValueError):
    """The requested diagram cannot be laid out within the export constraints."""


@dataclass(frozen=True)
class Bounds:
    x: float
    y: float
    width: float
    height: float

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def center(self) -> Point:
        return self.x + self.width / 2, self.y + self.height / 2

    def transform(self, scale: float = 1, dx: float = 0, dy: float = 0) -> Bounds:
        return Bounds(
            self.x * scale + dx, self.y * scale + dy, self.width * scale, self.height * scale
        )

    def padded(self, padding: float) -> Bounds:
        return Bounds(
            self.x - padding, self.y - padding, self.width + 2 * padding, self.height + 2 * padding
        )

    def overlaps(self, other: Bounds) -> bool:
        return (
            self.x < other.right
            and self.right > other.x
            and self.y < other.bottom
            and self.bottom > other.y
        )


@dataclass(frozen=True)
class TextBlock:
    text: str
    lines: tuple[str, ...]
    bounds: Bounds
    font_name: str
    font_size: float
    line_height: float
    align: str = "center"

    def transform(self, scale: float = 1, dx: float = 0, dy: float = 0) -> TextBlock:
        return replace(
            self,
            bounds=self.bounds.transform(scale, dx, dy),
            font_size=self.font_size * scale,
            line_height=self.line_height * scale,
        )


@dataclass(frozen=True)
class NodeLayout:
    id: str
    bounds: Bounds
    label: TextBlock
    role: str
    group_id: str | None


@dataclass(frozen=True)
class GroupLayout:
    id: str
    bounds: Bounds
    label: TextBlock


@dataclass(frozen=True)
class EdgeLayout:
    id: str
    source: str
    target: str
    kind: str
    points: tuple[Point, ...]
    label: TextBlock | None


@dataclass(frozen=True)
class FigureLayout:
    spec: FigureSpec
    width_px: int
    height_px: int
    style_preset: StylePreset
    scale: float
    nodes: tuple[NodeLayout, ...]
    edges: tuple[EdgeLayout, ...]
    groups: tuple[GroupLayout, ...]
    title: TextBlock | None
    caption: TextBlock | None


@lru_cache(maxsize=4)
def get_font(name: str) -> pymupdf.Font:
    # MuPDF 1.28 can dereference a null language under Python tracing.
    return pymupdf.Font(name, language="")


def _font_for(text: str) -> str:
    for name in ("helv", "cjk"):
        font = get_font(name)
        if all(char.isspace() or font.has_glyph(ord(char), language="") for char in text):
            return name
    raise FigureLayoutError("label contains glyphs unsupported by the bundled vector fonts")


def measure_text(text: str, font_name: str, font_size: float) -> float:
    return get_font(font_name).text_length(text, fontsize=font_size, language="")


def _text_block(
    text: str, max_width: float, font_size: float = 14, align: str = "center"
) -> TextBlock:
    font_name = _font_for(text)
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        current = ""
        for word in paragraph.split():
            candidate = f"{current} {word}" if current else word
            if measure_text(candidate, font_name, font_size) <= max_width:
                current = candidate
                continue
            if current:
                lines.append(current)
                current = ""
            # Break unspaced tokens (including CJK) using actual font advances.
            for char in word:
                if measure_text(current + char, font_name, font_size) > max_width:
                    if not current:
                        raise FigureLayoutError("a label glyph exceeds the available width")
                    lines.append(current)
                    current = ""
                current += char
        lines.append(current)
    font = get_font(font_name)
    line_height = font_size * (font.ascender - font.descender) * 1.08
    width = max(measure_text(line, font_name, font_size) for line in lines)
    return TextBlock(
        text,
        tuple(lines),
        Bounds(0, 0, width, len(lines) * line_height),
        font_name,
        font_size,
        line_height,
        align,
    )


def text_positions(block: TextBlock) -> tuple[tuple[str, float, float], ...]:
    """Return measured left origins and font baselines, identical across formats."""
    font = get_font(block.font_name)
    leading = (block.line_height - block.font_size * (font.ascender - font.descender)) / 2
    baseline = block.bounds.y + leading + font.ascender * block.font_size
    return tuple(
        (
            line,
            block.bounds.x
            + (
                0
                if block.align == "left"
                else (block.bounds.width - measure_text(line, block.font_name, block.font_size)) / 2
            ),
            baseline + index * block.line_height,
        )
        for index, line in enumerate(block.lines)
    )


def _arrange(
    sizes: dict[str, tuple[float, float]],
    connections: list[tuple[str, str]],
    direction: str,
    gap: float,
) -> tuple[dict[str, Bounds], float, float]:
    if not sizes:
        return {}, 0, 0
    graph = nx.DiGraph()
    graph.add_nodes_from(sorted(sizes))
    graph.add_edges_from(sorted((a, b) for a, b in connections if a != b))
    components = sorted(sorted(c) for c in nx.strongly_connected_components(graph))
    dag = nx.condensation(graph, components)
    layers = [
        sorted(node for component in generation for node in components[component])
        for generation in nx.topological_generations(dag)
    ]
    horizontal = direction == "LR"
    primary = 0 if horizontal else 1
    cross = 1 - primary
    cross_sizes = [
        sum(sizes[node][cross] for node in layer) + 56 * (len(layer) - 1) for layer in layers
    ]
    total_cross = max(cross_sizes)
    positions: dict[str, Bounds] = {}
    offset = 0.0
    for layer, cross_size in zip(layers, cross_sizes, strict=True):
        thickness = max(sizes[node][primary] for node in layer)
        cross_offset = (total_cross - cross_size) / 2
        for node in layer:
            p = offset + (thickness - sizes[node][primary]) / 2
            x, y = (p, cross_offset) if horizontal else (cross_offset, p)
            positions[node] = Bounds(x, y, *sizes[node])
            cross_offset += sizes[node][cross] + 56
        offset += thickness + gap
    return (
        (positions, offset - gap, total_cross)
        if horizontal
        else (positions, total_cross, offset - gap)
    )


def _clear(a: Point, b: Point, obstacles: list[Bounds]) -> bool:
    if a[0] == b[0]:
        return not any(
            r.x < a[0] < r.right and max(a[1], b[1]) > r.y and min(a[1], b[1]) < r.bottom
            for r in obstacles
        )
    if a[1] == b[1]:
        return not any(
            r.y < a[1] < r.bottom and max(a[0], b[0]) > r.x and min(a[0], b[0]) < r.right
            for r in obstacles
        )
    return False


def _simplify(points: list[Point]) -> tuple[Point, ...]:
    result: list[Point] = []
    for point in points:
        if result and point == result[-1]:
            continue
        if len(result) >= 2 and (
            (
                result[-2][0] == result[-1][0] == point[0]
                and min(result[-2][1], point[1]) <= result[-1][1] <= max(result[-2][1], point[1])
            )
            or (
                result[-2][1] == result[-1][1] == point[1]
                and min(result[-2][0], point[0]) <= result[-1][0] <= max(result[-2][0], point[0])
            )
        ):
            result.pop()
        result.append(point)
    return tuple(result)


def _route(start: Point, end: Point, obstacles: list[Bounds]) -> list[Point]:
    xs = sorted(
        {
            start[0],
            end[0],
            (start[0] + end[0]) / 2,
            *(r.x - 4 for r in obstacles),
            *(r.right + 4 for r in obstacles),
        }
    )
    ys = sorted(
        {
            start[1],
            end[1],
            (start[1] + end[1]) / 2,
            *(r.y - 4 for r in obstacles),
            *(r.bottom + 4 for r in obstacles),
        }
    )
    candidates = [[start, (x, start[1]), (x, end[1]), end] for x in xs]
    candidates += [[start, (start[0], y), (end[0], y), end] for y in ys]
    candidates.sort(key=lambda path: sum(math.dist(a, b) for a, b in zip(path, path[1:])))
    for path in candidates:
        if all(_clear(a, b, obstacles) for a, b in zip(path, path[1:])):
            return path
    # NetworkX A* handles compound/feedback routes when a two-bend route is obstructed.
    if len(xs) * len(ys) > 120_000:
        raise FigureLayoutError("diagram is too crowded to route; split it into smaller figures")
    graph = nx.Graph()
    for x in xs:
        for y in ys:
            if not any(r.x < x < r.right and r.y < y < r.bottom for r in obstacles):
                graph.add_node((x, y))
    for x_index, x in enumerate(xs):
        for y_index, y in enumerate(ys):
            point = (x, y)
            if point not in graph:
                continue
            neighbors = []
            if x_index:
                neighbors.append((xs[x_index - 1], y))
            if y_index:
                neighbors.append((x, ys[y_index - 1]))
            for neighbor in neighbors:
                if neighbor in graph and _clear(point, neighbor, obstacles):
                    graph.add_edge(point, neighbor, weight=math.dist(point, neighbor))
    try:
        return nx.astar_path(graph, start, end, heuristic=lambda a, b: math.dist(a, b))
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise FigureLayoutError("no unobstructed connector route exists") from exc


def _port(bounds: Bounds, side: str, fraction: float) -> tuple[Point, Point]:
    if side == "right":
        point, normal = (bounds.right, bounds.y + bounds.height * fraction), (1, 0)
    elif side == "left":
        point, normal = (bounds.x, bounds.y + bounds.height * fraction), (-1, 0)
    elif side == "bottom":
        point, normal = (bounds.x + bounds.width * fraction, bounds.bottom), (0, 1)
    else:
        point, normal = (bounds.x + bounds.width * fraction, bounds.y), (0, -1)
    return point, (point[0] + normal[0] * 18, point[1] + normal[1] * 18)


def _ports(
    source: Bounds,
    target: Bounds,
    direction: str,
    same: bool,
    source_fraction: float,
    target_fraction: float,
) -> tuple[Point, Point, Point, Point]:
    if same:
        sides = "right", "bottom"
    elif direction == "LR" and target.x >= source.right:
        sides = "right", "left"
    elif direction == "TB" and target.y >= source.bottom:
        sides = "bottom", "top"
    elif direction == "LR" and source.x >= target.right:
        sides = "top", "top"
    elif direction == "TB" and source.y >= target.bottom:
        sides = "right", "right"
    elif target.y >= source.bottom:
        sides = "bottom", "top"
    else:
        sides = "top", "bottom"
    start, escape = _port(source, sides[0], source_fraction)
    finish, approach = _port(target, sides[1], target_fraction)
    return start, escape, approach, finish


def _edge_label(
    block: TextBlock, points: tuple[Point, ...], obstacles: list[Bounds]
) -> TextBlock | None:
    segments = sorted(zip(points, points[1:]), key=lambda pair: -math.dist(*pair))
    for a, b in segments:
        required = block.bounds.width + 20 if a[1] == b[1] else block.bounds.height + 20
        if math.dist(a, b) < required:
            continue
        for fraction in (0.5, 0.25, 0.75):
            x = a[0] + (b[0] - a[0]) * fraction - block.bounds.width / 2
            y = a[1] + (b[1] - a[1]) * fraction - block.bounds.height / 2
            positioned = block.transform(dx=x, dy=y)
            if not any(positioned.bounds.padded(8).overlaps(r) for r in obstacles):
                return positioned
    return None


def layout_figure(
    spec: FigureSpec | dict, *, width: int = 1600, style_preset: StylePreset = "classic"
) -> FigureLayout:
    """Lay out a validated v1 graph. No file, database, network, or paid-service I/O."""
    validate_export_options(width, style_preset)
    spec = FigureSpec.model_validate(spec)
    labels = {node.id: _text_block(node.label, 208) for node in spec.nodes}
    edge_labels = {
        edge.id: _text_block(edge.label, 160, 12) for edge in spec.edges if edge.label.strip()
    }
    gap = max(
        [
            96.0,
            *(
                block.bounds.width + 80 if spec.direction == "LR" else block.bounds.height + 80
                for block in edge_labels.values()
            ),
        ]
    )
    sizes = {
        node.id: (
            max(168, labels[node.id].bounds.width + 32),
            max(64, labels[node.id].bounds.height + 28),
        )
        for node in spec.nodes
    }
    owners = {node.id: node.group_id or node.id for node in spec.nodes}
    placements: dict[str, Bounds] = {}
    group_labels: dict[str, TextBlock] = {}
    group_sizes: dict[str, tuple[float, float]] = {}
    for group in sorted(spec.groups, key=lambda item: item.id):
        members = {node.id: sizes[node.id] for node in spec.nodes if node.group_id == group.id}
        connections = [
            (e.source, e.target)
            for e in spec.edges
            if e.kind != "skip" and e.source in members and e.target in members
        ]
        local, local_width, local_height = _arrange(members, connections, spec.direction, gap)
        group_width = max(224, local_width + 48)
        label = _text_block(group.label, group_width - 32, 14)
        group_labels[group.id] = label.transform(dx=(group_width - label.bounds.width) / 2, dy=16)
        header = label.bounds.height + 64
        group_sizes[group.id] = (group_width, max(92, header + local_height + 24))
        placements.update(
            {
                key: box.transform(dx=(group_width - local_width) / 2, dy=header)
                for key, box in local.items()
            }
        )
    root_sizes = {node.id: sizes[node.id] for node in spec.nodes if node.group_id is None}
    root_sizes.update(group_sizes)
    connections = [(owners[e.source], owners[e.target]) for e in spec.edges if e.kind != "skip"]
    root, _, _ = _arrange(root_sizes, connections, spec.direction, gap + 32)
    groups = tuple(
        GroupLayout(
            group.id,
            root[group.id],
            group_labels[group.id].transform(dx=root[group.id].x, dy=root[group.id].y),
        )
        for group in sorted(spec.groups, key=lambda item: item.id)
    )
    nodes = []
    for node in sorted(spec.nodes, key=lambda item: item.id):
        box = (
            placements[node.id].transform(dx=root[node.group_id].x, dy=root[node.group_id].y)
            if node.group_id
            else root[node.id]
        )
        label = labels[node.id]
        label = label.transform(
            dx=box.x + (box.width - label.bounds.width) / 2,
            dy=box.y + (box.height - label.bounds.height) / 2,
        )
        nodes.append(NodeLayout(node.id, box, label, node.role, node.group_id))
    node_map = {node.id: node for node in nodes}
    obstacles = [node.bounds.padded(10) for node in nodes]
    obstacles += [group.label.bounds.padded(8) for group in groups]
    label_obstacles = [node.bounds.padded(26) for node in nodes]
    label_obstacles += [group.label.bounds.padded(8) for group in groups]
    edges = []
    ordered_edges = sorted(spec.edges, key=lambda item: item.id)
    outgoing = {node.id: [e.id for e in ordered_edges if e.source == node.id] for node in nodes}
    incoming = {node.id: [e.id for e in ordered_edges if e.target == node.id] for node in nodes}
    for edge in ordered_edges:
        source_fraction = 0.25 + 0.5 * (outgoing[edge.source].index(edge.id) + 1) / (
            len(outgoing[edge.source]) + 1
        )
        target_fraction = 0.25 + 0.5 * (incoming[edge.target].index(edge.id) + 1) / (
            len(incoming[edge.target]) + 1
        )
        start, escape, approach, finish = _ports(
            node_map[edge.source].bounds,
            node_map[edge.target].bounds,
            spec.direction,
            edge.source == edge.target,
            source_fraction,
            target_fraction,
        )
        points = _simplify([start, *_route(escape, approach, obstacles), finish])
        label = None
        if edge.id in edge_labels:
            block = edge_labels[edge.id]
            label = _edge_label(block, points, label_obstacles)
            if label is None:
                # Reserve an exterior channel for labels that cannot fit between nodes.
                left = min(r.x for r in obstacles)
                right = max(r.right for r in obstacles)
                y = min(r.y for r in obstacles) - block.bounds.height / 2 - 32
                x = (left + right - block.bounds.width) / 2
                label = block.transform(dx=x, dy=y - block.bounds.height / 2)
                a, b = (x - 12, y), (x + block.bounds.width + 12, y)
                points = _simplify(
                    [
                        start,
                        *_route(escape, a, obstacles),
                        b,
                        *_route(b, approach, obstacles),
                        finish,
                    ]
                )
            obstacles.append(label.bounds.padded(8))
            label_obstacles.append(label.bounds.padded(8))
        edges.append(EdgeLayout(edge.id, edge.source, edge.target, edge.kind, points, label))

    boxes = [node.bounds for node in nodes] + [group.bounds for group in groups]
    boxes += [edge.label.bounds.padded(6) for edge in edges if edge.label]
    coordinates = [(box.x, box.y) for box in boxes] + [(box.right, box.bottom) for box in boxes]
    coordinates += [point for edge in edges for point in edge.points]
    min_x, min_y = (min(point[axis] for point in coordinates) - 10 for axis in (0, 1))
    max_x, max_y = (max(point[axis] for point in coordinates) + 10 for axis in (0, 1))
    scale = min(1.8, (width - 48) / (max_x - min_x))
    title = _text_block(spec.title, width - 48, 20, "left") if spec.title.strip() else None
    caption = _text_block(spec.caption, width - 48, 12, "left") if spec.caption.strip() else None
    top = 24 + (title.bounds.height + 24 if title else 0)
    dx = (width - (max_x - min_x) * scale) / 2 - min_x * scale
    dy = top - min_y * scale
    content_bottom = top + (max_y - min_y) * scale
    height = math.ceil(content_bottom + 24 + (caption.bounds.height + 20 if caption else 0))
    if height > MAX_EXPORT_HEIGHT:
        raise FigureLayoutError(f"layout exceeds {MAX_EXPORT_HEIGHT}px height; split the figure")
    return FigureLayout(
        spec,
        width,
        height,
        style_preset,
        scale,
        tuple(
            replace(
                node,
                bounds=node.bounds.transform(scale, dx, dy),
                label=node.label.transform(scale, dx, dy),
            )
            for node in nodes
        ),
        tuple(
            replace(
                edge,
                points=tuple((x * scale + dx, y * scale + dy) for x, y in edge.points),
                label=edge.label.transform(scale, dx, dy) if edge.label else None,
            )
            for edge in edges
        ),
        tuple(
            replace(
                group,
                bounds=group.bounds.transform(scale, dx, dy),
                label=group.label.transform(scale, dx, dy),
            )
            for group in groups
        ),
        title.transform(dx=24, dy=24) if title else None,
        caption.transform(dx=24, dy=content_bottom + 20) if caption else None,
    )
