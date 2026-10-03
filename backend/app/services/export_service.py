from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import require_project
from app.core.exceptions import BadRequestException
from app.models import Document, FigureExport, Job
from app.schemas.figure_export import ExportRequest
from app.schemas.figure_spec import FigureSpec
from app.services.job_service import enqueue_job
from app.services.local_storage_service import LocalStorageService
from app.services.process_service import run_offline
from app.services.prompt_service import PromptService
from app.services.style_service import resolve_palette


async def submit_export(db: AsyncSession, prompt_id: str, data: ExportRequest) -> Job:
    prompt = await PromptService(db).get_prompt(prompt_id)
    project = await require_project(db, prompt.project_id)
    raw = data.figure_spec.model_dump() if data.figure_spec else prompt.figure_spec
    if raw is None:
        raise BadRequestException(
            "Generate or supply an editable FigureSpec first. Raster images are not converted to vectors."
        )
    spec = FigureSpec.model_validate(raw)
    if prompt.document_id:
        document = await db.get(Document, prompt.document_id)
        if document:
            try:
                spec.validate_source_references(
                    [section.get("content", "") for section in document.sections or []]
                )
            except ValueError as exc:
                raise BadRequestException(
                    "Figure source references do not match the document"
                ) from exc
    metadata = prompt.generation_metadata or {}
    palette = metadata.get("palette") or await resolve_palette(
        db, project.color_scheme, project.custom_colors
    )
    payload = {
        "prompt_id": prompt.id,
        "prompt_revision": prompt.revision,
        "figure_spec": spec.model_dump(),
        "format": data.format,
        "width": data.width,
        "style_preset": prompt.style_preset or project.style_preset,
        "palette": palette,
    }
    export_id = str(uuid4())
    job, created = await enqueue_job(
        db,
        project_id=project.id,
        kind="export",
        payload=payload,
        resource_id=export_id,
        idempotency_key=data.idempotency_key,
    )
    if created:
        db.add(
            FigureExport(
                id=export_id,
                project_id=project.id,
                prompt_id=prompt.id,
                prompt_revision=prompt.revision,
                job_id=job.id,
                format=data.format,
                figure_spec=payload["figure_spec"],
                generation_metadata={
                    "style_preset": payload["style_preset"],
                    "palette": palette,
                    "renderer": "figure_spec_v1",
                    "spec_override": data.figure_spec is not None,
                },
            )
        )
    await db.commit()
    await db.refresh(job)
    return job


async def render_export_job(job: Job, db: AsyncSession) -> dict:
    await require_project(db, job.project_id)
    record = await db.get(FigureExport, job.resource_id)
    if record is None:
        raise BadRequestException("Export record no longer exists")
    payload = job.payload
    output = await run_offline(
        "export_figure",
        payload["figure_spec"],
        format=payload["format"],
        width=payload["width"],
        style_preset=payload["style_preset"],
        palette=payload["palette"],
    )
    record.storage_path = LocalStorageService().save_export(
        f"{job.project_id}/{record.id}.{output['extension']}", output["data"]
    )
    record.width_px, record.height_px = output["width"], output["height"]
    record.media_type = output["media_type"]
    record.generation_status = "completed"
    record.generation_error = None
    return {"export_id": record.id}
