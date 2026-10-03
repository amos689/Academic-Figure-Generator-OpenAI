from sqlalchemy import JSON, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class FigureExport(Base, TimestampMixin):
    __tablename__ = "figure_exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id"), index=True)
    prompt_revision: Mapped[int] = mapped_column(Integer)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    format: Mapped[str] = mapped_column(String(20))
    figure_spec: Mapped[dict] = mapped_column(JSON)
    generation_metadata: Mapped[dict] = mapped_column(JSON)
    storage_path: Mapped[str | None] = mapped_column(String(1000))
    media_type: Mapped[str | None] = mapped_column(String(100))
    width_px: Mapped[int | None] = mapped_column(Integer)
    height_px: Mapped[int | None] = mapped_column(Integer)
    generation_status: Mapped[str] = mapped_column(String(20), default="pending")
    generation_error: Mapped[str | None] = mapped_column(Text)
