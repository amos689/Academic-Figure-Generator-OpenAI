import asyncio

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import FileValidationException
from app.models import Document, FigureExport, Image, Job
from app.services.document_service import DocumentService
from app.services.job_service import JobRunner
from app.services.local_storage_service import LocalStorageService
from app.services.process_service import run_offline


async def resource_failure(job: Job, db: AsyncSession, status: str, error: str) -> None:
    if job.kind == "document":
        await db.execute(
            update(Document)
            .where(Document.id == job.resource_id, Document.job_id == job.id)
            .values(parse_status=status, parse_error=error)
        )
    elif job.kind == "image":
        await db.execute(
            update(Image)
            .where(Image.id == job.resource_id, Image.job_id == job.id)
            .values(generation_status=status, generation_error=error)
        )
    elif job.kind == "export":
        await db.execute(
            update(FigureExport)
            .where(FigureExport.id == job.resource_id, FigureExport.job_id == job.id)
            .values(generation_status=status, generation_error=error)
        )


async def parse_document(job: Job, db: AsyncSession) -> dict:
    document = await db.get(Document, job.resource_id)
    if document is None:
        raise FileValidationException("Document no longer exists")
    document.parse_status = "parsing"
    await db.commit()
    storage = LocalStorageService()
    contents = await asyncio.to_thread(storage.get_file, document.storage_path)
    result = await run_offline("parse_document", contents, document.file_type)
    if not result.get("full_text", "").strip():
        raise FileValidationException(
            "No extractable text found. Supply a text-based PDF, DOCX, or TXT; OCR is not available."
        )
    document.full_text = result["full_text"]
    document.sections = result["sections"]
    document.page_count = result["page_count"]
    document.parse_status = "completed"
    document.parse_error = None
    return {"document_id": document.id, "section_count": len(document.sections)}


def register_handlers(runner: JobRunner) -> None:
    from app.services.export_service import render_export_job
    from app.services.prompt_generation_service import generate_prompt_job
    from app.services.image_generation_service import generate_image_job

    runner.register("document", parse_document, resource_failure)
    runner.register("prompt", generate_prompt_job, resource_failure)
    runner.register("image", generate_image_job, resource_failure)
    runner.register("export", render_export_job, resource_failure)
