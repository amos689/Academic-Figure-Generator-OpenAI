"""Effective local settings and explicitly requested, non-generative API checks."""

from __future__ import annotations

import asyncio

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models import Image, Job
from app.services import style_service

CHECK_TIMEOUT_SECONDS = 10.0


def _check_error(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return "Access denied. Check the configured API key and model permissions."
    if status == 404:
        return "A configured model is unavailable or cannot be accessed."
    if status == 429:
        return "The provider rate limit was reached. Try the check again later."
    if isinstance(exc, TimeoutError) or type(exc).__name__ == "APITimeoutError":
        return "The model access check timed out. Check the API base and network connection."
    return "Model access could not be verified. Check the API base, network, and credentials."


class ConfigurationService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings if settings is not None else get_settings()

    async def effective_configuration(self, db: AsyncSession) -> dict:
        settings = self.settings
        outcomes = dict(
            (await db.execute(select(Job.status, func.count()).group_by(Job.status))).all()
        )
        image_count = await db.scalar(
            select(func.count()).select_from(Image).where(Image.generation_status == "completed")
        )
        profiles = [style_service.generation_profile(profile) for profile in ("quality", "draft")]
        profiles[0].update(
            text_reasoning_effort=settings.OPENAI_TEXT_REASONING_EFFORT,
            image_quality=settings.OPENAI_IMAGE_QUALITY,
        )
        return {
            "api_key_configured": bool(settings.OPENAI_API_KEY),
            "api_key_source": settings.api_key_source,
            "api_base": settings.OPENAI_API_BASE,
            "text_model": settings.OPENAI_TEXT_MODEL,
            "text_reasoning_effort": settings.OPENAI_TEXT_REASONING_EFFORT,
            "text_max_output_tokens": settings.OPENAI_TEXT_MAX_OUTPUT_TOKENS,
            "image_model": settings.OPENAI_IMAGE_MODEL,
            "image_quality": settings.OPENAI_IMAGE_QUALITY,
            "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
            "max_concurrent_jobs": settings.MAX_CONCURRENT_JOBS,
            "styles": style_service.style_presets(),
            "profiles": profiles,
            "usage_summary": {
                "jobs_completed": outcomes.get("succeeded", 0),
                "jobs_failed": outcomes.get("failed", 0),
                # Legacy rows and ambiguous attempts lack a complete provider usage ledger.
                "input_tokens": None,
                "output_tokens": None,
                "image_count": image_count or 0,
                "duration_ms": None,
            },
        }

    async def check_connectivity(self) -> dict:
        """Keep the synchronous SDK's construction, requests, and cleanup off the event loop."""
        return await asyncio.to_thread(self._check_models)

    def _check_models(self) -> dict:
        from openai import OpenAI

        settings = self.settings
        models = [
            {"model": model, "accessible": False}
            for model in dict.fromkeys((settings.OPENAI_TEXT_MODEL, settings.OPENAI_IMAGE_MODEL))
        ]
        if not settings.OPENAI_API_KEY:
            return {"ok": False, "models": models, "detail": "No API key is configured."}
        errors = []
        try:
            with OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_API_BASE,
                timeout=CHECK_TIMEOUT_SECONDS,
                max_retries=0,
            ) as client:
                for model in models:
                    try:
                        client.models.retrieve(model["model"])
                    except Exception as exc:
                        errors.append(_check_error(exc))
                    else:
                        model["accessible"] = True
        except Exception as exc:
            errors.append(_check_error(exc))
        result = {
            "ok": not errors and all(model["accessible"] for model in models),
            "models": models,
        }
        if errors:
            result["detail"] = " ".join(dict.fromkeys(errors))
        return result
