from datetime import datetime

from app.core.prompts.color_schemes import COLOR_SCHEME_DISPLAY_NAMES, OKABE_ITO
from app.schemas.color_scheme import ColorSchemeResponse


def test_preset_identity_does_not_depend_on_database_uuid():
    for slug, name in COLOR_SCHEME_DISPLAY_NAMES.items():
        response = ColorSchemeResponse(
            id="random-database-uuid", name=name, type="preset", colors=OKABE_ITO,
            is_default=False, created_at=datetime(2026, 1, 1),
        )
        assert response.model_dump()["slug"] == slug


def test_custom_palette_cannot_impersonate_a_preset_by_name():
    response = ColorSchemeResponse(
        id="custom", name=COLOR_SCHEME_DISPLAY_NAMES["okabe-ito"], type="custom",
        colors=OKABE_ITO, is_default=False, created_at=datetime(2026, 1, 1),
    )
    assert response.slug is None
