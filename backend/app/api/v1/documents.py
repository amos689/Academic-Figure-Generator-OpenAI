"""Document storage and durable, nonblocking text extraction."""

import asyncio
from uuid import uuid4

from fastapi import APIRouter, Depends, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import require_project
from app.core.exceptions import NotFoundException
from app.dependencies import get_db
from app.models.document import Document
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService
from app.services.job_service import enqueue_job
from app.services.local_storage_service import LocalStorageService
from app.services.upload_service import display_filename, read_upload

router = APIRouter(tags=["Documents"])


@router.get("/projects/{project_id}/documents", response_model=list[DocumentResponse])
async def list_project_documents(project_id: str, db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id)
    return list(
        await db.scalars(
            select(Document)
            .where(Document.project_id == project_id)
            .order_by(Document.created_at.desc())
        )
    )


@router.post("/projects/{project_id}/documents", response_model=DocumentResponse, status_code=201)
async def upload_document(project_id: str, file: UploadFile, db: AsyncSession = Depends(get_db)):
    await require_project(db, project_id)
    contents = await read_upload(file)
    filename = display_filename(file.filename)
    file_type = await asyncio.to_thread(
        DocumentService().validate_file, filename, contents, len(contents)
    )
    document_id = str(uuid4())
    storage = LocalStorageService()
    path = storage.save_upload(f"{project_id}/{document_id}.{file_type}", contents)
    try:
        document = Document(
            id=document_id,
            project_id=project_id,
            original_filename=filename,
            file_type=file_type,
            file_size_bytes=len(contents),
            storage_path=path,
            parse_status="pending",
        )
        db.add(document)
        job, _ = await enqueue_job(
            db,
            project_id=project_id,
            kind="document",
            payload={"document_id": document_id},
            resource_id=document_id,
        )
        document.job_id = job.id
        await db.commit()
        await db.refresh(document)
    except Exception:
        await db.rollback()
        storage.delete_file(path)
        raise
    return document


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    document = await db.get(Document, document_id)
    if document is None:
        raise NotFoundException("Document not found")
    await require_project(db, document.project_id)
    return document
