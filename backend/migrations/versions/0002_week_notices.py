"""add per-week student notices

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "week_notices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("week_id", sa.Integer(), sa.ForeignKey("weeks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("week_id"),
    )


def downgrade() -> None:
    op.drop_table("week_notices")
