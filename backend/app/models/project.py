"""Project model — personal-use version (no user_id)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .document import Document
    from .image import Image
    from .prompt import Prompt


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    paper_field: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="e.g. 'computer vision', 'NLP'",
    )
    color_scheme: Mapped[str] = mapped_column(
        String(50),
        default="okabe-ito",
        nullable=False,
    )
    custom_colors: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    style_preset: Mapped[str] = mapped_column(
        String(20), default="classic", server_default="classic"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
        comment="active/archived/deleted",
    )

    # Relationships
    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="project", cascade="all, delete-orphan"
    )
    prompts: Mapped[list["Prompt"]] = relationship(
        "Prompt", back_populates="project", cascade="all, delete-orphan"
    )
    images: Mapped[list["Image"]] = relationship(
        "Image", back_populates="project", cascade="all, delete-orphan"
    )
