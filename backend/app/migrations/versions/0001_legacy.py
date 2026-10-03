"""Freeze the original local schema; adopt existing databases without rebuilding them."""

import sqlalchemy as sa
from alembic import op

revision = "0001_legacy"
down_revision = None
branch_labels = None
depends_on = None


def _id():
    return sa.Column("id", sa.String(36), primary_key=True)


def _timestamps():
    return [
        sa.Column(name, sa.DateTime, nullable=False, server_default=sa.func.now())
        for name in ("created_at", "updated_at")
    ]


def _project_id():
    return sa.Column(
        "project_id",
        sa.String(36),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade():
    existing = set(sa.inspect(op.get_bind()).get_table_names())
    tables = {
        "projects": [
            _id(),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text),
            sa.Column("paper_field", sa.String(100)),
            sa.Column("color_scheme", sa.String(50), nullable=False),
            sa.Column("custom_colors", sa.JSON),
            sa.Column("status", sa.String(20), nullable=False),
        ],
        "documents": [
            _id(),
            _project_id(),
            sa.Column("original_filename", sa.String(500), nullable=False),
            sa.Column("file_type", sa.String(20), nullable=False),
            sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
            sa.Column("storage_path", sa.String(1000), nullable=False),
            sa.Column("full_text", sa.Text),
            sa.Column("sections", sa.JSON),
            sa.Column("page_count", sa.Integer),
            sa.Column("parse_status", sa.String(20), nullable=False),
            sa.Column("parse_error", sa.Text),
            sa.Column("ocr_markdown", sa.Text),
        ],
        "prompts": [
            _id(),
            _project_id(),
            sa.Column(
                "document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="SET NULL")
            ),
            sa.Column("figure_number", sa.Integer, nullable=False),
            sa.Column("title", sa.String(300)),
            sa.Column("original_prompt", sa.Text),
            sa.Column("edited_prompt", sa.Text),
            sa.Column("suggested_figure_type", sa.String(50)),
            sa.Column("suggested_aspect_ratio", sa.String(10)),
            sa.Column("source_sections", sa.JSON),
            sa.Column("claude_model", sa.String(50)),
            sa.Column("generation_status", sa.String(20), nullable=False),
        ],
        "images": [
            _id(),
            _project_id(),
            sa.Column("prompt_id", sa.String(36), sa.ForeignKey("prompts.id", ondelete="SET NULL")),
            sa.Column("resolution", sa.String(10), nullable=False),
            sa.Column("aspect_ratio", sa.String(10), nullable=False),
            sa.Column("color_scheme", sa.String(50)),
            sa.Column("custom_colors", sa.JSON),
            sa.Column("reference_image_path", sa.String(1000)),
            sa.Column("edit_instruction", sa.Text),
            sa.Column("storage_path", sa.String(1000)),
            sa.Column("file_size_bytes", sa.BigInteger),
            sa.Column("width_px", sa.Integer),
            sa.Column("height_px", sa.Integer),
            sa.Column("generation_status", sa.String(20), nullable=False),
            sa.Column("generation_duration_ms", sa.Integer),
            sa.Column("generation_error", sa.Text),
            sa.Column("final_prompt_sent", sa.Text),
            sa.Column("retry_count", sa.Integer, nullable=False),
        ],
        "color_schemes": [
            _id(),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("type", sa.String(20), nullable=False),
            sa.Column("colors", sa.JSON, nullable=False),
            sa.Column("is_default", sa.Boolean, nullable=False),
        ],
    }
    for name, columns in tables.items():
        columns += _timestamps()
        if name not in existing:
            op.create_table(name, *columns)
        else:
            actual = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(name)}
            if not {column.name for column in columns} <= actual:
                raise RuntimeError(
                    f"Legacy schema for {name} is incomplete; restore or repair before upgrading"
                )


def downgrade():
    raise RuntimeError("Destructive downgrade is not supported; restore a database backup instead")
