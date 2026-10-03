from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import require_api_key, require_project
from app.core.exceptions import AppException
from app.dependencies import get_db
from app.models import Document, Image, Job
from app.schemas.job import JobResponse
from app.services.job_handlers import resource_failure
from app.services.job_service import enqueue_job, get_job, now

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    project_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    query = select(Job)
    if project_id:
        await require_project(db, project_id)
        query = query.where(Job.project_id == project_id)
    return list(await db.scalars(query.order_by(Job.created_at.desc(), Job.id.desc()).limit(limit)))


@router.get("/{job_id}", response_model=JobResponse)
async def read_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await get_job(db, job_id)
    await require_project(db, job.project_id)
    return job


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    job = await get_job(db, job_id)
    await require_project(db, job.project_id)
    result = await db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status == "queued")
        .values(status="cancelled", stage="cancelled", finished_at=now())
    )
    if result.rowcount != 1:
        raise AppException(
            409,
            "Only queued jobs can be cancelled. A started provider call cannot be recalled.",
            "CONFLICT",
        )
    await resource_failure(job, db, "cancelled", "Cancelled before processing")
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/{job_id}/retry", response_model=JobResponse, status_code=202)
async def retry_job(job_id: str, db: AsyncSession = Depends(get_db)):
    original = await get_job(db, job_id)
    await require_project(db, original.project_id)
    if original.status not in {"failed", "interrupted"}:
        raise AppException(409, "Only failed or interrupted jobs may be retried", "CONFLICT")
    if original.kind in {"prompt", "image", "spec"}:
        require_api_key()
    # One explicit successor per attempt prevents double-clicks creating billed duplicates.
    job, created = await enqueue_job(
        db,
        project_id=original.project_id,
        kind=original.kind,
        payload=original.payload,
        resource_id=original.resource_id,
        idempotency_key=f"retry:{original.id}",
        retry_of=original.id,
    )
    if created and job.kind == "document":
        await db.execute(
            update(Document)
            .where(Document.id == job.resource_id)
            .values(job_id=job.id, parse_status="pending", parse_error=None)
        )
    elif created and job.kind == "image":
        await db.execute(
            update(Image)
            .where(Image.id == job.resource_id)
            .values(
                job_id=job.id,
                generation_status="pending",
                generation_error=None,
                retry_count=Image.retry_count + 1,
            )
        )
    await db.commit()
    await db.refresh(job)
    return job
