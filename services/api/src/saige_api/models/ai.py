"""AI conversations, messages, agent runs and search history.

`ai_messages.trace` and the agent tables provide full AI traceability:
retrieval query, retrieved chunks, model, tool calls, latency and tokens.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from saige_api.db.base import (
    Base,
    CreatedAtMixin,
    SoftDeleteMixin,
    TimestampMixin,
    UserOwnedMixin,
    UUIDPrimaryKeyMixin,
    owned_fk,
    str_enum,
    tenant_key,
)
from saige_api.models.enums import (
    AgentRunStatus,
    AgentStepType,
    ConversationScope,
    MessageRole,
    MessageStatus,
    SearchMode,
    ToolCallStatus,
)


class AIConversation(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        tenant_key("ai_conversations"),
        Index("ix_ai_conversations_user_updated", "user_id", "updated_at"),
    )

    title: Mapped[str | None] = mapped_column(String(300))
    scope_type: Mapped[ConversationScope] = mapped_column(
        str_enum(ConversationScope, "conversation_scope"),
        nullable=False,
        default=ConversationScope.VAULT,
    )
    # IDs of files / folder / collection the conversation is restricted to.
    # Always re-validated against user_id at retrieval time.
    scope_ids: Mapped[list[Any]] = mapped_column(nullable=False, default=list)


class AIMessage(UUIDPrimaryKeyMixin, UserOwnedMixin, CreatedAtMixin, Base):
    __tablename__ = "ai_messages"
    __table_args__ = (
        tenant_key("ai_messages"),
        owned_fk("conversation_id", "ai_conversations"),
        owned_fk("parent_message_id", "ai_messages", ondelete="SET NULL"),
        Index("ix_ai_messages_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    # Set when a message is a regeneration of an earlier one.
    parent_message_id: Mapped[uuid.UUID | None] = mapped_column()
    role: Mapped[MessageRole] = mapped_column(str_enum(MessageRole, "message_role"), nullable=False)
    status: Mapped[MessageStatus] = mapped_column(
        str_enum(MessageStatus, "message_status"),
        nullable=False,
        default=MessageStatus.COMPLETED,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # [{"file_id", "chunk_id", "page", "quote", "kind": "source"|"inference"}]
    citations: Mapped[list[Any]] = mapped_column(nullable=False, default=list)
    # {"retrieval_query", "retrieved_chunk_ids", "reranked_chunk_ids", "filters", ...}
    trace: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    model_provider: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(128))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class AgentRun(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        tenant_key("agent_runs"),
        owned_fk("conversation_id", "ai_conversations", ondelete="SET NULL"),
        owned_fk("message_id", "ai_messages", ondelete="SET NULL"),
        Index("ix_agent_runs_user_created", "user_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID | None] = mapped_column()
    message_id: Mapped[uuid.UUID | None] = mapped_column()
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(
        str_enum(AgentRunStatus, "agent_run_status"),
        nullable=False,
        default=AgentRunStatus.RUNNING,
    )
    max_iterations: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    iterations: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    model_provider: Mapped[str | None] = mapped_column(String(64))
    model_name: Mapped[str | None] = mapped_column(String(128))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    final_output: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentStep(UUIDPrimaryKeyMixin, UserOwnedMixin, CreatedAtMixin, Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        tenant_key("agent_steps"),
        owned_fk("run_id", "agent_runs"),
        Index("uq_agent_steps_run_index", "run_id", "step_index", unique=True),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    step_index: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    step_type: Mapped[AgentStepType] = mapped_column(
        str_enum(AgentStepType, "agent_step_type"), nullable=False
    )
    content: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class AgentToolCall(UUIDPrimaryKeyMixin, UserOwnedMixin, TimestampMixin, Base):
    __tablename__ = "agent_tool_calls"
    __table_args__ = (
        owned_fk("run_id", "agent_runs"),
        owned_fk("step_id", "agent_steps", ondelete="SET NULL"),
        Index("ix_agent_tool_calls_run", "run_id"),
        Index("ix_agent_tool_calls_pending_confirmation", "user_id", "status"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    step_id: Mapped[uuid.UUID | None] = mapped_column()
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    # Bounded summary of the result (IDs, counts) — not raw document content.
    result_summary: Mapped[dict[str, Any] | None] = mapped_column()
    status: Mapped[ToolCallStatus] = mapped_column(
        str_enum(ToolCallStatus, "tool_call_status"),
        nullable=False,
        default=ToolCallStatus.PENDING,
    )
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    error_code: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class SearchHistory(UUIDPrimaryKeyMixin, UserOwnedMixin, CreatedAtMixin, Base):
    """User-visible recent searches. Subject to a retention policy and can be
    cleared by the user at any time."""

    __tablename__ = "search_history"
    __table_args__ = (Index("ix_search_history_user_created", "user_id", "created_at"),)

    query: Mapped[str] = mapped_column(String(1000), nullable=False)
    mode: Mapped[SearchMode] = mapped_column(str_enum(SearchMode, "search_mode"), nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(nullable=False, default=dict)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
