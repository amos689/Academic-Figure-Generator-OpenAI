"""Image generation, retrieval, editing, and SSE status endpoints — personal-use."""

import asyncio
import json
import logging
import mimetypes
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.dependencies import get_db
from app.models.image import Image
from app.models.project import Project
from app.models.prompt import Prompt
from app.schemas.image import (
    ImageDirectGenerateRequest,
    ImageGenerateRequest,
    ImageResponse,
    ImageStatusResponse,
)
from app.services.local_storage_service import LocalStorageService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["Images"])


def _ensure_openai_api_key_configured() -> None:
    settings = get_settings()
    if not settings.OPENAI_API_KEY:
        raise BadRequestException(
            "OPENAI_API_KEY not configured. Set it in your Mac environment, "
            "a local .env file, or backend/app/config.py."
        )


async def _get_project(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project: Project | None = result.scalar_one_or_none()
    if project is None or project.status == "deleted":
        raise NotFoundException("Project not found")
    return project


def _image_to_response(image: Image, download_url: str | None = None) -> ImageResponse:
    return ImageResponse(
        id=image.id,
        prompt_id=image.prompt_id,
        project_id=image.project_id,
        resolution=image.resolution,
        aspect_ratio=image.aspect_ratio,
        color_scheme=image.color_scheme,
        storage_path=image.storage_path,
        file_size_bytes=image.file_size_bytes,
        width_px=image.width_px,
        height_px=image.height_px,
        generation_status=image.generation_status,
        generation_duration_ms=image.generation_duration_ms,
        generation_error=image.generation_error,
        retry_count=image.retry_count,
        download_url=download_url,
        created_at=image.created_at,
    )


async def _generate_image_async(
    image_id: str,
    prompt_text: str,
    resolution: str,
    aspect_ratio: str,
    color_scheme: str | None,
    reference_image_path: str | None,
    edit_instruction: str | None,
) -> None:
    """Background task: call OpenAI Image API and update DB record."""
    from app.dependencies import get_async_session_factory  # noqa: PLC0415
    from app.services.image_service import ImageService  # noqa: PLC0415

    session_factory = get_async_session_factory()
    storage = LocalStorageService()

    async with session_factory() as session:
        result = await session.execute(select(Image).where(Image.id == image_id))
        image: Image | None = result.scalar_one_or_none()
        if image is None:
            logger.error("Image %s not found for generation", image_id)
            return

        image.generation_status = "generating"
        session.add(image)
        await session.commit()

        try:
            image_service = ImageService()

            # Load reference image bytes if path provided
            reference_bytes: bytes | None = None
            if reference_image_path and storage.file_exists(reference_image_path):
                reference_bytes = storage.get_file(reference_image_path)

            # ImageService.generate_image is synchronous — run in executor
            import asyncio  # noqa: PLC0415

            loop = asyncio.get_event_loop()
            generated_data = await loop.run_in_executor(
                None,
                lambda: image_service.generate_image(
                    prompt=prompt_text,
                    resolution=resolution,
                    aspect_ratio=aspect_ratio,
                    reference_image_bytes=reference_bytes,
                    edit_instruction=edit_instruction,
                ),
            )

            # Decode base64 result to bytes and save locally
            image_b64 = generated_data.get("image_base64", "")
            if image_b64:
                image_bytes = ImageService.image_bytes_from_base64(image_b64)
                file_name = f"{image_id}.png"
                storage_path = storage.save_figure(
                    f"{image.project_id}/{file_name}", image_bytes
                )
                image.storage_path = storage_path
                image.file_size_bytes = len(image_bytes)
                image.width_px = generated_data.get("width")
                image.height_px = generated_data.get("height")

            image.generation_status = "completed"
            image.generation_duration_ms = generated_data.get("duration_ms")
            image.final_prompt_sent = prompt_text

        except Exception as exc:
            image.generation_status = "failed"
            image.generation_error = str(exc)
            logger.error("Image %s generation failed: %s", image_id, exc)

        session.add(image)
        await session.commit()


@router.post(
    "/prompts/{prompt_id}/images/generate",
    response_model=ImageStatusResponse,
    status_code=202,
)
async def generate_image_from_prompt(
    prompt_id: str,
    data: ImageGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate an image from an existing prompt (async background task)."""
    result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
    prompt: Prompt | None = result.scalar_one_or_none()
    if prompt is None:
        raise NotFoundException("Prompt not found")

    if not prompt.active_prompt:
        raise BadRequestException("Prompt has no text. Generate or edit the prompt first.")

    _ensure_openai_api_key_configured()

    image = Image(
        prompt_id=prompt.id,
        project_id=prompt.project_id,
        resolution=data.resolution,
        aspect_ratio=data.aspect_ratio,
        color_scheme=data.color_scheme,
        generation_status="pending",
    )
    db.add(image)
    await db.flush()
    await db.refresh(image)

    # Launch background task (no Celery)
    asyncio.create_task(
        _generate_image_async(
            image_id=image.id,
            prompt_text=prompt.active_prompt,
            resolution=data.resolution,
            aspect_ratio=data.aspect_ratio,
            color_scheme=data.color_scheme,
            reference_image_path=None,
            edit_instruction=None,
        )
    )

    return ImageStatusResponse(
        id=image.id,
        generation_status=image.generation_status,
    )


@router.post(
    "/images/generate-direct",
    response_model=ImageStatusResponse,
    status_code=202,
)
async def generate_image_direct(
    data: ImageDirectGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Generate an image from custom prompt text (no linked Prompt record)."""
    project_id = data.project_id

    _ensure_openai_api_key_configured()

    if project_id is None:
        # Auto-create or reuse a default project
        result = await db.execute(
            select(Project).where(
                Project.name == "直接生成",
                Project.status == "active",
            )
        )
        project = result.scalar_one_or_none()
        if project is None:
            project = Project(
                name="直接生成",
                description="通过直接生成模式创建的图片",
            )
            db.add(project)
            await db.flush()
            await db.refresh(project)
        project_id = project.id
    else:
        await _get_project(project_id, db)

    image = Image(
        prompt_id=None,
        project_id=project_id,
        resolution=data.resolution,
        aspect_ratio=data.aspect_ratio,
        color_scheme=data.color_scheme,
        final_prompt_sent=data.prompt,
        generation_status="pending",
    )
    db.add(image)
    await db.flush()
    await db.refresh(image)

    asyncio.create_task(
        _generate_image_async(
            image_id=image.id,
            prompt_text=data.prompt,
            resolution=data.resolution,
            aspect_ratio=data.aspect_ratio,
            color_scheme=data.color_scheme,
            reference_image_path=None,
            edit_instruction=None,
        )
    )

    return ImageStatusResponse(
        id=image.id,
        generation_status=image.generation_status,
    )


@router.get("/projects/{project_id}/images", response_model=list[ImageResponse])
async def list_project_images(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_project(project_id, db)
    result = await db.execute(
        select(Image)
        .where(Image.project_id == project_id)
        .order_by(Image.created_at.desc())
    )
    return [_image_to_response(img) for img in result.scalars().all()]


@router.get("/images/{image_id}", response_model=ImageResponse)
async def get_image(
    image_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Image).where(Image.id == image_id))
    image: Image | None = result.scalar_one_or_none()
    if image is None:
        raise NotFoundException("Image not found")

    download_url: str | None = None
    if image.storage_path:
        download_url = f"{get_settings().API_V1_PREFIX}/images/{image.id}/download"

    return _image_to_response(image, download_url=download_url)


@router.get("/images/{image_id}/download")
async def download_image(
    image_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Image).where(Image.id == image_id))
    image: Image | None = result.scalar_one_or_none()
    if image is None:
        raise NotFoundException("Image not found")
    if not image.storage_path:
        raise NotFoundException("Image file not available")

    storage = LocalStorageService()
    file_bytes = storage.get_file(image.storage_path)

    guessed_type, _ = mimetypes.guess_type(image.storage_path)
    media_type = guessed_type or "application/octet-stream"
    filename = image.storage_path.split("/")[-1] or f"{image_id}.png"
    quoted = quote(filename)
    headers = {"Content-Disposition": f"inline; filename*=UTF-8''{quoted}"}

    return StreamingResponse(iter([file_bytes]), media_type=media_type, headers=headers)


@router.get("/images/{image_id}/status", response_model=ImageStatusResponse)
async def get_image_status(
    image_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Image).where(Image.id == image_id))
    image: Image | None = result.scalar_one_or_none()
    if image is None:
        raise NotFoundException("Image not found")
    return ImageStatusResponse(
        id=image.id,
        generation_status=image.generation_status,
        generation_error=image.generation_error,
    )


@router.post(
    "/images/{image_id}/edit",
    response_model=ImageStatusResponse,
    status_code=202,
)
async def edit_image(
    image_id: str,
    edit_instruction: str = Form(...),
    reference_image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Image-to-image editing via OpenAI Image API."""
    result = await db.execute(select(Image).where(Image.id == image_id))
    source_image: Image | None = result.scalar_one_or_none()
    if source_image is None:
        raise NotFoundException("Image not found")

    _ensure_openai_api_key_configured()

    storage = LocalStorageService()
    reference_path: str | None = source_image.storage_path

    if reference_image is not None:
        contents = await reference_image.read()
        ref_filename = reference_image.filename or "reference.png"
        reference_path = storage.save_upload(f"references/{image_id}/{ref_filename}", contents)

    if not reference_path:
        raise BadRequestException(
            "No reference image available. Upload one or use an image that has been generated."
        )

    new_image = Image(
        prompt_id=source_image.prompt_id,
        project_id=source_image.project_id,
        resolution=source_image.resolution,
        aspect_ratio=source_image.aspect_ratio,
        color_scheme=source_image.color_scheme,
        reference_image_path=reference_path,
        edit_instruction=edit_instruction,
        generation_status="pending",
    )
    db.add(new_image)
    await db.flush()
    await db.refresh(new_image)

    asyncio.create_task(
        _generate_image_async(
            image_id=new_image.id,
            prompt_text=source_image.final_prompt_sent or "",
            resolution=source_image.resolution,
            aspect_ratio=source_image.aspect_ratio,
            color_scheme=source_image.color_scheme,
            reference_image_path=reference_path,
            edit_instruction=edit_instruction,
        )
    )

    return ImageStatusResponse(
        id=new_image.id,
        generation_status=new_image.generation_status,
    )


@router.get("/images/{image_id}/stream")
async def stream_image_status(
    image_id: str,
    db: AsyncSession = Depends(get_db),
):
    """SSE endpoint for real-time image generation status."""
    result = await db.execute(select(Image).where(Image.id == image_id))
    if result.scalar_one_or_none() is None:
        raise NotFoundException("Image not found")

    async def event_generator():
        from app.dependencies import get_async_session_factory  # noqa: PLC0415

        session_factory = get_async_session_factory()
        terminal_states = {"completed", "failed"}
        last_status: str | None = None

        while True:
            async with session_factory() as session:
                result = await session.execute(select(Image).where(Image.id == image_id))
                current_image: Image | None = result.scalar_one_or_none()

            if current_image is None:
                yield {"event": "error", "data": json.dumps({"error": "Image not found"})}
                break

            current_status = current_image.generation_status
            if current_status != last_status:
                last_status = current_status
                event_data = {
                    "id": str(current_image.id),
                    "status": current_status,
                    "storage_path": current_image.storage_path,
                    "generation_duration_ms": current_image.generation_duration_ms,
                }
                yield {"event": "status", "data": json.dumps(event_data)}

                if current_status in terminal_states:
                    yield {"event": "done", "data": json.dumps({"status": current_status})}
                    break

            await asyncio.sleep(2)

    return EventSourceResponse(event_generator())
