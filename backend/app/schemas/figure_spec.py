"""Validated semantic FigureSpec v1; geometry and markup are deliberately absent."""

from __future__ import annotations

import html
import re
from collections.abc import Sequence
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationInfo,
    model_validator,
)

MAX_NODES = 100
MAX_EDGES = 200
MAX_GROUPS = 32
MAX_SOURCES = 16
MAX_TEXT_LENGTH = 100_000
MIN_EXPORT_WIDTH = 640
MAX_EXPORT_WIDTH = 4096

StylePreset = Literal["classic", "pastel"]
ExportFormat = Literal["svg", "pdf", "drawio"]

_MARKUP = re.compile(
    r"<\s*(?:/?\s*[A-Za-z][^>]*>|!|\?|/?\s*(?:script|svg|html|iframe)\b)"
    r"|(?:javascript|vbscript)\s*:|data\s*:\s*(?:text/html|image/svg\+xml)",
    re.IGNORECASE,
)


def _plain_text(value: str) -> str:
    if any(
        (ord(char) < 32 and char not in "\n\r\t")
        or 0x7F <= ord(char) <= 0x9F
        or 0xD800 <= ord(char) <= 0xDFFF
        or ord(char) & 0xFFFF in (0xFFFE, 0xFFFF)
        for char in value
    ):
        raise ValueError("text contains unsupported control or XML characters")
    if _MARKUP.search(html.unescape(value)):
        raise ValueError("raw HTML, SVG, scripts, and executable URLs are not allowed")
    return value


def _nonblank(value: str) -> str:
    if not value.strip():
        raise ValueError("text must not be blank")
    return value


Identifier = Annotated[
    str, StringConstraints(strict=True, pattern=r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
]
Label = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=240),
    AfterValidator(_plain_text),
    AfterValidator(_nonblank),
]
OptionalLabel = Annotated[
    str, StringConstraints(strict=True, max_length=240), AfterValidator(_plain_text)
]
Caption = Annotated[
    str, StringConstraints(strict=True, max_length=4000), AfterValidator(_plain_text)
]
Quote = Annotated[
    str,
    StringConstraints(strict=True, min_length=1, max_length=2000),
    AfterValidator(_plain_text),
    AfterValidator(_nonblank),
]


class _SpecModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always")


class SourceReference(_SpecModel):
    section_index: int = Field(ge=0, le=100_000)
    quote: Quote


class FigureNode(_SpecModel):
    id: Identifier
    label: Label
    role: Literal["input", "process", "output", "note"] = "process"
    group_id: Identifier | None = None
    sources: list[SourceReference] = Field(default_factory=list, max_length=MAX_SOURCES)


class FigureEdge(_SpecModel):
    id: Identifier
    source: Identifier
    target: Identifier
    label: OptionalLabel = ""
    kind: Literal["data", "control", "skip"] = "data"
    sources: list[SourceReference] = Field(default_factory=list, max_length=MAX_SOURCES)


class FigureGroup(_SpecModel):
    id: Identifier
    label: Label


class FigureSpec(_SpecModel):
    version: Literal[1] = 1
    title: OptionalLabel = ""
    caption: Caption = ""
    direction: Literal["LR", "TB"] = "LR"
    nodes: list[FigureNode] = Field(min_length=1, max_length=MAX_NODES)
    edges: list[FigureEdge] = Field(default_factory=list, max_length=MAX_EDGES)
    groups: list[FigureGroup] = Field(default_factory=list, max_length=MAX_GROUPS)

    @model_validator(mode="before")
    @classmethod
    def _version_is_integer(cls, value):
        if isinstance(value, dict) and "version" in value and type(value["version"]) is not int:
            raise ValueError("version must be the integer 1")
        return value

    @model_validator(mode="after")
    def _integrity(self, info: ValidationInfo) -> Self:
        identifiers = [item.id for item in [*self.nodes, *self.edges, *self.groups]]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("node, edge, and group IDs must be globally unique")
        node_ids = {node.id for node in self.nodes}
        group_ids = {group.id for group in self.groups}
        for node in self.nodes:
            if node.group_id is not None and node.group_id not in group_ids:
                raise ValueError(f"node {node.id!r} references unknown group {node.group_id!r}")
        for edge in self.edges:
            if edge.source not in node_ids or edge.target not in node_ids:
                raise ValueError(f"edge {edge.id!r} must reference existing nodes")
        text_length = len(self.title) + len(self.caption)
        text_length += sum(len(item.label) for item in [*self.nodes, *self.edges, *self.groups])
        text_length += sum(
            len(source.quote) for item in [*self.nodes, *self.edges] for source in item.sources
        )
        if text_length > MAX_TEXT_LENGTH:
            raise ValueError(f"total figure text exceeds {MAX_TEXT_LENGTH} characters")
        if info.context and "section_texts" in info.context:
            self.validate_source_references(info.context["section_texts"])
        return self

    def validate_source_references(self, section_texts: Sequence[str]) -> None:
        """Optionally verify references against the owning document's ordered sections.

        Without document text, validation establishes structure, not provenance.
        Whitespace normalization tolerates PDF line wrapping; quotes stay unchanged.
        """
        if (
            not isinstance(section_texts, Sequence)
            or isinstance(section_texts, (str, bytes))
            or not all(isinstance(section, str) for section in section_texts)
        ):
            raise ValueError("section_texts must be a sequence of section strings")
        normalized = [" ".join(section.split()) for section in section_texts]
        for item in [*self.nodes, *self.edges]:
            for source in item.sources:
                if source.section_index >= len(normalized):
                    raise ValueError(f"source section {source.section_index} does not exist")
                if " ".join(source.quote.split()) not in normalized[source.section_index]:
                    raise ValueError(f"source quote for {item.id!r} is absent from its section")


def validate_export_options(width: int, style_preset: str) -> None:
    if type(width) is not int or not MIN_EXPORT_WIDTH <= width <= MAX_EXPORT_WIDTH:
        raise ValueError(f"width must be an integer in {MIN_EXPORT_WIDTH}-{MAX_EXPORT_WIDTH}")
    if style_preset not in ("classic", "pastel"):
        raise ValueError("style_preset must be 'classic' or 'pastel'")
