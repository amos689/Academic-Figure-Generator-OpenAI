from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import require_project
from app.core.exceptions import NotFoundException
from app.dependencies import get_db
from app.models import FigureExport
from app.schemas.figure_export import ExportRequest, ExportResponse
from app.schemas.job import JobResponse
from app.services.export_service import submit_export
from app.services.local_storage_service import LocalStorageService

router = APIRouter(tags=["Exports"])


@router.post("/prompts/{prompt_id}/exports", response_model=JobResponse, status_code=202)
async def create_export(prompt_id: str, data: ExportRequest, db: AsyncSession = Depends(get_db)):
    return await submit_export(db, prompt_id, data)


@router.get("/projects/{project_id}/exports", response_model=list[ExportResponse])
async def list_exports(project_id: str, db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id)
    return list(
        await db.scalars(
            select(FigureExport)
            .where(FigureExport.project_id == project_id)
            .order_by(FigureExport.created_at.desc(), FigureExport.id.desc())
        )
    )


@router.get("/exports/{export_id}/download")
async def download_export(export_id: str, db: AsyncSession = Depends(get_db)):
    record = await db.get(FigureExport, export_id)
    if record is None:
        raise NotFoundException("Export not found")
    await require_project(db, record.project_id)
    if record.generation_status != "completed" or not record.storage_path:
        raise NotFoundException("Export file is not available")
    path = LocalStorageService().get_file_path(record.storage_path)
    if not path.is_file():
        raise NotFoundException("Export file is missing")
    return FileResponse(
        path,
        media_type=record.media_type,
        filename=path.name,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Cache-Control": "private, no-store",
        },
    )
