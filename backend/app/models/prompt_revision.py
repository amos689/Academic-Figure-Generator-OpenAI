from sqlalchemy import JSON, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, new_uuid


class PromptRevision(Base, TimestampMixin):
    __tablename__ = "prompt_revisions"
    __table_args__ = (UniqueConstraint("prompt_id", "revision", name="uq_prompt_revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    prompt_id: Mapped[str] = mapped_column(ForeignKey("prompts.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer)
    prompt_text: Mapped[str] = mapped_column(Text)
    figure_spec: Mapped[dict | None] = mapped_column(JSON)
