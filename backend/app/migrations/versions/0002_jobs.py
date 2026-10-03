"""Persist queued jobs and explicit retry attempts."""

import sqlalchemy as sa
from alembic import op

revision = "0002_jobs"
down_revision = "0001_legacy"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(36)),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), unique=True),
        sa.Column("result", sa.JSON),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.DateTime),
        sa.Column("finished_at", sa.DateTime),
        sa.Column("retry_of", sa.String(36), sa.ForeignKey("jobs.id")),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_jobs_project_id", "jobs", ["project_id"])
    op.create_index("ix_jobs_status", "jobs", ["status"])


def downgrade():
    raise RuntimeError("Restore a pre-upgrade backup to downgrade")
