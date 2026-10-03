from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str
    kind: Literal["document", "prompt", "image", "spec", "export"]
    status: Literal["queued", "running", "succeeded", "failed", "interrupted", "cancelled"]
    stage: str
    resource_id: str | None
    result: dict | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    retry_of: str | None
