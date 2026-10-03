from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    paper_field: str | None = None
    color_scheme: str = "okabe-ito"
    custom_colors: dict | None = None
    style_preset: Literal["classic", "pastel"] = "classic"


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    paper_field: str | None = None
    color_scheme: str | None = None
    custom_colors: dict | None = None
    status: Literal["active", "archived"] | None = None
    style_preset: Literal["classic", "pastel"] | None = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str | None
    paper_field: str | None
    color_scheme: str
    custom_colors: dict | None
    style_preset: str
    status: str
    created_at: datetime
    updated_at: datetime | None
    document_count: int = 0
    prompt_count: int = 0
    image_count: int = 0


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
    page: int
    page_size: int
