from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

from app.core.prompts.color_schemes import COLOR_SCHEME_DISPLAY_NAMES


class ColorValues(BaseModel):
    primary: str
    secondary: str
    tertiary: str
    text: str
    fill: str
    section_bg: str
    border: str
    arrow: str

    @field_validator(
        "primary", "secondary", "tertiary", "text", "fill", "section_bg", "border", "arrow"
    )
    @classmethod
    def validate_hex_color(cls, v: str) -> str:
        import re  # noqa: PLC0415

        if not re.match(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", v):
            raise ValueError(f"Invalid hex color: {v!r}. Must be #RGB or #RRGGBB format.")
        return v


class ColorSchemeCreate(BaseModel):
    name: str
    colors: ColorValues


class ColorSchemeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    type: str
    colors: dict
    is_default: bool
    created_at: datetime

    @computed_field
    @property
    def slug(self) -> str | None:
        if self.type != "preset":
            return None
        return next(
            (slug for slug, name in COLOR_SCHEME_DISPLAY_NAMES.items() if name == self.name), None
        )


class ColorSchemeUpdate(BaseModel):
    name: str | None = None
    colors: ColorValues | None = None
