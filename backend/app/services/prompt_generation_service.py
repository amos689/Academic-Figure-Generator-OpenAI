from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.access import require_api_key, require_project
from app.config import get_settings
from app.core.exceptions import BadRequestException
from app.models import Document, Job
from app.schemas.prompt import PromptGenerateRequest
from app.services.context_service import ContextService
from app.services.openai_prompt_service import OpenAIPromptService
from app.services.prompt_service import PromptService
from app.services.style_service import generation_profile, resolve_palette


async def prepare_prompt_job(
    db: AsyncSession, project_id: str, data: PromptGenerateRequest
) -> dict:
    require_api_key()
    project = await require_project(db, project_id)
    query = select(Document).where(
        Document.project_id == project_id, Document.parse_status == "completed"
    )
    if data.document_id:
        query = query.where(Document.id == data.document_id)
    document = (
        await db.scalars(query.order_by(Document.created_at.desc(), Document.id).limit(1))
    ).first()
    if document is None:
        raise BadRequestException("Choose a successfully parsed document in this project")
    try:
        context = ContextService().select(document.sections or [], data.section_indices)
    except ValueError as exc:
        raise BadRequestException("Invalid section selection for the chosen document") from exc
    if not context["sections"]:
        raise BadRequestException("Select at least one non-empty source section")
    palette = await resolve_palette(
        db,
        data.color_scheme or project.color_scheme,
        data.custom_colors if data.custom_colors is not None else project.custom_colors,
    )
    profile = generation_profile(data.profile)
    settings = get_settings()
    return {
        "document_id": document.id,
        "section_indices": data.section_indices,
        "palette": palette,
        "color_scheme": data.color_scheme or project.color_scheme,
        "paper_field": project.paper_field,
        "figure_types": data.figure_types,
        "user_request": data.user_request,
        "max_figures": data.max_figures,
        "template_mode": data.template_mode,
        "style_preset": data.style_preset or project.style_preset,
        "profile": data.profile,
        "model": settings.OPENAI_TEXT_MODEL,
        "reasoning_effort": profile["text_reasoning_effort"],
        "max_output_tokens": settings.OPENAI_TEXT_MAX_OUTPUT_TOKENS,
    }


async def generate_prompt_job(job: Job, db: AsyncSession) -> dict:
    await require_project(db, job.project_id)
    payload = job.payload
    document = await db.get(Document, payload["document_id"])
    if document is None or document.parse_status != "completed":
        raise BadRequestException("Source document is no longer available")
    service = OpenAIPromptService(
        style_preset=payload["style_preset"],
        profile=payload["profile"],
        model=payload["model"],
        reasoning_effort=payload["reasoning_effort"],
        max_output_tokens=payload["max_output_tokens"],
    )
    response = await service.generate_figure_prompts(
        sections=document.sections or [],
        section_indices=payload["section_indices"],
        color_scheme=payload["palette"],
        paper_field=payload["paper_field"],
        figure_types=payload["figure_types"],
        user_request=payload["user_request"],
        max_figures=payload["max_figures"],
        template_mode=payload["template_mode"],
    )
    metadata = {
        **response.get("generation_metadata", {}),
        "palette": payload["palette"],
        "color_scheme": payload["color_scheme"],
        "job_id": job.id,
    }
    prompts = await PromptService(db).create_prompts_from_figures(
        job.project_id,
        document.id,
        response["figures"],
        response.get("model", payload["model"]),
        style_preset=payload["style_preset"],
        generation_metadata=metadata,
    )
    return {
        "prompt_ids": [prompt.id for prompt in prompts],
        "usage": metadata.get("usage"),
        "duration_ms": response.get("duration_ms"),
    }
