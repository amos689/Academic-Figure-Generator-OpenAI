"""Document model — personal-use version (no user_id)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from .project import Project


class Document(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=new_uuid,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_filename: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    file_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="pdf/docx/txt",
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
    )
    full_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    sections: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Parsed chapter structure",
    )
    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    parse_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        comment="pending/parsing/completed/failed",
    )
    parse_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    ocr_markdown: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Raw OCR Markdown output",
    )
    job_id: Mapped[str | None] = mapped_column(String(36))

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="documents")
