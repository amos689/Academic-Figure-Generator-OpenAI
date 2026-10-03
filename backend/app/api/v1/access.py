from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.models import Project


async def require_project(db: AsyncSession, project_id: str) -> Project:
    project = await db.get(Project, project_id)
    if project is None or project.status == "deleted":
        raise NotFoundException("Project not found")
    return project


def require_api_key() -> None:
    if not get_settings().OPENAI_API_KEY:
        raise BadRequestException(
            "OPENAI_API_KEY is not configured. "
            "Set it in the system environment or a local .env file."
        )
