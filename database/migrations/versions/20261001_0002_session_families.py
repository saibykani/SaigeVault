"""session families

Adds user_sessions.family_id: the stable session id shared by every refresh
rotation of one sign-in. Existing rows become single-generation families.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-01 16:18:18.143067+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0002'
down_revision: str | None = '0001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("user_sessions", sa.Column("family_id", sa.UUID(), nullable=True))
    op.execute("UPDATE user_sessions SET family_id = id WHERE family_id IS NULL")
    op.alter_column("user_sessions", "family_id", nullable=False)
    op.create_index(
        "ix_user_sessions_family", "user_sessions", ["user_id", "family_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_user_sessions_family", table_name="user_sessions")
    op.drop_column("user_sessions", "family_id")
