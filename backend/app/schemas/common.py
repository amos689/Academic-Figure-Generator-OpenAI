from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error_code: str
    detail: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
