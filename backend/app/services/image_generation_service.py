import asyncio
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import require_api_key, require_project
from app.config import get_settings
from app.core.exceptions import BadRequestException
from app.models import Image, Job, Prompt
from app.schemas.image import ImageGenerateRequest
from app.services.image_service import ImageService
from app.services.job_service import enqueue_job
from app.services.local_storage_service import LocalStorageService
from app.services.style_service import compose_image_prompt, generation_profile, resolve_palette


async def submit_image(
    db: AsyncSession,
    project_id: str,
    prompt_text: str,
    data: ImageGenerateRequest,
    *,
    prompt: Prompt | None = None,
    parent: Image | None = None,
    reference_path: str | None = None,
    mask_path: str | None = None,
    edit_instruction: str | None = None,
) -> Image:
    require_api_key()
    project = await require_project(db, project_id)
    if not prompt_text.strip():
        raise BadRequestException("Image prompt must not be blank")
    style = (
        data.style_preset
        or (parent.style_preset if parent else None)
        or (prompt.style_preset if prompt else None)
        or project.style_preset
    )
    prompt_metadata = (prompt.generation_metadata or {}) if prompt else {}
    parent_metadata = (parent.generation_metadata or {}) if parent else {}
    color_name = (
        data.color_scheme
        or (parent.color_scheme if parent else None)
        or prompt_metadata.get("color_scheme")
        or project.color_scheme
    )
    inherited_palette = parent_metadata.get("palette") or prompt_metadata.get("palette")
    custom = (
        data.custom_colors
        if data.custom_colors is not None
        else (
            inherited_palette
            if not data.color_scheme and inherited_palette
            else project.custom_colors
            if color_name == project.color_scheme
            else None
        )
    )
    palette = await resolve_palette(db, color_name, custom)
    final_prompt = compose_image_prompt(prompt_text, style, palette)
    profile = generation_profile(data.profile)
    settings = get_settings()
    payload = {
        "prompt": final_prompt,
        "source_prompt": prompt_text,
        "prompt_id": prompt.id if prompt else None,
        "prompt_revision": prompt.revision
        if prompt
        else (parent.prompt_revision if parent else None),
        "parent_image_id": parent.id if parent else None,
        "resolution": data.resolution,
        "aspect_ratio": data.aspect_ratio,
        "style_preset": style,
        "palette": palette,
        "color_scheme": color_name,
        "profile": data.profile,
        "model": settings.OPENAI_IMAGE_MODEL,
        "quality": profile["image_quality"],
        "reference_path": reference_path,
        "mask_path": mask_path,
        "edit_instruction": edit_instruction,
    }
    image_id = str(uuid4())
    job, created = await enqueue_job(
        db,
        project_id=project_id,
        kind="image",
        payload=payload,
        resource_id=image_id,
        idempotency_key=data.idempotency_key,
    )
    if not created:
        image = await db.get(Image, job.resource_id)
        if image is None:
            raise BadRequestException("Original image request is no longer available")
        return image
    image = Image(
        id=image_id,
        project_id=project_id,
        prompt_id=prompt.id if prompt else (parent.prompt_id if parent else None),
        job_id=job.id,
        parent_image_id=parent.id if parent else None,
        prompt_revision=payload["prompt_revision"],
        resolution=data.resolution,
        aspect_ratio=data.aspect_ratio,
        color_scheme=color_name,
        custom_colors=palette,
        style_preset=style,
        generation_model=payload["model"],
        quality=payload["quality"],
        reference_image_path=reference_path,
        mask_image_path=mask_path,
        edit_instruction=edit_instruction,
        final_prompt_sent=final_prompt,
        generation_metadata={
            "profile": data.profile,
            "palette": palette,
            "source_prompt": prompt_text,
        },
        generation_status="pending",
    )
    db.add(image)
    await db.commit()
    await db.refresh(image)
    return image


async def generate_image_job(job: Job, db: AsyncSession) -> dict:
    await require_project(db, job.project_id)
    image = await db.get(Image, job.resource_id)
    if image is None:
        raise BadRequestException("Image record no longer exists")
    image.generation_status = "generating"
    await db.commit()
    payload = job.payload
    storage = LocalStorageService()
    # Missing reference files must fail, never silently turn an edit into a new image.
    reference = (
        storage.get_file(payload["reference_path"]) if payload.get("reference_path") else None
    )
    mask = storage.get_file(payload["mask_path"]) if payload.get("mask_path") else None
    service = ImageService(model=payload["model"], quality=payload["quality"])
    generated = await asyncio.to_thread(
        service.generate_image,
        prompt=payload["prompt"],
        resolution=payload["resolution"],
        aspect_ratio=payload["aspect_ratio"],
        reference_image_bytes=reference,
        mask_image_bytes=mask,
        edit_instruction=payload.get("edit_instruction"),
    )
    contents = service.image_bytes_from_base64(generated["image_base64"])
    extension = {"jpeg": "jpg", "webp": "webp"}.get(generated.get("format"), "png")
    image.storage_path = storage.save_figure(f"{job.project_id}/{image.id}.{extension}", contents)
    image.file_size_bytes = len(contents)
    image.width_px, image.height_px = generated["width"], generated["height"]
    image.generation_duration_ms = generated["duration_ms"]
    image.generation_status = "completed"
    image.generation_error = None
    image.generation_metadata = {
        **(image.generation_metadata or {}),
        **generated.get("generation_metadata", {}),
        "job_id": job.id,
    }
    image.generation_model = image.generation_metadata.get("model", payload["model"])
    return {
        "image_id": image.id,
        "usage": image.generation_metadata.get("usage"),
        "duration_ms": image.generation_duration_ms,
    }
