"""Prompt management service — personal-use version (no user_id)."""

from __future__ import annotations

import logging
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException, BadRequestException, NotFoundException
from app.models.document import Document
from app.models.project import Project
from app.models.prompt import Prompt
from app.models.prompt_revision import PromptRevision
from app.schemas.figure_spec import FigureSpec

logger = logging.getLogger(__name__)


class PromptService:
    """CRUD and status queries for AI-generated figure prompts."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_prompts_by_project(self, project_id: str) -> list[Prompt]:
        """Return all prompts belonging to a project, ordered by figure_number."""
        stmt = select(Prompt).where(Prompt.project_id == project_id).order_by(Prompt.figure_number)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_prompt(self, prompt_id: str) -> Prompt:
        """Fetch a single prompt by ID."""
        stmt = (
            select(Prompt).join(Project).where(Prompt.id == prompt_id, Project.status != "deleted")
        )
        result = await self.db.execute(stmt)
        prompt: Prompt | None = result.scalar_one_or_none()
        if prompt is None:
            raise NotFoundException(f"Prompt {prompt_id} not found")
        return prompt

    async def update_prompt(
        self,
        prompt_id: str,
        edited_prompt: str,
        *,
        expected_revision: int | None = None,
        figure_spec: dict | None = None,
        spec_supplied: bool = False,
    ) -> Prompt:
        prompt = await self.get_prompt(prompt_id)
        revision = expected_revision if expected_revision is not None else prompt.revision
        if revision != prompt.revision:
            raise AppException(
                409,
                "Prompt changed since it was loaded. Reload before saving.",
                "REVISION_CONFLICT",
            )
        text = edited_prompt.strip()
        if not text:
            raise BadRequestException("Prompt cannot be blank")
        spec = (
            figure_spec
            if spec_supplied
            else (prompt.figure_spec if text == prompt.active_prompt else None)
        )
        if spec is not None:
            validated = FigureSpec.model_validate(spec)
            if prompt.document_id:
                document = await self.db.get(Document, prompt.document_id)
                if document:
                    try:
                        validated.validate_source_references(
                            [
                                section.get("content", section.get("text", ""))
                                for section in document.sections or []
                            ]
                        )
                    except ValueError as exc:
                        raise BadRequestException(
                            "Figure source references do not match the document"
                        ) from exc
            spec = validated.model_dump()
        result = await self.db.execute(
            update(Prompt)
            .where(Prompt.id == prompt_id, Prompt.revision == revision)
            .values(edited_prompt=text, figure_spec=spec, revision=revision + 1)
        )
        if result.rowcount != 1:
            raise AppException(
                409, "Prompt changed during save. Reload before saving.", "REVISION_CONFLICT"
            )
        self.db.add(
            PromptRevision(
                prompt_id=prompt_id, revision=revision + 1, prompt_text=text, figure_spec=spec
            )
        )
        await self.db.flush()
        await self.db.refresh(prompt)
        logger.info("Prompt %s updated (edited_prompt length=%d)", prompt_id, len(edited_prompt))
        return prompt

    async def revisions(self, prompt_id: str) -> list[PromptRevision]:
        await self.get_prompt(prompt_id)
        return list(
            await self.db.scalars(
                select(PromptRevision)
                .where(PromptRevision.prompt_id == prompt_id)
                .order_by(PromptRevision.revision.desc())
            )
        )

    async def restore(
        self, prompt_id: str, revision: int, expected_revision: int | None = None
    ) -> Prompt:
        snapshot = (
            await self.db.scalars(
                select(PromptRevision).where(
                    PromptRevision.prompt_id == prompt_id, PromptRevision.revision == revision
                )
            )
        ).first()
        if snapshot is None:
            raise NotFoundException("Prompt revision not found")
        return await self.update_prompt(
            prompt_id,
            snapshot.prompt_text,
            expected_revision=expected_revision,
            figure_spec=snapshot.figure_spec,
            spec_supplied=True,
        )

    async def create_prompts_from_figures(
        self,
        project_id: str,
        document_id: str | None,
        figures: list[dict],
        claude_model: str | None = None,
        style_preset: str = "classic",
        generation_metadata: dict | None = None,
    ) -> list[Prompt]:
        """Create Prompt records from a list of generated figure dicts."""
        prompts: list[Prompt] = []
        await self.db.execute(
            update(Project).where(Project.id == project_id).values(updated_at=func.now())
        )
        offset = (
            await self.db.scalar(
                select(func.max(Prompt.figure_number)).where(Prompt.project_id == project_id)
            )
        ) or 0
        for fig in figures:
            prompt = Prompt(
                project_id=project_id,
                document_id=document_id,
                figure_number=offset + len(prompts) + 1,
                title=fig.get("title"),
                original_prompt=fig.get("prompt"),
                suggested_figure_type=fig.get("suggested_figure_type"),
                suggested_aspect_ratio=fig.get("suggested_aspect_ratio"),
                source_sections={
                    "titles": fig.get("source_section_titles", []),
                    "rationale": fig.get("rationale", ""),
                },
                claude_model=claude_model,
                generation_model=claude_model,
                style_preset=style_preset,
                figure_spec=fig.get("figure_spec"),
                generation_metadata=generation_metadata,
                generation_status="completed",
            )
            self.db.add(prompt)
            prompts.append(prompt)

        await self.db.flush()
        for p in prompts:
            await self.db.refresh(p)
            self.db.add(
                PromptRevision(
                    prompt_id=p.id,
                    revision=1,
                    prompt_text=p.original_prompt or "",
                    figure_spec=p.figure_spec,
                )
            )
        await self.db.flush()

        logger.info("Created %d prompts for project %s", len(prompts), project_id)
        return prompts
