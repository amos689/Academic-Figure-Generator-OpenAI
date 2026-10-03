import pytest

from app.core.exceptions import BadRequestException
from app.models.color_scheme import ColorScheme
from app.services.style_service import (
    compose_image_prompt,
    generation_profile,
    resolve_palette,
    style_presets,
)


async def test_preset_display_name_and_saved_palette(sessions):
    async with sessions() as db:
        preset = await resolve_palette(db, "okabe-ito")
        by_label = await resolve_palette(db, "Okabe-Ito (Colorblind Safe, Recommended)")
        assert preset == by_label
        custom = {**preset, "primary": "#ABCDEF"}
        scheme = ColorScheme(name="Custom", type="custom", colors=custom)
        db.add(scheme)
        await db.flush()
        assert await resolve_palette(db, scheme.id) == custom
        with pytest.raises(BadRequestException):
            await resolve_palette(db, "unknown")
        with pytest.raises(BadRequestException):
            await resolve_palette(db, "custom", {"primary": "not-hex"})


def test_styles_reach_final_image_prompt():
    text = compose_image_prompt("A -> B", "pastel", {"primary": "#ABCDEF"})
    assert "pastel" in text and "#ABCDEF" in text and "A -> B" in text
    assert {style["id"] for style in style_presets()} == {"classic", "pastel"}
    assert generation_profile("draft")["image_quality"] == "medium"
