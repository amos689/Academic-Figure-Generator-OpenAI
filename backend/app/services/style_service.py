"""Shared style and palette resolution for prompts, raster images, and exports."""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import BadRequestException
from app.core.prompts.color_schemes import COLOR_SCHEME_DISPLAY_NAMES, PRESET_COLOR_SCHEMES
from app.models.color_scheme import ColorScheme
from app.schemas.color_scheme import ColorValues

STYLES = {
    "classic": {
        "id": "classic",
        "name": "Classic",
        "description": "Precise publication diagrams",
        "instructions": (
            "Use a clean white canvas, restrained flat fills, precise alignment, crisp vector-like "
            "lines, readable dark labels, and clear directional connectors. Encode distinctions "
            "with labels and shapes as well as color."
        ),
    },
    "pastel": {
        "id": "pastel",
        "name": "Pastel",
        "description": "Airy modern ML diagrams",
        "instructions": (
            "Use a pure white canvas with airy modern ML paper composition, soft pastel region "
            "fills, compact rounded panels, subtle shadows, small token squares, readable rounded "
            "sans-serif labels, and clear connector arrows. "
            "Keep rich scientific content organized, "
            "not decorative or vague. Use palette accents consistently across modules."
        ),
    },
}


def style_presets() -> list[dict]:
    return [
        {key: value for key, value in style.items() if key != "instructions"}
        for style in STYLES.values()
    ]


def generation_profile(profile: str) -> dict:
    settings = get_settings()
    if profile not in {"quality", "draft"}:
        raise BadRequestException("Unknown generation profile")
    return {
        "id": profile,
        "name": "Quality" if profile == "quality" else "Draft",
        "text_reasoning_effort": settings.OPENAI_TEXT_REASONING_EFFORT
        if profile == "quality"
        else "medium",
        "image_quality": settings.OPENAI_IMAGE_QUALITY if profile == "quality" else "medium",
    }


async def resolve_palette(db: AsyncSession, name: str, custom: dict | None = None) -> dict:
    if custom and set(ColorValues.model_fields) <= custom.keys():
        try:
            return ColorValues.model_validate(custom).model_dump()
        except ValueError as exc:
            raise BadRequestException(
                "Palette must contain valid hex colors for every role"
            ) from exc
    normalized = name.replace("_", "-")
    base = PRESET_COLOR_SCHEMES.get(normalized)
    if base is None:
        display_slug = next(
            (slug for slug, label in COLOR_SCHEME_DISPLAY_NAMES.items() if label == name), None
        )
        base = PRESET_COLOR_SCHEMES.get(display_slug) if display_slug else None
    if base is None and name != "custom":
        scheme = (await db.scalars(select(ColorScheme).where(ColorScheme.id == name))).first()
        if scheme is None:
            raise BadRequestException(
                "Unknown color scheme. Choose a preset or saved custom palette."
            )
        base = scheme.colors
    if base is None:
        base = PRESET_COLOR_SCHEMES["okabe-ito"]
    try:
        return ColorValues.model_validate({**base, **(custom or {})}).model_dump()
    except ValueError as exc:
        raise BadRequestException("Palette must contain valid hex colors for every role") from exc


def compose_image_prompt(prompt: str, style_preset: str, palette: dict) -> str:
    if style_preset not in STYLES:
        raise BadRequestException("Unknown figure style")
    return (
        f"{prompt.strip()}\n\nRendering direction:\n{STYLES[style_preset]['instructions']}\n"
        f"Exact semantic palette: {json.dumps(palette, sort_keys=True)}\n"
        "Preserve scientific labels, numbers, and connectivity. "
        "Do not invent results or decorative text."
    )
