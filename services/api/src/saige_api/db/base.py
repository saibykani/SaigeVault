"""Declarative base, naming conventions and shared column mixins.

Tenant isolation is enforced at three levels:
1. Every user-owned table carries a non-null, indexed `user_id`.
2. Child rows reference their parent through a composite foreign key on
   (parent_id, user_id), so the database rejects any row that points at
   another user's resource — even if application code has a bug.
3. Repository/service code always filters by the authenticated user_id.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    MetaData,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Fetch server-generated values (created_at/updated_at) via RETURNING on
    # INSERT and UPDATE, so attributes never expire into lazy loads, which are
    # illegal under asyncio.
    __mapper_args__ = {"eager_defaults": True}
    type_annotation_map = {
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
        uuid.UUID: UUID(as_uuid=True),
    }


def str_enum(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    """Store enums as VARCHAR + CHECK constraint.

    Native PostgreSQL ENUM types cannot have values removed and complicate
    migrations; a check constraint gives the same integrity guarantee.
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=max(len(member.value) for member in enum_cls),
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
        server_default=text("gen_random_uuid()"),
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class UserOwnedMixin:
    """Marks a table as tenant-scoped. See module docstring."""

    __tenant_scoped__ = True

    @declared_attr
    def user_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805
        return mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)


def tenant_key(table: str) -> UniqueConstraint:
    """Unique (id, user_id) so children can reference (parent_id, user_id)."""
    return UniqueConstraint("id", "user_id", name=f"uq_{table}_id_user_id")


def owned_fk(
    column: str,
    parent_table: str,
    *,
    ondelete: str = "CASCADE",
) -> ForeignKeyConstraint:
    """Composite FK guaranteeing the parent row belongs to the same user.

    With ondelete="SET NULL" only the nullable reference column is cleared
    (PostgreSQL 15+ column list syntax), never user_id.
    """
    set_null = ondelete.upper() == "SET NULL"
    return ForeignKeyConstraint(
        [column, "user_id"],
        [f"{parent_table}.id", f"{parent_table}.user_id"],
        ondelete=f"SET NULL ({column})" if set_null else ondelete,
    )
