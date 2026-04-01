"""add subcategory to video_jobs

Revision ID: 20260401_0005
Revises: 20260327_0004
Create Date: 2026-04-01 00:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260401_0005"
down_revision: Union[str, None] = "20260327_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "video_jobs",
        sa.Column(
            "subcategory",
            sa.String(length=100),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("video_jobs", "subcategory")
