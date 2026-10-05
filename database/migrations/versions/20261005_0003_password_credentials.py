"""password credentials

Adds email + password sign-in with an optional TOTP second factor, and
users.email_verified_at (set when Google proves ownership of the address).
Existing Google users are marked verified.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05 10:00:00.000000+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.execute(
        "UPDATE users SET email_verified_at = COALESCE(last_login_at, created_at) "
        "WHERE id IN (SELECT user_id FROM oauth_accounts WHERE provider = 'google')"
    )
    op.create_table(
        "password_credentials",
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "password_changed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("encrypted_totp_secret", sa.LargeBinary(), nullable=True),
        sa.Column("totp_key_version", sa.Integer(), nullable=True),
        sa.Column("totp_enabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("totp_last_used_step", sa.BigInteger(), nullable=True),
        sa.Column("recovery_code_hashes", sa.ARRAY(sa.String(length=64)), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_password_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_password_credentials")),
        sa.UniqueConstraint("id", "user_id", name="uq_password_credentials_id_user_id"),
        sa.UniqueConstraint("user_id", name=op.f("uq_password_credentials_user_id")),
    )
    op.create_index(
        op.f("ix_password_credentials_user_id"), "password_credentials", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_password_credentials_user_id"), table_name="password_credentials")
    op.drop_table("password_credentials")
    op.drop_column("users", "email_verified_at")
