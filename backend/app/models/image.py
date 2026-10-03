"""Image model — personal-use version (no user_id)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .project import Project
    from .prompt import Prompt


class Image(Base, TimestampMixin):
    __tablename__ = "images"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )
    prompt_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("prompts.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    resolution: Mapped[str] = mapped_column(
        String(10),
        default="2K",
        nullable=False,
    )
    aspect_ratio: Mapped[str] = mapped_column(
        String(10),
        default="16:9",
        nullable=False,
    )
    color_scheme: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    custom_colors: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    reference_image_path: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )
    edit_instruction: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    storage_path: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )
    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
    )
    width_px: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    height_px: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    generation_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
    )
    generation_duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    generation_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Failure reason for generation.",
    )
    final_prompt_sent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    job_id: Mapped[str | None] = mapped_column(String(36))
    parent_image_id: Mapped[str | None] = mapped_column(String(36))
    prompt_revision: Mapped[int | None] = mapped_column(Integer)
    generation_model: Mapped[str | None] = mapped_column(String(100))
    quality: Mapped[str | None] = mapped_column(String(20))
    style_preset: Mapped[str | None] = mapped_column(String(20))
    generation_metadata: Mapped[dict | None] = mapped_column(JSON)
    mask_image_path: Mapped[str | None] = mapped_column(String(1000))
    favorite: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
    selected: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    # Relationships
    prompt: Mapped[Optional["Prompt"]] = relationship("Prompt", back_populates="images")
    project: Mapped["Project"] = relationship("Project", back_populates="images")
