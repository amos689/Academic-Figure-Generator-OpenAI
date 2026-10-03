"""Color scheme model — personal-use version (no user_id)."""

from __future__ import annotations

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class ColorScheme(Base, TimestampMixin):
    __tablename__ = "color_schemes"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="preset/custom",
    )
    colors: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment=("Keys: primary, secondary, tertiary, text, fill, section_bg, border, arrow"),
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
