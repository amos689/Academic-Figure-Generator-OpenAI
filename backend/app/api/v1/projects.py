"""Project CRUD endpoints — personal-use (no auth)."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.dependencies import get_db
from app.models.document import Document
from app.models.image import Image
from app.models.project import Project
from app.models.prompt import Prompt
from app.schemas.common import MessageResponse
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["Projects"])


async def _get_project(project_id: str, db: AsyncSession) -> Project:
    result = await db.execute(select(Project).where(Project.id == project_id))
    project: Project | None = result.scalar_one_or_none()
    if project is None or project.status == "deleted":
        raise NotFoundException("Project not found")
    return project


async def _enrich_response(project: Project, db: AsyncSession) -> ProjectResponse:
    doc_count = (
        await db.execute(
            select(func.count()).select_from(Document).where(Document.project_id == project.id)
        )
    ).scalar_one()
    prompt_count = (
        await db.execute(
            select(func.count()).select_from(Prompt).where(Prompt.project_id == project.id)
        )
    ).scalar_one()
    image_count = (
        await db.execute(
            select(func.count()).select_from(Image).where(Image.project_id == project.id)
        )
    ).scalar_one()

    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        paper_field=project.paper_field,
        color_scheme=project.color_scheme,
        custom_colors=project.custom_colors,
        style_preset=project.style_preset,
        status=project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
        document_count=doc_count,
        prompt_count=prompt_count,
        image_count=image_count,
    )


@router.post("/", response_model=ProjectResponse, status_code=201)
async def create_project(
    data: ProjectCreate,
    db: AsyncSession = Depends(get_db),
):
    project = Project(
        name=data.name,
        description=data.description,
        paper_field=data.paper_field,
        color_scheme=data.color_scheme,
        custom_colors=data.custom_colors,
        style_preset=data.style_preset,
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)
    return await _enrich_response(project, db)


@router.get("/", response_model=ProjectListResponse)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    base_query = select(Project).where(Project.status != "deleted")
    if status is not None:
        base_query = base_query.where(Project.status == status)

    total: int = (
        await db.execute(select(func.count()).select_from(base_query.subquery()))
    ).scalar_one()
    offset = (page - 1) * page_size
    rows = (
        (
            await db.execute(
                base_query.order_by(Project.created_at.desc()).offset(offset).limit(page_size)
            )
        )
        .scalars()
        .all()
    )

    items = [await _enrich_response(p, db) for p in rows]
    return ProjectListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    return await _enrich_response(project, db)


@router.put("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    if data.name is not None:
        project.name = data.name
    if data.description is not None:
        project.description = data.description
    if data.paper_field is not None:
        project.paper_field = data.paper_field
    if data.color_scheme is not None:
        project.color_scheme = data.color_scheme
    if data.custom_colors is not None:
        project.custom_colors = data.custom_colors
    if data.status is not None:
        project.status = data.status
    if data.style_preset is not None:
        project.style_preset = data.style_preset

    db.add(project)
    await db.flush()
    await db.refresh(project)
    return await _enrich_response(project, db)


@router.delete("/{project_id}", response_model=MessageResponse)
async def delete_project(
    project_id: str,
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, db)
    project.status = "deleted"
    db.add(project)
    await db.flush()
    return MessageResponse(message="Project deleted")
