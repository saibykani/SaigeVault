"""Static guarantees about multi-tenant isolation in the schema.

These tests fail the build if someone adds a user-owned table without a
user_id, or links two user-owned tables without including user_id in the
foreign key (which would allow cross-tenant references).
"""

from __future__ import annotations

from sqlalchemy import ForeignKeyConstraint, Table

from saige_api import models
from saige_api.db.base import Base

TABLES: dict[str, Table] = dict(Base.metadata.tables)
TENANT_TABLES = {
    name for name, table in TABLES.items() if name not in models.GLOBAL_OR_NULLABLE_USER_TABLES
}


def test_every_tenant_table_has_non_null_indexed_user_id() -> None:
    for name in TENANT_TABLES:
        table = TABLES[name]
        assert "user_id" in table.c, f"{name} is missing user_id"
        column = table.c.user_id
        assert not column.nullable, f"{name}.user_id must be NOT NULL"
        fk_targets = {fk.target_fullname for fk in column.foreign_keys}
        assert "users.id" in fk_targets, f"{name}.user_id must reference users.id"
        indexed = (
            any(idx.columns.keys()[:1] == ["user_id"] for idx in table.indexes) or column.index
        )
        primary_cols = table.primary_key.columns.keys()
        assert indexed or primary_cols[:1] == ["user_id"], f"{name}.user_id must be indexed"


def test_references_between_tenant_tables_include_user_id() -> None:
    violations: list[str] = []
    for name in TENANT_TABLES:
        for constraint in TABLES[name].constraints:
            if not isinstance(constraint, ForeignKeyConstraint):
                continue
            target = constraint.referred_table.name
            if target == "users" or target not in TENANT_TABLES:
                continue
            local_cols = set(constraint.column_keys)
            if "user_id" not in local_cols:
                violations.append(f"{name}({', '.join(sorted(local_cols))}) -> {target}")
    assert not violations, (
        "FKs between tenant tables must be composite with user_id:\n" + "\n".join(violations)
    )


def test_set_null_never_clears_user_id() -> None:
    for name in TENANT_TABLES:
        for constraint in TABLES[name].constraints:
            if isinstance(constraint, ForeignKeyConstraint) and constraint.ondelete:
                rule = constraint.ondelete.upper()
                if rule.startswith("SET NULL") and "user_id" in constraint.column_keys:
                    assert "(" in rule, f"{name}: composite SET NULL must name its column"


def test_expected_tables_exist() -> None:
    required = {
        "users", "user_sessions", "oauth_accounts", "storage_connections",
        "files", "file_versions", "folders", "file_metadata", "file_tags", "tags",
        "collections", "collection_files", "document_processing_jobs",
        "document_extracted_content", "document_entities", "document_summaries",
        "document_chunks", "embedding_records", "ai_conversations", "ai_messages",
        "agent_runs", "agent_steps", "agent_tool_calls", "search_history",
        "audit_logs", "security_events", "notifications", "sync_jobs", "sync_events",
        "api_keys", "feature_flags",
    }  # fmt: skip
    assert required <= set(TABLES), f"missing: {sorted(required - set(TABLES))}"


def test_secrets_are_never_stored_in_plaintext_columns() -> None:
    forbidden = {"access_token", "refresh_token", "password", "api_key", "client_secret"}
    for name, table in TABLES.items():
        assert not forbidden & set(table.c.keys()), f"{name} has a plaintext secret column"
