from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.figure_spec import FigureSpec


class PromptGenerateRequest(BaseModel):
    document_id: str | None = None
    section_indices: list[Annotated[int, Field(ge=0)]] | None = Field(default=None, max_length=1000)
    color_scheme: str | None = None
    custom_colors: dict | None = None
    figure_types: list[Annotated[str, Field(max_length=100)]] | None = Field(
        default=None, max_length=20
    )
    user_request: str | None = Field(default=None, max_length=6000)
    max_figures: int = Field(default=3, ge=1, le=8)
    template_mode: bool = False
    style_preset: Literal["classic", "pastel"] | None = None
    profile: Literal["quality", "draft"] = "quality"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class PromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    document_id: str | None
    figure_number: int
    title: str | None
    original_prompt: str | None
    edited_prompt: str | None
    active_prompt: str | None
    suggested_figure_type: str | None
    suggested_aspect_ratio: str | None
    source_sections: dict | list | None
    claude_model: str | None
    generation_model: str | None
    revision: int
    figure_spec: dict | None
    style_preset: str | None
    generation_metadata: dict | None
    generation_status: str
    created_at: datetime
    updated_at: datetime | None


class PromptUpdate(BaseModel):
    edited_prompt: str = Field(min_length=1, max_length=60000)
    figure_spec: FigureSpec | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class PromptRestore(BaseModel):
    revision: int = Field(ge=1)
    expected_revision: int | None = Field(default=None, ge=1)


class PromptRevisionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    revision: int
    prompt_text: str
    figure_spec: dict | None
    created_at: datetime


class PromptStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    generation_status: str
