from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.figure_spec import FigureSpec


class ExportRequest(BaseModel):
    format: Literal["svg", "pdf", "drawio"]
    figure_spec: FigureSpec | None = None
    width: int = Field(default=1600, ge=640, le=4096)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class ExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    prompt_id: str
    prompt_revision: int
    format: str
    created_at: datetime
    generation_status: str
    width_px: int | None
    height_px: int | None
    job_id: str
    generation_error: str | None
    generation_metadata: dict
