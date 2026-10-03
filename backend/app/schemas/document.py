from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SectionInfo(BaseModel):
    index: int
    title: str
    level: int
    content: str
    page_start: int | None = None
    page_end: int | None = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    page_count: int | None
    sections: list[dict] | None
    parse_status: str
    parse_error: str | None
    ocr_markdown: str | None = None
    created_at: datetime
    job_id: str | None = None
