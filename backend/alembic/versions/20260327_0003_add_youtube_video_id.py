"""add youtube_video_id to video_jobs

Revision ID: 20260327_0003
Revises: 20260324_0002
Create Date: 2026-03-27 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260327_0003"
down_revision: Union[str, None] = "20260324_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("video_jobs", sa.Column("youtube_video_id", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("video_jobs", "youtube_video_id")
