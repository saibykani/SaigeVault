"""initial schema

Foundation schema for all Saige Vault domains. Enum columns are VARCHAR with
explicit CHECK constraints (see ADR-0004). Composite (id, user_id) foreign
keys enforce tenant isolation at the database level (see ADR-0005).

Revision ID: 0001
Revises: 
Create Date: 2026-10-01 11:36:52.223337+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('display_name', sa.String(length=200), nullable=True),
    sa.Column('avatar_url', sa.Text(), nullable=True),
    sa.Column('status', sa.Enum('active', 'disabled', name='user_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("status IN ('active', 'disabled')", name=op.f('ck_users_user_status')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_index(op.f('ix_users_deleted_at'), 'users', ['deleted_at'], unique=False)
    op.create_index('uq_users_email_lower', 'users', [sa.literal_column('lower(email)')], unique=True)
    op.create_table('ai_conversations',
    sa.Column('title', sa.String(length=300), nullable=True),
    sa.Column('scope_type', sa.Enum('file', 'files', 'folder', 'collection', 'vault', name='conversation_scope', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('scope_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("scope_type IN ('file', 'files', 'folder', 'collection', 'vault')", name=op.f('ck_ai_conversations_conversation_scope')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ai_conversations_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_conversations')),
    sa.UniqueConstraint('id', 'user_id', name='uq_ai_conversations_id_user_id')
    )
    op.create_index(op.f('ix_ai_conversations_deleted_at'), 'ai_conversations', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_ai_conversations_user_id'), 'ai_conversations', ['user_id'], unique=False)
    op.create_index('ix_ai_conversations_user_updated', 'ai_conversations', ['user_id', 'updated_at'], unique=False)
    op.create_table('api_keys',
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('prefix', sa.String(length=16), nullable=False),
    sa.Column('key_hash', sa.String(length=128), nullable=False),
    sa.Column('scopes', sa.ARRAY(sa.String(length=64)), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_api_keys_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_api_keys')),
    sa.UniqueConstraint('key_hash', name=op.f('uq_api_keys_key_hash'))
    )
    op.create_index(op.f('ix_api_keys_user_id'), 'api_keys', ['user_id'], unique=False)
    op.create_table('audit_logs',
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('actor_type', sa.Enum('user', 'system', 'agent', 'worker', name='audit_actor_type', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('action', sa.Enum('LOGIN', 'LOGOUT', 'FILE_UPLOAD', 'FILE_DOWNLOAD', 'FILE_DELETE', 'FILE_RESTORE', 'FILE_RENAME', 'FILE_MOVE', 'AI_QUERY', 'AI_DOCUMENT_ACCESS', 'AGENT_EXECUTION', 'OAUTH_CONNECT', 'OAUTH_DISCONNECT', 'SECURITY_EVENT', 'DATA_EXPORT', name='audit_action', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('resource_type', sa.String(length=64), nullable=True),
    sa.Column('resource_id', sa.UUID(), nullable=True),
    sa.Column('outcome', sa.String(length=16), nullable=False),
    sa.Column('request_id', sa.String(length=128), nullable=True),
    sa.Column('ip_address', postgresql.INET(), nullable=True),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("action IN ('LOGIN', 'LOGOUT', 'FILE_UPLOAD', 'FILE_DOWNLOAD', 'FILE_DELETE', 'FILE_RESTORE', 'FILE_RENAME', 'FILE_MOVE', 'AI_QUERY', 'AI_DOCUMENT_ACCESS', 'AGENT_EXECUTION', 'OAUTH_CONNECT', 'OAUTH_DISCONNECT', 'SECURITY_EVENT', 'DATA_EXPORT')", name=op.f('ck_audit_logs_audit_action')),
    sa.CheckConstraint("actor_type IN ('user', 'system', 'agent', 'worker')", name=op.f('ck_audit_logs_audit_actor_type')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_audit_logs_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_index('ix_audit_logs_action_created', 'audit_logs', ['action', 'created_at'], unique=False)
    op.create_index('ix_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'], unique=False)
    op.create_index('ix_audit_logs_user_created', 'audit_logs', ['user_id', 'created_at'], unique=False)
    op.create_table('collections',
    sa.Column('parent_collection_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('icon', sa.String(length=64), nullable=True),
    sa.Column('color', sa.String(length=16), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['parent_collection_id', 'user_id'], ['collections.id', 'collections.user_id'], name=op.f('fk_collections_parent_collection_id_collections'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_collections_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_collections')),
    sa.UniqueConstraint('id', 'user_id', name='uq_collections_id_user_id')
    )
    op.create_index(op.f('ix_collections_deleted_at'), 'collections', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_collections_user_id'), 'collections', ['user_id'], unique=False)
    op.create_index('uq_collections_user_parent_name', 'collections', ['user_id', sa.literal_column("coalesce(parent_collection_id, '00000000-0000-0000-0000-000000000000'::uuid)"), sa.literal_column('lower(name)')], unique=True, postgresql_where=sa.text('deleted_at IS NULL'))
    op.create_table('feature_flags',
    sa.Column('key', sa.String(length=128), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('rules', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_feature_flags_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_feature_flags')),
    sa.UniqueConstraint('key', 'user_id', name=op.f('uq_feature_flags_key_user_id'), postgresql_nulls_not_distinct=True)
    )
    op.create_index(op.f('ix_feature_flags_user_id'), 'feature_flags', ['user_id'], unique=False)
    op.create_table('notifications',
    sa.Column('type', sa.Enum('processing_complete', 'processing_failed', 'upload_complete', 'sync_complete', 'ai_indexing_complete', 'security_event', 'expiry_reminder', name='notification_type', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('body', sa.String(length=1000), nullable=True),
    sa.Column('resource_type', sa.String(length=64), nullable=True),
    sa.Column('resource_id', sa.UUID(), nullable=True),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('pushed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("type IN ('processing_complete', 'processing_failed', 'upload_complete', 'sync_complete', 'ai_indexing_complete', 'security_event', 'expiry_reminder')", name=op.f('ck_notifications_notification_type')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_notifications_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_notifications'))
    )
    op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    op.create_index('ix_notifications_user_unread', 'notifications', ['user_id', 'created_at'], unique=False, postgresql_where=sa.text('read_at IS NULL'))
    op.create_table('oauth_accounts',
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('provider_subject', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_oauth_accounts_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_oauth_accounts')),
    sa.UniqueConstraint('provider', 'provider_subject', name=op.f('uq_oauth_accounts_provider_provider_subject'))
    )
    op.create_index(op.f('ix_oauth_accounts_user_id'), 'oauth_accounts', ['user_id'], unique=False)
    op.create_table('search_history',
    sa.Column('query', sa.String(length=1000), nullable=False),
    sa.Column('mode', sa.Enum('exact', 'full_text', 'semantic', 'hybrid', name='search_mode', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('filters', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('result_count', sa.Integer(), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("mode IN ('exact', 'full_text', 'semantic', 'hybrid')", name=op.f('ck_search_history_search_mode')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_search_history_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_search_history'))
    )
    op.create_index('ix_search_history_user_created', 'search_history', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_search_history_user_id'), 'search_history', ['user_id'], unique=False)
    op.create_table('security_events',
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('severity', sa.Enum('info', 'low', 'medium', 'high', 'critical', name='security_severity', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('description', sa.String(length=1000), nullable=False),
    sa.Column('request_id', sa.String(length=128), nullable=True),
    sa.Column('ip_address', postgresql.INET(), nullable=True),
    sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("severity IN ('info', 'low', 'medium', 'high', 'critical')", name=op.f('ck_security_events_security_severity')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_security_events_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_security_events'))
    )
    op.create_index('ix_security_events_unresolved', 'security_events', ['severity'], unique=False, postgresql_where=sa.text('resolved_at IS NULL'))
    op.create_index('ix_security_events_user_created', 'security_events', ['user_id', 'created_at'], unique=False)
    op.create_table('storage_connections',
    sa.Column('provider', sa.Enum('google_drive', name='storage_provider_kind', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('provider_account_id', sa.String(length=255), nullable=False),
    sa.Column('account_email', sa.String(length=320), nullable=True),
    sa.Column('status', sa.Enum('active', 'needs_reauth', 'disconnected', 'error', name='storage_connection_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('encrypted_access_token', sa.LargeBinary(), nullable=True),
    sa.Column('encrypted_refresh_token', sa.LargeBinary(), nullable=True),
    sa.Column('token_key_version', sa.Integer(), nullable=False),
    sa.Column('access_token_expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('scopes', sa.ARRAY(sa.String(length=255)), nullable=False),
    sa.Column('root_folder_id', sa.String(length=255), nullable=True),
    sa.Column('changes_page_token', sa.String(length=255), nullable=True),
    sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('connected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('disconnected_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("provider IN ('google_drive')", name=op.f('ck_storage_connections_storage_provider_kind')),
    sa.CheckConstraint("status IN ('active', 'needs_reauth', 'disconnected', 'error')", name=op.f('ck_storage_connections_storage_connection_status')),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_storage_connections_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_storage_connections')),
    sa.UniqueConstraint('id', 'user_id', name='uq_storage_connections_id_user_id'),
    sa.UniqueConstraint('user_id', 'provider', 'provider_account_id', name=op.f('uq_storage_connections_user_id_provider_provider_account_id'))
    )
    op.create_index(op.f('ix_storage_connections_user_id'), 'storage_connections', ['user_id'], unique=False)
    op.create_table('tags',
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('normalized_name', sa.String(length=64), nullable=False),
    sa.Column('color', sa.String(length=16), nullable=True),
    sa.Column('is_sensitive', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_tags_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tags')),
    sa.UniqueConstraint('id', 'user_id', name='uq_tags_id_user_id'),
    sa.UniqueConstraint('user_id', 'normalized_name', name=op.f('uq_tags_user_id_normalized_name'))
    )
    op.create_index(op.f('ix_tags_user_id'), 'tags', ['user_id'], unique=False)
    op.create_table('user_sessions',
    sa.Column('refresh_token_hash', sa.String(length=128), nullable=False),
    sa.Column('platform', sa.Enum('web', 'android', 'ios', 'api', name='client_platform', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('device_name', sa.String(length=200), nullable=True),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('ip_address', postgresql.INET(), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_reason', sa.String(length=64), nullable=True),
    sa.Column('rotated_from_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("platform IN ('web', 'android', 'ios', 'api')", name=op.f('ck_user_sessions_client_platform')),
    sa.ForeignKeyConstraint(['rotated_from_id', 'user_id'], ['user_sessions.id', 'user_sessions.user_id'], name=op.f('fk_user_sessions_rotated_from_id_user_sessions'), ondelete='SET NULL (rotated_from_id)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_sessions')),
    sa.UniqueConstraint('id', 'user_id', name='uq_user_sessions_id_user_id'),
    sa.UniqueConstraint('refresh_token_hash', name=op.f('uq_user_sessions_refresh_token_hash'))
    )
    op.create_index('ix_user_sessions_active', 'user_sessions', ['user_id', 'revoked_at', 'expires_at'], unique=False)
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_table('ai_messages',
    sa.Column('conversation_id', sa.UUID(), nullable=False),
    sa.Column('parent_message_id', sa.UUID(), nullable=True),
    sa.Column('role', sa.Enum('user', 'assistant', 'system', 'tool', name='message_role', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('status', sa.Enum('pending', 'streaming', 'completed', 'failed', 'cancelled', name='message_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('citations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('trace', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('model_provider', sa.String(length=64), nullable=True),
    sa.Column('model_name', sa.String(length=128), nullable=True),
    sa.Column('model_version', sa.String(length=128), nullable=True),
    sa.Column('input_tokens', sa.Integer(), nullable=True),
    sa.Column('output_tokens', sa.Integer(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('user', 'assistant', 'system', 'tool')", name=op.f('ck_ai_messages_message_role')),
    sa.CheckConstraint("status IN ('pending', 'streaming', 'completed', 'failed', 'cancelled')", name=op.f('ck_ai_messages_message_status')),
    sa.ForeignKeyConstraint(['conversation_id', 'user_id'], ['ai_conversations.id', 'ai_conversations.user_id'], name=op.f('fk_ai_messages_conversation_id_ai_conversations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['parent_message_id', 'user_id'], ['ai_messages.id', 'ai_messages.user_id'], name=op.f('fk_ai_messages_parent_message_id_ai_messages'), ondelete='SET NULL (parent_message_id)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ai_messages_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_messages')),
    sa.UniqueConstraint('id', 'user_id', name='uq_ai_messages_id_user_id')
    )
    op.create_index('ix_ai_messages_conversation_created', 'ai_messages', ['conversation_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_ai_messages_user_id'), 'ai_messages', ['user_id'], unique=False)
    op.create_table('folders',
    sa.Column('storage_connection_id', sa.UUID(), nullable=False),
    sa.Column('storage_folder_id', sa.String(length=255), nullable=False),
    sa.Column('parent_folder_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=1024), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('parent_folder_id IS NULL OR parent_folder_id <> id', name=op.f('ck_folders_not_own_parent')),
    sa.ForeignKeyConstraint(['parent_folder_id', 'user_id'], ['folders.id', 'folders.user_id'], name=op.f('fk_folders_parent_folder_id_folders'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['storage_connection_id', 'user_id'], ['storage_connections.id', 'storage_connections.user_id'], name=op.f('fk_folders_storage_connection_id_storage_connections'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_folders_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_folders')),
    sa.UniqueConstraint('id', 'user_id', name='uq_folders_id_user_id'),
    sa.UniqueConstraint('storage_connection_id', 'storage_folder_id', name=op.f('uq_folders_storage_connection_id_storage_folder_id'))
    )
    op.create_index(op.f('ix_folders_deleted_at'), 'folders', ['deleted_at'], unique=False)
    op.create_index(op.f('ix_folders_user_id'), 'folders', ['user_id'], unique=False)
    op.create_index('ix_folders_user_parent', 'folders', ['user_id', 'parent_folder_id'], unique=False)
    op.create_table('sync_jobs',
    sa.Column('storage_connection_id', sa.UUID(), nullable=False),
    sa.Column('sync_type', sa.Enum('full', 'incremental', name='sync_type', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('status', sa.Enum('queued', 'running', 'succeeded', 'failed', name='sync_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('start_page_token', sa.String(length=255), nullable=True),
    sa.Column('end_page_token', sa.String(length=255), nullable=True),
    sa.Column('stats', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed')", name=op.f('ck_sync_jobs_sync_status')),
    sa.CheckConstraint("sync_type IN ('full', 'incremental')", name=op.f('ck_sync_jobs_sync_type')),
    sa.ForeignKeyConstraint(['storage_connection_id', 'user_id'], ['storage_connections.id', 'storage_connections.user_id'], name=op.f('fk_sync_jobs_storage_connection_id_storage_connections'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sync_jobs_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sync_jobs')),
    sa.UniqueConstraint('id', 'user_id', name='uq_sync_jobs_id_user_id')
    )
    op.create_index('ix_sync_jobs_connection_created', 'sync_jobs', ['storage_connection_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_sync_jobs_user_id'), 'sync_jobs', ['user_id'], unique=False)
    op.create_table('agent_runs',
    sa.Column('conversation_id', sa.UUID(), nullable=True),
    sa.Column('message_id', sa.UUID(), nullable=True),
    sa.Column('goal', sa.Text(), nullable=False),
    sa.Column('status', sa.Enum('running', 'awaiting_confirmation', 'succeeded', 'failed', 'timed_out', 'max_iterations', 'cancelled', name='agent_run_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('max_iterations', sa.SmallInteger(), nullable=False),
    sa.Column('iterations', sa.SmallInteger(), nullable=False),
    sa.Column('timeout_seconds', sa.Integer(), nullable=False),
    sa.Column('model_provider', sa.String(length=64), nullable=True),
    sa.Column('model_name', sa.String(length=128), nullable=True),
    sa.Column('input_tokens', sa.Integer(), nullable=True),
    sa.Column('output_tokens', sa.Integer(), nullable=True),
    sa.Column('final_output', sa.Text(), nullable=True),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('running', 'awaiting_confirmation', 'succeeded', 'failed', 'timed_out', 'max_iterations', 'cancelled')", name=op.f('ck_agent_runs_agent_run_status')),
    sa.ForeignKeyConstraint(['conversation_id', 'user_id'], ['ai_conversations.id', 'ai_conversations.user_id'], name=op.f('fk_agent_runs_conversation_id_ai_conversations'), ondelete='SET NULL (conversation_id)'),
    sa.ForeignKeyConstraint(['message_id', 'user_id'], ['ai_messages.id', 'ai_messages.user_id'], name=op.f('fk_agent_runs_message_id_ai_messages'), ondelete='SET NULL (message_id)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_agent_runs_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_runs')),
    sa.UniqueConstraint('id', 'user_id', name='uq_agent_runs_id_user_id')
    )
    op.create_index('ix_agent_runs_user_created', 'agent_runs', ['user_id', 'created_at'], unique=False)
    op.create_index(op.f('ix_agent_runs_user_id'), 'agent_runs', ['user_id'], unique=False)
    op.create_table('files',
    sa.Column('storage_provider', sa.Enum('google_drive', name='file_storage_provider', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('storage_connection_id', sa.UUID(), nullable=False),
    sa.Column('storage_file_id', sa.String(length=255), nullable=False),
    sa.Column('parent_folder_id', sa.UUID(), nullable=True),
    sa.Column('name', sa.String(length=1024), nullable=False),
    sa.Column('extension', sa.String(length=32), nullable=True),
    sa.Column('mime_type', sa.String(length=255), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('checksum', sa.String(length=64), nullable=True),
    sa.Column('storage_modified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('visibility', sa.Enum('private', name='file_visibility', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('is_starred', sa.Boolean(), nullable=False),
    sa.Column('is_favorite', sa.Boolean(), nullable=False),
    sa.Column('last_accessed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('access_count', sa.Integer(), nullable=False),
    sa.Column('document_type', sa.Enum('identity', 'education', 'employment', 'salary', 'banking', 'tax', 'insurance', 'finance', 'medical', 'legal', 'travel', 'certificate', 'resume', 'job_description', 'personal', 'work', 'project', 'image', 'other', 'unclassified', name='document_type', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('document_type_source', sa.Enum('system', 'ai', 'user', name='document_type_source', native_enum=False, create_constraint=False), nullable=True),
    sa.Column('document_type_confidence', sa.Float(), nullable=True),
    sa.Column('processing_status', sa.Enum('pending', 'queued', 'processing', 'ready', 'failed', 'unsupported', name='processing_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('ocr_status', sa.Enum('not_required', 'pending', 'processing', 'completed', 'failed', 'skipped_by_policy', name='ocr_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('extraction_status', sa.Enum('not_required', 'pending', 'processing', 'completed', 'failed', 'skipped_by_policy', name='extraction_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('embedding_status', sa.Enum('not_required', 'pending', 'processing', 'completed', 'failed', 'skipped_by_policy', name='embedding_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('is_ai_indexed', sa.Boolean(), nullable=False),
    sa.Column('page_count', sa.Integer(), nullable=True),
    sa.Column('thumbnail_storage_key', sa.String(length=512), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("document_type IN ('identity', 'education', 'employment', 'salary', 'banking', 'tax', 'insurance', 'finance', 'medical', 'legal', 'travel', 'certificate', 'resume', 'job_description', 'personal', 'work', 'project', 'image', 'other', 'unclassified')", name=op.f('ck_files_document_type')),
    sa.CheckConstraint("document_type_source IN ('system', 'ai', 'user')", name=op.f('ck_files_document_type_source')),
    sa.CheckConstraint("embedding_status IN ('not_required', 'pending', 'processing', 'completed', 'failed', 'skipped_by_policy')", name=op.f('ck_files_embedding_status')),
    sa.CheckConstraint("extraction_status IN ('not_required', 'pending', 'processing', 'completed', 'failed', 'skipped_by_policy')", name=op.f('ck_files_extraction_status')),
    sa.CheckConstraint("ocr_status IN ('not_required', 'pending', 'processing', 'completed', 'failed', 'skipped_by_policy')", name=op.f('ck_files_ocr_status')),
    sa.CheckConstraint("processing_status IN ('pending', 'queued', 'processing', 'ready', 'failed', 'unsupported')", name=op.f('ck_files_processing_status')),
    sa.CheckConstraint("storage_provider IN ('google_drive')", name=op.f('ck_files_file_storage_provider')),
    sa.CheckConstraint("visibility IN ('private')", name=op.f('ck_files_file_visibility')),
    sa.CheckConstraint('document_type_confidence IS NULL OR (document_type_confidence >= 0 AND document_type_confidence <= 1)', name=op.f('ck_files_confidence_range')),
    sa.CheckConstraint('size_bytes >= 0', name=op.f('ck_files_size_non_negative')),
    sa.ForeignKeyConstraint(['parent_folder_id', 'user_id'], ['folders.id', 'folders.user_id'], name=op.f('fk_files_parent_folder_id_folders'), ondelete='SET NULL (parent_folder_id)'),
    sa.ForeignKeyConstraint(['storage_connection_id', 'user_id'], ['storage_connections.id', 'storage_connections.user_id'], name=op.f('fk_files_storage_connection_id_storage_connections'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_files_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_files')),
    sa.UniqueConstraint('id', 'user_id', name='uq_files_id_user_id'),
    sa.UniqueConstraint('storage_connection_id', 'storage_file_id', name=op.f('uq_files_storage_connection_id_storage_file_id'))
    )
    op.create_index('ix_files_checksum', 'files', ['user_id', 'checksum'], unique=False)
    op.create_index(op.f('ix_files_deleted_at'), 'files', ['deleted_at'], unique=False)
    op.create_index('ix_files_user_document_type', 'files', ['user_id', 'document_type'], unique=False)
    op.create_index('ix_files_user_folder', 'files', ['user_id', 'parent_folder_id'], unique=False)
    op.create_index(op.f('ix_files_user_id'), 'files', ['user_id'], unique=False)
    op.create_index('ix_files_user_processing', 'files', ['user_id', 'processing_status'], unique=False)
    op.create_index('ix_files_user_starred', 'files', ['user_id'], unique=False, postgresql_where=sa.text('is_starred AND deleted_at IS NULL'))
    op.create_index('ix_files_user_updated', 'files', ['user_id', 'updated_at'], unique=False)
    op.create_table('agent_steps',
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('step_index', sa.SmallInteger(), nullable=False),
    sa.Column('step_type', sa.Enum('plan', 'tool_call', 'observation', 'final', name='agent_step_type', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("step_type IN ('plan', 'tool_call', 'observation', 'final')", name=op.f('ck_agent_steps_agent_step_type')),
    sa.ForeignKeyConstraint(['run_id', 'user_id'], ['agent_runs.id', 'agent_runs.user_id'], name=op.f('fk_agent_steps_run_id_agent_runs'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_agent_steps_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_steps')),
    sa.UniqueConstraint('id', 'user_id', name='uq_agent_steps_id_user_id')
    )
    op.create_index(op.f('ix_agent_steps_user_id'), 'agent_steps', ['user_id'], unique=False)
    op.create_index('uq_agent_steps_run_index', 'agent_steps', ['run_id', 'step_index'], unique=True)
    op.create_table('collection_files',
    sa.Column('collection_id', sa.UUID(), nullable=False),
    sa.Column('file_id', sa.UUID(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['collection_id', 'user_id'], ['collections.id', 'collections.user_id'], name=op.f('fk_collection_files_collection_id_collections'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['file_id', 'user_id'], ['files.id', 'files.user_id'], name=op.f('fk_collection_files_file_id_files'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_collection_files_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('collection_id', 'file_id', name=op.f('pk_collection_files'))
    )
    op.create_index('ix_collection_files_file', 'collection_files', ['file_id'], unique=False)
    op.create_index(op.f('ix_collection_files_user_id'), 'collection_files', ['user_id'], unique=False)
    op.create_table('document_entities',
    sa.Column('file_id', sa.UUID(), nullable=False),
    sa.Column('entity_type', sa.String(length=64), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('normalized_value', sa.Text(), nullable=True),
    sa.Column('page_number', sa.Integer(), nullable=True),
    sa.Column('char_start', sa.Integer(), nullable=True),
    sa.Column('char_end', sa.Integer(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('source', sa.Enum('system', 'ai', 'user', name='document_entity_source', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('is_confirmed', sa.Boolean(), nullable=False),
    sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('system', 'ai', 'user')", name=op.f('ck_document_entities_document_entity_source')),
    sa.ForeignKeyConstraint(['file_id', 'user_id'], ['files.id', 'files.user_id'], name=op.f('fk_document_entities_file_id_files'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_document_entities_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_entities')),
    sa.UniqueConstraint('id', 'user_id', name='uq_document_entities_id_user_id')
    )
    op.create_index(op.f('ix_document_entities_file_id'), 'document_entities', ['file_id'], unique=False)
    op.create_index('ix_document_entities_lookup', 'document_entities', ['user_id', 'entity_type', 'normalized_value'], unique=False)
    op.create_index(op.f('ix_document_entities_user_id'), 'document_entities', ['user_id'], unique=False)
    op.create_table('document_processing_jobs',
    sa.Column('file_id', sa.UUID(), nullable=True),
    sa.Column('job_type', sa.Enum('document_processing', 'ocr', 'embedding_generation', 'metadata_extraction', 'thumbnail_generation', 'drive_sync', 'file_integrity_check', 'ai_indexing', name='job_type', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('status', sa.Enum('queued', 'running', 'retry_scheduled', 'succeeded', 'failed', 'dead_lettered', 'cancelled', name='job_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('idempotency_key', sa.String(length=255), nullable=False),
    sa.Column('attempt', sa.SmallInteger(), nullable=False),
    sa.Column('max_attempts', sa.SmallInteger(), nullable=False),
    sa.Column('progress', sa.SmallInteger(), nullable=False),
    sa.Column('current_stage', sa.String(length=64), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('error_message', sa.String(length=1000), nullable=True),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("job_type IN ('document_processing', 'ocr', 'embedding_generation', 'metadata_extraction', 'thumbnail_generation', 'drive_sync', 'file_integrity_check', 'ai_indexing')", name=op.f('ck_document_processing_jobs_job_type')),
    sa.CheckConstraint("status IN ('queued', 'running', 'retry_scheduled', 'succeeded', 'failed', 'dead_lettered', 'cancelled')", name=op.f('ck_document_processing_jobs_job_status')),
    sa.CheckConstraint('attempt >= 0 AND attempt <= max_attempts', name=op.f('ck_document_processing_jobs_attempt_bounds')),
    sa.CheckConstraint('progress >= 0 AND progress <= 100', name=op.f('ck_document_processing_jobs_progress_range')),
    sa.ForeignKeyConstraint(['file_id', 'user_id'], ['files.id', 'files.user_id'], name=op.f('fk_document_processing_jobs_file_id_files'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_document_processing_jobs_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_processing_jobs')),
    sa.UniqueConstraint('id', 'user_id', name='uq_document_processing_jobs_id_user_id'),
    sa.UniqueConstraint('idempotency_key', name=op.f('uq_document_processing_jobs_idempotency_key'))
    )
    op.create_index(op.f('ix_document_processing_jobs_user_id'), 'document_processing_jobs', ['user_id'], unique=False)
    op.create_index('ix_jobs_status_scheduled', 'document_processing_jobs', ['status', 'next_attempt_at'], unique=False)
    op.create_index('ix_jobs_user_file', 'document_processing_jobs', ['user_id', 'file_id'], unique=False)
    op.create_table('file_metadata',
    sa.Column('file_id', sa.UUID(), nullable=False),
    sa.Column('key', sa.String(length=128), nullable=False),
    sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('source', sa.Enum('system', 'ai', 'user', name='file_metadata_source', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('source_page', sa.Integer(), nullable=True),
    sa.Column('is_confirmed', sa.Boolean(), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('system', 'ai', 'user')", name=op.f('ck_file_metadata_file_metadata_source')),
    sa.CheckConstraint('confidence IS NULL OR (confidence >= 0 AND confidence <= 1)', name=op.f('ck_file_metadata_confidence_range')),
    sa.ForeignKeyConstraint(['file_id', 'user_id'], ['files.id', 'files.user_id'], name=op.f('fk_file_metadata_file_id_files'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_file_metadata_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_file_metadata')),
    sa.UniqueConstraint('file_id', 'key', 'source', name=op.f('uq_file_metadata_file_id_key_source'))
    )
    op.create_index(op.f('ix_file_metadata_file_id'), 'file_metadata', ['file_id'], unique=False)
    op.create_index(op.f('ix_file_metadata_user_id'), 'file_metadata', ['user_id'], unique=False)
    op.create_index('ix_file_metadata_user_key', 'file_metadata', ['user_id', 'key'], unique=False)
    op.create_table('file_tags',
    sa.Column('file_id', sa.UUID(), nullable=False),
    sa.Column('tag_id', sa.UUID(), nullable=False),
    sa.Column('source', sa.Enum('system', 'ai', 'user', name='file_tag_source', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('status', sa.Enum('suggested', 'confirmed', 'rejected', name='file_tag_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('confidence', sa.Float(), nullable=True),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("source IN ('system', 'ai', 'user')", name=op.f('ck_file_tags_file_tag_source')),
    sa.CheckConstraint("status IN ('suggested', 'confirmed', 'rejected')", name=op.f('ck_file_tags_file_tag_status')),
    sa.ForeignKeyConstraint(['file_id', 'user_id'], ['files.id', 'files.user_id'], name=op.f('fk_file_tags_file_id_files'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tag_id', 'user_id'], ['tags.id', 'tags.user_id'], name=op.f('fk_file_tags_tag_id_tags'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_file_tags_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('file_id', 'tag_id', name=op.f('pk_file_tags'))
    )
    op.create_index('ix_file_tags_tag', 'file_tags', ['tag_id'], unique=False)
    op.create_index(op.f('ix_file_tags_user_id'), 'file_tags', ['user_id'], unique=False)
    op.create_table('file_versions',
    sa.Column('file_id', sa.UUID(), nullable=False),
    sa.Column('version_number', sa.Integer(), nullable=False),
    sa.Column('storage_revision_id', sa.String(length=255), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('checksum', sa.String(length=64), nullable=True),
    sa.Column('mime_type', sa.String(length=255), nullable=False),
    sa.Column('storage_modified_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['file_id', 'user_id'], ['files.id', 'files.user_id'], name=op.f('fk_file_versions_file_id_files'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_file_versions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_file_versions')),
    sa.UniqueConstraint('file_id', 'storage_revision_id', name=op.f('uq_file_versions_file_id_storage_revision_id')),
    sa.UniqueConstraint('file_id', 'version_number', name=op.f('uq_file_versions_file_id_version_number')),
    sa.UniqueConstraint('id', 'user_id', name='uq_file_versions_id_user_id')
    )
    op.create_index(op.f('ix_file_versions_file_id'), 'file_versions', ['file_id'], unique=False)
    op.create_index(op.f('ix_file_versions_user_id'), 'file_versions', ['user_id'], unique=False)
    op.create_table('sync_events',
    sa.Column('sync_job_id', sa.UUID(), nullable=False),
    sa.Column('change_type', sa.Enum('created', 'modified', 'moved', 'renamed', 'trashed', 'restored', 'deleted', name='sync_change_type', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('storage_file_id', sa.String(length=255), nullable=False),
    sa.Column('file_id', sa.UUID(), nullable=True),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("change_type IN ('created', 'modified', 'moved', 'renamed', 'trashed', 'restored', 'deleted')", name=op.f('ck_sync_events_sync_change_type')),
    sa.ForeignKeyConstraint(['file_id', 'user_id'], ['files.id', 'files.user_id'], name=op.f('fk_sync_events_file_id_files'), ondelete='SET NULL (file_id)'),
    sa.ForeignKeyConstraint(['sync_job_id', 'user_id'], ['sync_jobs.id', 'sync_jobs.user_id'], name=op.f('fk_sync_events_sync_job_id_sync_jobs'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_sync_events_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sync_events'))
    )
    op.create_index('ix_sync_events_job', 'sync_events', ['sync_job_id'], unique=False)
    op.create_index(op.f('ix_sync_events_user_id'), 'sync_events', ['user_id'], unique=False)
    op.create_table('agent_tool_calls',
    sa.Column('run_id', sa.UUID(), nullable=False),
    sa.Column('step_id', sa.UUID(), nullable=True),
    sa.Column('tool_name', sa.String(length=64), nullable=False),
    sa.Column('arguments', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('result_summary', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('status', sa.Enum('pending', 'awaiting_confirmation', 'approved', 'rejected', 'succeeded', 'failed', 'denied', name='tool_call_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('requires_confirmation', sa.Boolean(), nullable=False),
    sa.Column('confirmed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('attempt', sa.SmallInteger(), nullable=False),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'awaiting_confirmation', 'approved', 'rejected', 'succeeded', 'failed', 'denied')", name=op.f('ck_agent_tool_calls_tool_call_status')),
    sa.ForeignKeyConstraint(['run_id', 'user_id'], ['agent_runs.id', 'agent_runs.user_id'], name=op.f('fk_agent_tool_calls_run_id_agent_runs'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['step_id', 'user_id'], ['agent_steps.id', 'agent_steps.user_id'], name=op.f('fk_agent_tool_calls_step_id_agent_steps'), ondelete='SET NULL (step_id)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_agent_tool_calls_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_agent_tool_calls'))
    )
    op.create_index('ix_agent_tool_calls_pending_confirmation', 'agent_tool_calls', ['user_id', 'status'], unique=False)
    op.create_index('ix_agent_tool_calls_run', 'agent_tool_calls', ['run_id'], unique=False)
    op.create_index(op.f('ix_agent_tool_calls_user_id'), 'agent_tool_calls', ['user_id'], unique=False)
    op.create_table('document_chunks',
    sa.Column('file_id', sa.UUID(), nullable=False),
    sa.Column('file_version_id', sa.UUID(), nullable=True),
    sa.Column('strategy', sa.Enum('recursive', 'document_aware', 'page_aware', 'semantic', name='chunking_strategy', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('page_start', sa.Integer(), nullable=True),
    sa.Column('page_end', sa.Integer(), nullable=True),
    sa.Column('section', sa.String(length=512), nullable=True),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('token_count', sa.Integer(), nullable=True),
    sa.Column('char_start', sa.Integer(), nullable=True),
    sa.Column('char_end', sa.Integer(), nullable=True),
    sa.Column('attributes', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("strategy IN ('recursive', 'document_aware', 'page_aware', 'semantic')", name=op.f('ck_document_chunks_chunking_strategy')),
    sa.CheckConstraint('page_end IS NULL OR page_start IS NULL OR page_end >= page_start', name=op.f('ck_document_chunks_page_order')),
    sa.CheckConstraint('page_start IS NULL OR page_start >= 1', name=op.f('ck_document_chunks_page_start_positive')),
    sa.ForeignKeyConstraint(['file_id', 'user_id'], ['files.id', 'files.user_id'], name=op.f('fk_document_chunks_file_id_files'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['file_version_id', 'user_id'], ['file_versions.id', 'file_versions.user_id'], name=op.f('fk_document_chunks_file_version_id_file_versions'), ondelete='SET NULL (file_version_id)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_document_chunks_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_chunks')),
    sa.UniqueConstraint('file_id', 'file_version_id', 'strategy', 'chunk_index', name=op.f('uq_document_chunks_file_id_file_version_id_strategy_chunk_index')),
    sa.UniqueConstraint('id', 'user_id', name='uq_document_chunks_id_user_id')
    )
    op.create_index('ix_document_chunks_fts', 'document_chunks', [sa.literal_column("to_tsvector('simple', content)")], unique=False, postgresql_using='gin')
    op.create_index('ix_document_chunks_user_file', 'document_chunks', ['user_id', 'file_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_user_id'), 'document_chunks', ['user_id'], unique=False)
    op.create_table('document_extracted_content',
    sa.Column('file_id', sa.UUID(), nullable=False),
    sa.Column('file_version_id', sa.UUID(), nullable=True),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('method', sa.Enum('native_text', 'ocr', name='extraction_method', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('char_count', sa.Integer(), nullable=False),
    sa.Column('language', sa.String(length=16), nullable=True),
    sa.Column('ocr_confidence', sa.Float(), nullable=True),
    sa.Column('bounding_boxes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("method IN ('native_text', 'ocr')", name=op.f('ck_document_extracted_content_extraction_method')),
    sa.CheckConstraint('page_number >= 1', name=op.f('ck_document_extracted_content_page_positive')),
    sa.ForeignKeyConstraint(['file_id', 'user_id'], ['files.id', 'files.user_id'], name=op.f('fk_document_extracted_content_file_id_files'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['file_version_id', 'user_id'], ['file_versions.id', 'file_versions.user_id'], name=op.f('fk_document_extracted_content_file_version_id_file_versions'), ondelete='SET NULL (file_version_id)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_document_extracted_content_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_extracted_content')),
    sa.UniqueConstraint('file_id', 'file_version_id', 'page_number', 'method', name='uq_extracted_content_page')
    )
    op.create_index(op.f('ix_document_extracted_content_file_id'), 'document_extracted_content', ['file_id'], unique=False)
    op.create_index(op.f('ix_document_extracted_content_user_id'), 'document_extracted_content', ['user_id'], unique=False)
    op.create_table('document_summaries',
    sa.Column('file_id', sa.UUID(), nullable=False),
    sa.Column('file_version_id', sa.UUID(), nullable=True),
    sa.Column('summary_type', sa.Enum('short', 'detailed', 'key_points', 'action_items', 'important_dates', name='summary_type', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('source_chunk_ids', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('model_provider', sa.String(length=64), nullable=False),
    sa.Column('model_name', sa.String(length=128), nullable=False),
    sa.Column('prompt_version', sa.String(length=32), nullable=False),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("summary_type IN ('short', 'detailed', 'key_points', 'action_items', 'important_dates')", name=op.f('ck_document_summaries_summary_type')),
    sa.ForeignKeyConstraint(['file_id', 'user_id'], ['files.id', 'files.user_id'], name=op.f('fk_document_summaries_file_id_files'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['file_version_id', 'user_id'], ['file_versions.id', 'file_versions.user_id'], name=op.f('fk_document_summaries_file_version_id_file_versions'), ondelete='SET NULL (file_version_id)'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_document_summaries_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_document_summaries'))
    )
    op.create_index('ix_document_summaries_file_type', 'document_summaries', ['file_id', 'summary_type'], unique=False)
    op.create_index(op.f('ix_document_summaries_user_id'), 'document_summaries', ['user_id'], unique=False)
    op.create_table('embedding_records',
    sa.Column('chunk_id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=64), nullable=False),
    sa.Column('model', sa.String(length=128), nullable=False),
    sa.Column('dimensions', sa.Integer(), nullable=False),
    sa.Column('qdrant_collection', sa.String(length=128), nullable=False),
    sa.Column('qdrant_point_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'indexed', 'failed', 'stale', name='embedding_record_status', native_enum=False, create_constraint=False), nullable=False),
    sa.Column('indexed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'indexed', 'failed', 'stale')", name=op.f('ck_embedding_records_embedding_record_status')),
    sa.ForeignKeyConstraint(['chunk_id', 'user_id'], ['document_chunks.id', 'document_chunks.user_id'], name=op.f('fk_embedding_records_chunk_id_document_chunks'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_embedding_records_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_embedding_records')),
    sa.UniqueConstraint('chunk_id', 'provider', 'model', name=op.f('uq_embedding_records_chunk_id_provider_model')),
    sa.UniqueConstraint('qdrant_point_id', name=op.f('uq_embedding_records_qdrant_point_id'))
    )
    op.create_index(op.f('ix_embedding_records_chunk_id'), 'embedding_records', ['chunk_id'], unique=False)
    op.create_index('ix_embedding_records_status', 'embedding_records', ['user_id', 'status'], unique=False)
    op.create_index(op.f('ix_embedding_records_user_id'), 'embedding_records', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_embedding_records_user_id'), table_name='embedding_records')
    op.drop_index('ix_embedding_records_status', table_name='embedding_records')
    op.drop_index(op.f('ix_embedding_records_chunk_id'), table_name='embedding_records')
    op.drop_table('embedding_records')
    op.drop_index(op.f('ix_document_summaries_user_id'), table_name='document_summaries')
    op.drop_index('ix_document_summaries_file_type', table_name='document_summaries')
    op.drop_table('document_summaries')
    op.drop_index(op.f('ix_document_extracted_content_user_id'), table_name='document_extracted_content')
    op.drop_index(op.f('ix_document_extracted_content_file_id'), table_name='document_extracted_content')
    op.drop_table('document_extracted_content')
    op.drop_index(op.f('ix_document_chunks_user_id'), table_name='document_chunks')
    op.drop_index('ix_document_chunks_user_file', table_name='document_chunks')
    op.drop_index('ix_document_chunks_fts', table_name='document_chunks', postgresql_using='gin')
    op.drop_table('document_chunks')
    op.drop_index(op.f('ix_agent_tool_calls_user_id'), table_name='agent_tool_calls')
    op.drop_index('ix_agent_tool_calls_run', table_name='agent_tool_calls')
    op.drop_index('ix_agent_tool_calls_pending_confirmation', table_name='agent_tool_calls')
    op.drop_table('agent_tool_calls')
    op.drop_index(op.f('ix_sync_events_user_id'), table_name='sync_events')
    op.drop_index('ix_sync_events_job', table_name='sync_events')
    op.drop_table('sync_events')
    op.drop_index(op.f('ix_file_versions_user_id'), table_name='file_versions')
    op.drop_index(op.f('ix_file_versions_file_id'), table_name='file_versions')
    op.drop_table('file_versions')
    op.drop_index(op.f('ix_file_tags_user_id'), table_name='file_tags')
    op.drop_index('ix_file_tags_tag', table_name='file_tags')
    op.drop_table('file_tags')
    op.drop_index('ix_file_metadata_user_key', table_name='file_metadata')
    op.drop_index(op.f('ix_file_metadata_user_id'), table_name='file_metadata')
    op.drop_index(op.f('ix_file_metadata_file_id'), table_name='file_metadata')
    op.drop_table('file_metadata')
    op.drop_index('ix_jobs_user_file', table_name='document_processing_jobs')
    op.drop_index('ix_jobs_status_scheduled', table_name='document_processing_jobs')
    op.drop_index(op.f('ix_document_processing_jobs_user_id'), table_name='document_processing_jobs')
    op.drop_table('document_processing_jobs')
    op.drop_index(op.f('ix_document_entities_user_id'), table_name='document_entities')
    op.drop_index('ix_document_entities_lookup', table_name='document_entities')
    op.drop_index(op.f('ix_document_entities_file_id'), table_name='document_entities')
    op.drop_table('document_entities')
    op.drop_index(op.f('ix_collection_files_user_id'), table_name='collection_files')
    op.drop_index('ix_collection_files_file', table_name='collection_files')
    op.drop_table('collection_files')
    op.drop_index('uq_agent_steps_run_index', table_name='agent_steps')
    op.drop_index(op.f('ix_agent_steps_user_id'), table_name='agent_steps')
    op.drop_table('agent_steps')
    op.drop_index('ix_files_user_updated', table_name='files')
    op.drop_index('ix_files_user_starred', table_name='files', postgresql_where=sa.text('is_starred AND deleted_at IS NULL'))
    op.drop_index('ix_files_user_processing', table_name='files')
    op.drop_index(op.f('ix_files_user_id'), table_name='files')
    op.drop_index('ix_files_user_folder', table_name='files')
    op.drop_index('ix_files_user_document_type', table_name='files')
    op.drop_index(op.f('ix_files_deleted_at'), table_name='files')
    op.drop_index('ix_files_checksum', table_name='files')
    op.drop_table('files')
    op.drop_index(op.f('ix_agent_runs_user_id'), table_name='agent_runs')
    op.drop_index('ix_agent_runs_user_created', table_name='agent_runs')
    op.drop_table('agent_runs')
    op.drop_index(op.f('ix_sync_jobs_user_id'), table_name='sync_jobs')
    op.drop_index('ix_sync_jobs_connection_created', table_name='sync_jobs')
    op.drop_table('sync_jobs')
    op.drop_index('ix_folders_user_parent', table_name='folders')
    op.drop_index(op.f('ix_folders_user_id'), table_name='folders')
    op.drop_index(op.f('ix_folders_deleted_at'), table_name='folders')
    op.drop_table('folders')
    op.drop_index(op.f('ix_ai_messages_user_id'), table_name='ai_messages')
    op.drop_index('ix_ai_messages_conversation_created', table_name='ai_messages')
    op.drop_table('ai_messages')
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_index('ix_user_sessions_active', table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_index(op.f('ix_tags_user_id'), table_name='tags')
    op.drop_table('tags')
    op.drop_index(op.f('ix_storage_connections_user_id'), table_name='storage_connections')
    op.drop_table('storage_connections')
    op.drop_index('ix_security_events_user_created', table_name='security_events')
    op.drop_index('ix_security_events_unresolved', table_name='security_events', postgresql_where=sa.text('resolved_at IS NULL'))
    op.drop_table('security_events')
    op.drop_index(op.f('ix_search_history_user_id'), table_name='search_history')
    op.drop_index('ix_search_history_user_created', table_name='search_history')
    op.drop_table('search_history')
    op.drop_index(op.f('ix_oauth_accounts_user_id'), table_name='oauth_accounts')
    op.drop_table('oauth_accounts')
    op.drop_index('ix_notifications_user_unread', table_name='notifications', postgresql_where=sa.text('read_at IS NULL'))
    op.drop_index(op.f('ix_notifications_user_id'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_feature_flags_user_id'), table_name='feature_flags')
    op.drop_table('feature_flags')
    op.drop_index('uq_collections_user_parent_name', table_name='collections', postgresql_where=sa.text('deleted_at IS NULL'))
    op.drop_index(op.f('ix_collections_user_id'), table_name='collections')
    op.drop_index(op.f('ix_collections_deleted_at'), table_name='collections')
    op.drop_table('collections')
    op.drop_index('ix_audit_logs_user_created', table_name='audit_logs')
    op.drop_index('ix_audit_logs_resource', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action_created', table_name='audit_logs')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_api_keys_user_id'), table_name='api_keys')
    op.drop_table('api_keys')
    op.drop_index('ix_ai_conversations_user_updated', table_name='ai_conversations')
    op.drop_index(op.f('ix_ai_conversations_user_id'), table_name='ai_conversations')
    op.drop_index(op.f('ix_ai_conversations_deleted_at'), table_name='ai_conversations')
    op.drop_table('ai_conversations')
    op.drop_index('uq_users_email_lower', table_name='users')
    op.drop_index(op.f('ix_users_deleted_at'), table_name='users')
    op.drop_table('users')
