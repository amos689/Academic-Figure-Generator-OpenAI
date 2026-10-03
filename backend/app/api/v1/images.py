"""Durable raster generation, edit ancestry, selection, and private downloads."""

import asyncio
import hashlib
import json
import mimetypes

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.v1.access import require_project
from app.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.dependencies import get_db
from app.models import Image, Project
from app.schemas.image import (
    ImageDirectGenerateRequest,
    ImageGenerateRequest,
    ImageResponse,
    ImageStatusResponse,
    ImageUpdate,
)
from app.services.image_generation_service import submit_image
from app.services.local_storage_service import LocalStorageService
from app.services.prompt_service import PromptService
from app.services.upload_service import read_upload, reference_png, validate_mask

router = APIRouter(tags=["Images"])


async def _get_image(db: AsyncSession, image_id: str) -> Image:
    image = await db.get(Image, image_id)
    if image is None:
        raise NotFoundException("Image not found")
    await require_project(db, image.project_id)
    return image


def _response(image: Image) -> ImageResponse:
    response = ImageResponse.model_validate(image)
    if image.storage_path:
        response.download_url = f"{get_settings().API_V1_PREFIX}/images/{image.id}/download"
    return response


@router.post(
    "/prompts/{prompt_id}/images/generate", response_model=ImageStatusResponse, status_code=202
)
async def generate_image_from_prompt(
    prompt_id: str, data: ImageGenerateRequest, db: AsyncSession = Depends(get_db)
):
    prompt = await PromptService(db).get_prompt(prompt_id)
    return await submit_image(
        db, prompt.project_id, prompt.active_prompt or "", data, prompt=prompt
    )


@router.post("/images/generate-direct", response_model=ImageStatusResponse, status_code=202)
async def generate_image_direct(
    data: ImageDirectGenerateRequest, db: AsyncSession = Depends(get_db)
):
    project_id = data.project_id
    if project_id is None:
        project_id = "00000000-0000-4000-8000-000000000001"
        await db.execute(
            insert(Project)
            .values(id=project_id, name="Quick figures", status="active")
            .on_conflict_do_nothing(index_elements=["id"])
        )
    return await submit_image(db, project_id, data.prompt, data)


@router.get("/projects/{project_id}/images", response_model=list[ImageResponse])
async def list_project_images(project_id: str, db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id)
    return [
        _response(image)
        for image in await db.scalars(
            select(Image)
            .where(Image.project_id == project_id)
            .order_by(Image.created_at.desc(), Image.id.desc())
        )
    ]


@router.get("/images/{image_id}", response_model=ImageResponse)
async def get_image(image_id: str, db: AsyncSession = Depends(get_db)):
    return _response(await _get_image(db, image_id))


@router.get("/images/{image_id}/download")
async def download_image(image_id: str, db: AsyncSession = Depends(get_db)):
    image = await _get_image(db, image_id)
    if not image.storage_path or image.generation_status != "completed":
        raise NotFoundException("Image file is not available")
    path = LocalStorageService().get_file_path(image.storage_path)
    if not path.is_file():
        raise NotFoundException("Image file is missing")
    return FileResponse(
        path,
        media_type=mimetypes.guess_type(path.name)[0] or "image/png",
        filename=path.name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.get("/images/{image_id}/status", response_model=ImageStatusResponse)
async def get_image_status(image_id: str, db: AsyncSession = Depends(get_db)):
    return await _get_image(db, image_id)


@router.patch("/images/{image_id}", response_model=ImageResponse)
async def update_image(image_id: str, data: ImageUpdate, db: AsyncSession = Depends(get_db)):
    image = await _get_image(db, image_id)
    if data.favorite is not None:
        image.favorite = data.favorite
    if data.selected is not None:
        if data.selected and image.generation_status != "completed":
            raise BadRequestException("Only completed images can be selected")
        if data.selected:
            await db.execute(
                update(Image)
                .where(Image.project_id == image.project_id, Image.prompt_id == image.prompt_id)
                .values(selected=False)
            )
        image.selected = data.selected
    await db.flush()
    await db.refresh(image)
    return _response(image)


@router.get("/images/{image_id}/provenance")
async def image_provenance(image_id: str, db: AsyncSession = Depends(get_db)):
    image = await _get_image(db, image_id)
    return {
        "image_id": image.id,
        "prompt_id": image.prompt_id,
        "prompt_revision": image.prompt_revision,
        "parent_image_id": image.parent_image_id,
        "generation_model": image.generation_model,
        "quality": image.quality,
        "resolution": image.resolution,
        "aspect_ratio": image.aspect_ratio,
        "style_preset": image.style_preset,
        "palette": image.custom_colors,
        "prompt": image.final_prompt_sent,
        "edit_instruction": image.edit_instruction,
        "generation_metadata": image.generation_metadata,
        "duration_ms": image.generation_duration_ms,
    }


@router.post("/images/{image_id}/edit", response_model=ImageStatusResponse, status_code=202)
async def edit_image(
    image_id: str,
    edit_instruction: str = Form(..., min_length=1, max_length=6000),
    reference_image: UploadFile | None = File(None),
    mask_image: UploadFile | None = File(None),
    idempotency_key: str | None = Form(None, min_length=1, max_length=128),
    db: AsyncSession = Depends(get_db),
):
    source = await _get_image(db, image_id)
    if not edit_instruction.strip():
        raise BadRequestException("Edit instruction must not be blank")
    storage = LocalStorageService()
    reference_path = source.storage_path
    if reference_image is not None:
        contents = reference_png(await read_upload(reference_image))
        digest = hashlib.sha256(contents).hexdigest()
        reference_path = storage.save_upload(f"references/{image_id}/{digest}.png", contents)
    if not reference_path or not storage.file_exists(reference_path):
        raise BadRequestException("Generate an image or upload a reference before editing")
    mask_path = None
    if mask_image is not None:
        contents = await read_upload(mask_image)
        validate_mask(storage.get_file(reference_path), contents)
        digest = hashlib.sha256(contents).hexdigest()
        mask_path = storage.save_upload(f"masks/{image_id}/{digest}.png", contents)
    metadata = source.generation_metadata or {}
    data = ImageGenerateRequest(
        resolution=source.resolution,
        aspect_ratio=source.aspect_ratio,
        color_scheme=source.color_scheme,
        custom_colors=source.custom_colors,
        style_preset=source.style_preset,
        profile=metadata.get("profile", "quality"),
        idempotency_key=idempotency_key,
    )
    return await submit_image(
        db,
        source.project_id,
        metadata.get("source_prompt")
        or source.final_prompt_sent
        or "Preserve the scientific content of this reference figure.",
        data,
        parent=source,
        reference_path=reference_path,
        mask_path=mask_path,
        edit_instruction=edit_instruction.strip(),
    )


@router.get("/images/{image_id}/stream")
async def stream_image_status(image_id: str, db: AsyncSession = Depends(get_db)):
    await _get_image(db, image_id)

    async def events():
        from app.dependencies import get_async_session_factory

        last_status = None
        while True:
            async with get_async_session_factory()() as session:
                current = await session.get(Image, image_id)
                if current is None:
                    break
                status = current.generation_status
                if status != last_status:
                    yield {
                        "event": "status",
                        "data": json.dumps(
                            {
                                "id": image_id,
                                "status": status,
                                "generation_error": current.generation_error,
                            }
                        ),
                    }
                    last_status = status
                if status in {"completed", "failed", "interrupted", "cancelled"}:
                    yield {"event": "done", "data": json.dumps({"status": status})}
                    break
            await asyncio.sleep(2)

    return EventSourceResponse(events())
