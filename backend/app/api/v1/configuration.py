"""Read-only effective settings and an explicit model access check."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import ApiKeySource
from app.dependencies import get_db
from app.services.configuration_service import ConfigurationService
from app.services.style_service import style_presets

router = APIRouter(tags=["Configuration"])


class UsageSummary(BaseModel):
    jobs_completed: int
    jobs_failed: int
    input_tokens: int | None
    output_tokens: int | None
    image_count: int
    duration_ms: int | None


class GenerationProfile(BaseModel):
    id: str
    name: str
    text_reasoning_effort: str
    image_quality: str


class ConfigurationResponse(BaseModel):
    api_key_configured: bool
    api_key_source: ApiKeySource
    api_base: str
    text_model: str
    text_reasoning_effort: str
    text_max_output_tokens: int
    image_model: str
    image_quality: str
    max_upload_size_mb: int
    max_concurrent_jobs: int
    styles: list[dict[str, str]]
    profiles: list[GenerationProfile]
    usage_summary: UsageSummary


class ModelAccess(BaseModel):
    model: str
    accessible: bool


class ConfigurationCheckResponse(BaseModel):
    ok: bool
    models: list[ModelAccess]
    detail: str | None = None


@router.get("/configuration", response_model=ConfigurationResponse)
async def read_configuration(db: AsyncSession = Depends(get_db)):
    return await ConfigurationService().effective_configuration(db)


@router.get("/styles", response_model=list[dict[str, str]])
async def read_styles():
    return style_presets()


@router.post(
    "/configuration/check",
    response_model=ConfigurationCheckResponse,
    response_model_exclude_none=True,
)
async def check_configuration():
    return await ConfigurationService().check_connectivity()
