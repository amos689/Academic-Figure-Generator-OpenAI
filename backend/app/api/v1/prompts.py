"""Durable prompt generation and conflict-aware revision history."""

import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import require_project
from app.core.exceptions import AppException
from app.dependencies import get_db
from app.models import Job, Prompt
from app.schemas.job import JobResponse
from app.schemas.prompt import (
    PromptGenerateRequest,
    PromptResponse,
    PromptRestore,
    PromptRevisionResponse,
    PromptStatusResponse,
    PromptUpdate,
)
from app.services.job_service import enqueue_job
from app.services.prompt_generation_service import prepare_prompt_job
from app.services.prompt_service import PromptService
from app.services.spec_generation_service import submit_spec

router = APIRouter(tags=["Prompts"])


async def _submit(project_id: str, data: PromptGenerateRequest, db: AsyncSession) -> Job:
    payload = await prepare_prompt_job(db, project_id, data)
    job, _ = await enqueue_job(
        db,
        project_id=project_id,
        kind="prompt",
        payload=payload,
        idempotency_key=data.idempotency_key,
    )
    await db.commit()
    await db.refresh(job)
    return job


@router.post("/projects/{project_id}/prompt-jobs", response_model=JobResponse, status_code=202)
async def queue_prompts(
    project_id: str, data: PromptGenerateRequest, db: AsyncSession = Depends(get_db)
):
    return await _submit(project_id, data, db)


@router.post(
    "/projects/{project_id}/prompts/generate", response_model=list[PromptResponse], status_code=201
)
async def generate_prompts(
    project_id: str, data: PromptGenerateRequest, db: AsyncSession = Depends(get_db)
):
    """Legacy waiting endpoint, using the same durable queue and concurrency limit."""
    job = await _submit(project_id, data, db)
    while job.status in {"queued", "running"}:
        await asyncio.sleep(0.5)
        await db.refresh(job)
    if job.status != "succeeded":
        raise AppException(502, job.error or f"Prompt generation {job.status}", "GENERATION_FAILED")
    ids = (job.result or {}).get("prompt_ids", [])
    return list(
        await db.scalars(select(Prompt).where(Prompt.id.in_(ids)).order_by(Prompt.figure_number))
    )


@router.get("/projects/{project_id}/prompts", response_model=list[PromptResponse])
async def list_project_prompts(project_id: str, db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id)
    return await PromptService(db).get_prompts_by_project(project_id)


@router.get("/prompts/{prompt_id}", response_model=PromptResponse)
async def get_prompt(prompt_id: str, db: AsyncSession = Depends(get_db)):
    return await PromptService(db).get_prompt(prompt_id)


@router.put("/prompts/{prompt_id}", response_model=PromptResponse)
async def update_prompt(prompt_id: str, data: PromptUpdate, db: AsyncSession = Depends(get_db)):
    return await PromptService(db).update_prompt(
        prompt_id,
        data.edited_prompt,
        expected_revision=data.expected_revision,
        figure_spec=data.figure_spec.model_dump() if data.figure_spec else None,
        spec_supplied="figure_spec" in data.model_fields_set,
    )


@router.get("/prompts/{prompt_id}/revisions", response_model=list[PromptRevisionResponse])
async def list_revisions(prompt_id: str, db: AsyncSession = Depends(get_db)):
    return await PromptService(db).revisions(prompt_id)


@router.post("/prompts/{prompt_id}/spec-jobs", response_model=JobResponse, status_code=202)
async def queue_spec(prompt_id: str, db: AsyncSession = Depends(get_db)):
    return await submit_spec(db, prompt_id)


@router.post("/prompts/{prompt_id}/restore", response_model=PromptResponse)
async def restore_prompt(prompt_id: str, data: PromptRestore, db: AsyncSession = Depends(get_db)):
    return await PromptService(db).restore(prompt_id, data.revision, data.expected_revision)


@router.get("/prompts/{prompt_id}/status", response_model=PromptStatusResponse)
async def get_prompt_status(prompt_id: str, db: AsyncSession = Depends(get_db)):
    return await PromptService(db).get_prompt(prompt_id)
