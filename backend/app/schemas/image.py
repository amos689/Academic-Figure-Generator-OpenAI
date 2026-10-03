from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Resolution = Literal["1K", "2K", "4K"]
AspectRatio = Literal["1:1", "16:9", "9:16", "4:3", "3:4", "3:2", "2:3", "21:9", "9:21", "1:2"]


class ImageGenerateRequest(BaseModel):
    resolution: Resolution = "2K"
    aspect_ratio: AspectRatio = "16:9"
    color_scheme: str | None = None
    custom_colors: dict | None = None
    style_preset: Literal["classic", "pastel"] | None = None
    profile: Literal["quality", "draft"] = "quality"
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=128)


class ImageDirectGenerateRequest(ImageGenerateRequest):
    prompt: str = Field(min_length=1, max_length=60000)
    project_id: str | None = None


class ImageEditRequest(BaseModel):
    edit_instruction: str
    resolution: str = "2K"


class ImageUpdate(BaseModel):
    favorite: bool | None = None
    selected: bool | None = None


class ImageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    prompt_id: str | None
    project_id: str | None
    resolution: str
    aspect_ratio: str
    color_scheme: str | None
    storage_path: str | None
    file_size_bytes: int | None
    width_px: int | None
    height_px: int | None
    generation_status: str
    generation_duration_ms: int | None
    generation_error: str | None
    retry_count: int
    download_url: str | None = None
    created_at: datetime
    job_id: str | None = None
    parent_image_id: str | None = None
    prompt_revision: int | None = None
    generation_model: str | None = None
    quality: str | None = None
    style_preset: str | None = None
    generation_metadata: dict | None = None
    favorite: bool = False
    selected: bool = False


class ImageStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    generation_status: str
    generation_error: str | None = None
    job_id: str | None = None
