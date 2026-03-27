"""add avatar_mode to video_jobs

Revision ID: 20260327_0004
Revises: 20260327_0003
Create Date: 2026-03-27 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260327_0004"
down_revision: Union[str, None] = "20260327_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "video_jobs",
        sa.Column(
            "avatar_mode",
            sa.String(length=20),
            nullable=False,
            server_default="static",
        ),
    )


def downgrade() -> None:
    op.drop_column("video_jobs", "avatar_mode")
