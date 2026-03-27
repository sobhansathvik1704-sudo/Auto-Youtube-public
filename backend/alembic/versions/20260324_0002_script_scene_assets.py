"""script scene assets

Revision ID: 20260324_0002
Revises: 20260324_0001
Create Date: 2026-03-24 00:10:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260324_0002"
down_revision: Union[str, None] = "20260324_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("video_jobs", sa.Column("render_storage_key", sa.Text(), nullable=True))
    op.add_column("video_jobs", sa.Column("metadata_json", sa.Text(), nullable=True))

    op.create_table(
        "scripts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("video_job_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("hook", sa.Text(), nullable=False),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("outro", sa.Text(), nullable=True),
        sa.Column("full_text", sa.Text(), nullable=False),
        sa.Column("structured_json", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["video_job_id"], ["video_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scripts_video_job_id"), "scripts", ["video_job_id"], unique=False)

    op.create_table(
        "scenes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("video_job_id", sa.String(length=36), nullable=False),
        sa.Column("scene_index", sa.Integer(), nullable=False),
        sa.Column("scene_type", sa.String(length=100), nullable=False),
        sa.Column("narration_text", sa.Text(), nullable=False),
        sa.Column("on_screen_text", sa.Text(), nullable=True),
        sa.Column("visual_prompt", sa.Text(), nullable=True),
        sa.Column("asset_config_json", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["video_job_id"], ["video_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_scenes_video_job_id"), "scenes", ["video_job_id"], unique=False)

    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("video_job_id", sa.String(length=36), nullable=False),
        sa.Column("scene_id", sa.String(length=36), nullable=True),
        sa.Column("asset_type", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["scene_id"], ["scenes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["video_job_id"], ["video_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_assets_video_job_id"), "assets", ["video_job_id"], unique=False)
    op.create_index(op.f("ix_assets_scene_id"), "assets", ["scene_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_assets_scene_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_video_job_id"), table_name="assets")
    op.drop_table("assets")

    op.drop_index(op.f("ix_scenes_video_job_id"), table_name="scenes")
    op.drop_table("scenes")

    op.drop_index(op.f("ix_scripts_video_job_id"), table_name="scripts")
    op.drop_table("scripts")

    op.drop_column("video_jobs", "metadata_json")
    op.drop_column("video_jobs", "render_storage_key")