"""OpenAI Responses API integration for academic figure prompt generation."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.core.exceptions import ExternalAPIException

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SKILL_PATH = _PROJECT_ROOT / "academic-figure-prompt" / "SKILL.md"


def _load_skill_content() -> str:
    """Load the repository skill as reusable prompt-generation instructions."""
    if not _SKILL_PATH.exists():
        logger.warning("SKILL.md not found at %s", _SKILL_PATH)
        return ""
    return _SKILL_PATH.read_text(encoding="utf-8")


class OpenAIPromptService:
    """Generate academic figure prompts via OpenAI Responses API."""

    RESPONSE_SCHEMA: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "figures": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "figure_number": {"type": "integer", "minimum": 1},
                        "title": {"type": "string", "minLength": 1},
                        "suggested_figure_type": {"type": "string", "minLength": 1},
                        "suggested_aspect_ratio": {"type": "string", "minLength": 3},
                        "prompt": {"type": "string", "minLength": 500},
                        "source_section_titles": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "rationale": {"type": "string"},
                    },
                    "required": [
                        "figure_number",
                        "title",
                        "suggested_figure_type",
                        "suggested_aspect_ratio",
                        "prompt",
                        "source_section_titles",
                        "rationale",
                    ],
                },
            }
        },
        "required": ["figures"],
    }

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.OPENAI_API_KEY
        self.api_base = settings.OPENAI_API_BASE
        self.model = settings.OPENAI_TEXT_MODEL
        self.reasoning_effort = settings.OPENAI_TEXT_REASONING_EFFORT
        self.max_output_tokens = settings.OPENAI_TEXT_MAX_OUTPUT_TOKENS
        self.skill_content = _load_skill_content()

        if not self.api_key:
            raise ExternalAPIException(
                "OpenAI",
                "OPENAI_API_KEY is not configured. Set it in your system environment, "
                "a local .env file, or backend/app/config.py.",
            )

    async def generate_figure_prompts(
        self,
        sections: list[dict],
        color_scheme: dict,
        paper_field: str | None = None,
        figure_types: list[str] | None = None,
        user_request: str | None = None,
        max_figures: int | None = None,
        template_mode: bool = False,
    ) -> dict:
        """Call OpenAI and return normalized figure prompt records."""
        user_message = self._build_user_message(
            sections=sections,
            color_scheme=color_scheme,
            paper_field=paper_field,
            figure_types=figure_types,
            user_request=user_request,
            max_figures=max_figures,
            template_mode=template_mode,
        )

        start_time = time.monotonic()
        try:
            response_text = await asyncio.to_thread(self._create_response, user_message)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("OpenAI prompt generation failed after %d ms: %s", duration_ms, exc)
            raise ExternalAPIException("OpenAI", f"Prompt generation failed: {exc}") from exc

        duration_ms = int((time.monotonic() - start_time) * 1000)
        figures = self._parse_figures_response(response_text)
        logger.info(
            "OpenAI prompt generation completed in %d ms: %d figures",
            duration_ms,
            len(figures),
        )

        return {"figures": figures, "duration_ms": duration_ms, "model": self.model}

    def _create_response(self, user_message: str) -> str:
        """Synchronous SDK call split out for easy testing/mocking."""
        from openai import OpenAI  # noqa: PLC0415

        client = OpenAI(api_key=self.api_key, base_url=self.api_base)
        response = client.responses.create(
            model=self.model,
            instructions=self._build_instructions(),
            input=user_message,
            reasoning={"effort": self.reasoning_effort},
            max_output_tokens=self.max_output_tokens,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "academic_figure_prompt_batch",
                    "schema": self.RESPONSE_SCHEMA,
                    "strict": True,
                }
            },
        )
        return self._extract_response_text(response)

    def _build_instructions(self) -> str:
        skill = self.skill_content.strip()
        if not skill:
            skill = "Generate detailed English prompts for top-tier academic figures."

        return "\n\n".join(
            [
                skill,
                "You are running inside the Academic Figure Generator backend.",
                "Return only data that satisfies the requested JSON schema.",
                "Every generated image prompt must be in English and extremely detailed.",
                "Do not ask follow-up questions; use the supplied color palette and request.",
            ]
        )

    def _build_user_message(
        self,
        sections: list[dict],
        color_scheme: dict,
        paper_field: str | None,
        figure_types: list[str] | None = None,
        user_request: str | None = None,
        max_figures: int | None = None,
        template_mode: bool = False,
    ) -> str:
        parts: list[str] = []

        if paper_field:
            parts.append(f"Academic field: {paper_field}")

        parts.append("Color palette to use:")
        parts.append(json.dumps(color_scheme, ensure_ascii=False, indent=2))
        parts.append("")

        if figure_types:
            parts.append("Preferred figure types:")
            parts.extend(f"- {figure_type}" for figure_type in figure_types)
            parts.append("")

        if user_request and user_request.strip():
            parts.append("User request, highest priority:")
            parts.append(user_request.strip())
            parts.append("")

        if template_mode:
            parts.append(
                "Template mode: create a clean structural base figure with no readable text "
                "inside boxes, arrows, badges, or labels. Use unlabeled shapes and visual "
                "placeholders so the user can add text later."
            )
            parts.append("")

        if max_figures is not None and max_figures > 0:
            parts.append(f"Generate at most {max_figures} figure prompt(s).")
            parts.append("")

        parts.append("--- PAPER SECTIONS ---")
        for i, section in enumerate(sections, 1):
            title = str(section.get("title", f"Section {i}"))
            content = str(section.get("content", section.get("text", "")))
            max_section_chars = 8000
            if len(content) > max_section_chars:
                content = content[:max_section_chars] + "\n[... section truncated ...]"

            parts.append(f"## Section {i}: {title}")
            parts.append(content)
            parts.append("")

        parts.append("--- END OF PAPER ---")
        parts.append(
            "Generate the figure prompts that best match the paper content. "
            "Each prompt should be at least 500 words, information-dense, and precise."
        )
        return "\n".join(parts)

    @classmethod
    def _extract_response_text(cls, response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if output_text:
            return str(output_text)

        if isinstance(response, dict):
            output_text = response.get("output_text")
            if output_text:
                return str(output_text)
            output = response.get("output", [])
        else:
            output = getattr(response, "output", [])

        text_parts: list[str] = []
        for item in output or []:
            if isinstance(item, dict):
                content_items = item.get("content", [])
            else:
                content_items = getattr(item, "content", [])
            for content in content_items or []:
                if isinstance(content, dict):
                    text = content.get("text")
                else:
                    text = getattr(content, "text", None)
                if text:
                    text_parts.append(str(text))

        return "\n".join(text_parts)

    def _parse_figures_response(self, text: str) -> list[dict]:
        if not text or not text.strip():
            raise ExternalAPIException("OpenAI", "Empty prompt generation response")

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ExternalAPIException("OpenAI", f"Invalid JSON response: {exc}") from exc

        figures = parsed.get("figures") if isinstance(parsed, dict) else parsed
        if not isinstance(figures, list):
            raise ExternalAPIException("OpenAI", "Response JSON does not contain a figures list")

        return self._validate_figures(figures)

    @staticmethod
    def _validate_figures(figures: list) -> list[dict]:
        valid: list[dict] = []
        for i, figure in enumerate(figures):
            if not isinstance(figure, dict):
                continue

            prompt = str(figure.get("prompt", "")).strip()
            if not prompt:
                continue

            valid.append(
                {
                    "figure_number": int(figure.get("figure_number") or i + 1),
                    "title": figure.get("title") or f"Figure {i + 1}",
                    "suggested_figure_type": figure.get("suggested_figure_type")
                    or figure.get("figure_type")
                    or "diagram",
                    "suggested_aspect_ratio": figure.get("suggested_aspect_ratio") or "16:9",
                    "prompt": prompt,
                    "source_section_titles": figure.get("source_section_titles") or [],
                    "rationale": figure.get("rationale") or "",
                }
            )

        if not valid:
            raise ExternalAPIException("OpenAI", "No valid figure prompts returned")
        return valid
