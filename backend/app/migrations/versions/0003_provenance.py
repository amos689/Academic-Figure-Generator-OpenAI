"""Preserve prompt history and image provenance without inventing old settings."""

import uuid

import sqlalchemy as sa
from alembic import op

revision = "0003_provenance"
down_revision = "0002_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "projects",
        sa.Column("style_preset", sa.String(20), server_default="classic", nullable=False),
    )
    op.add_column("documents", sa.Column("job_id", sa.String(36)))
    for column in [
        sa.Column("generation_model", sa.String(100)),
        sa.Column("revision", sa.Integer, server_default="1", nullable=False),
        sa.Column("figure_spec", sa.JSON),
        sa.Column("style_preset", sa.String(20)),
        sa.Column("generation_metadata", sa.JSON),
    ]:
        op.add_column("prompts", column)
    op.execute("UPDATE prompts SET generation_model = claude_model")
    for column in [
        sa.Column("job_id", sa.String(36)),
        sa.Column("parent_image_id", sa.String(36)),
        sa.Column("prompt_revision", sa.Integer),
        sa.Column("generation_model", sa.String(100)),
        sa.Column("quality", sa.String(20)),
        sa.Column("style_preset", sa.String(20)),
        sa.Column("generation_metadata", sa.JSON),
        sa.Column("mask_image_path", sa.String(1000)),
        sa.Column("favorite", sa.Boolean, server_default="0", nullable=False),
        sa.Column("selected", sa.Boolean, server_default="0", nullable=False),
    ]:
        op.add_column("images", column)
    revisions = op.create_table(
        "prompt_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "prompt_id",
            sa.String(36),
            sa.ForeignKey("prompts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("revision", sa.Integer, nullable=False),
        sa.Column("prompt_text", sa.Text, nullable=False),
        sa.Column("figure_spec", sa.JSON),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("prompt_id", "revision", name="uq_prompt_revision"),
    )
    op.create_index("ix_prompt_revisions_prompt_id", "prompt_revisions", ["prompt_id"])
    rows = (
        op.get_bind()
        .execute(sa.text("SELECT id, original_prompt, edited_prompt FROM prompts"))
        .mappings()
    )
    for row in rows:
        op.get_bind().execute(
            revisions.insert().values(
                id=str(uuid.uuid4()),
                prompt_id=row["id"],
                revision=1,
                prompt_text=row["edited_prompt"] or row["original_prompt"] or "",
            )
        )


def downgrade():
    raise RuntimeError("Restore a pre-upgrade backup to downgrade")
