"""Shared provider output schema and local validation of every returned field."""

from copy import deepcopy

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.figure_spec import FigureSpec


class GeneratedFigure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    figure_number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=300)
    suggested_figure_type: str = Field(min_length=1, max_length=50)
    suggested_aspect_ratio: str = Field(pattern=r"^(1:1|16:9|9:16|4:3|3:4|3:2|2:3|21:9|9:21|1:2)$")
    prompt: str = Field(min_length=500, max_length=60000)
    source_section_titles: list[str] = Field(max_length=100)
    rationale: str = Field(max_length=4000)
    figure_spec: FigureSpec | None


class GeneratedFigureBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    figures: list[GeneratedFigure] = Field(min_length=1, max_length=8)


def strict_json_schema(schema: dict) -> dict:
    result = deepcopy(schema)

    def visit(item):
        if isinstance(item, dict):
            item.pop("default", None)
            if item.get("type") == "object":
                item["additionalProperties"] = False
                item["required"] = list(item.get("properties", {}))
            for value in item.values():
                visit(value)
        elif isinstance(item, list):
            for value in item:
                visit(value)

    visit(result)
    return result
