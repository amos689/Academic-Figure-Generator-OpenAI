"""Track editable export snapshots independently from mutable prompts."""

import sqlalchemy as sa
from alembic import op

revision = "0004_exports"
down_revision = "0003_provenance"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "figure_exports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("prompt_id", sa.String(36), sa.ForeignKey("prompts.id"), nullable=False),
        sa.Column("prompt_revision", sa.Integer, nullable=False),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("figure_spec", sa.JSON, nullable=False),
        sa.Column("generation_metadata", sa.JSON, nullable=False),
        sa.Column("storage_path", sa.String(1000)),
        sa.Column("media_type", sa.String(100)),
        sa.Column("width_px", sa.Integer),
        sa.Column("height_px", sa.Integer),
        sa.Column("generation_status", sa.String(20), nullable=False),
        sa.Column("generation_error", sa.Text),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_figure_exports_project_id", "figure_exports", ["project_id"])
    op.create_index("ix_figure_exports_prompt_id", "figure_exports", ["prompt_id"])


def downgrade():
    raise RuntimeError("Restore a pre-upgrade backup to downgrade")
