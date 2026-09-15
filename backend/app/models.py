import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    false,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, now


def identifier() -> str:
    return uuid.uuid4().hex


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(Text)
    recovery_hash: Mapped[str | None] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    name: Mapped[str] = mapped_column(String(80))
    public_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    collaboration_mode: Mapped[str] = mapped_column(
        String(20), default="maintainers", server_default="maintainers"
    )


class SiteSettings(Base):
    __tablename__ = "site_settings"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    home_workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"))


class TransferReceipt(Base):
    __tablename__ = "transfer_receipts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    package_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        CheckConstraint("role IN ('member','maintainer','admin')"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    role: Mapped[str] = mapped_column(String(20), default="member")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    active_workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"))


class AccountReset(Base):
    __tablename__ = "account_resets"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)


class Invitation(Base):
    __tablename__ = "invitations"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    role: Mapped[str] = mapped_column(String(20), default="member")
    kind: Mapped[str] = mapped_column(String(20), default="invite")
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)


SCOPE_CHECK = "(scope = 'team' AND workspace_id IS NOT NULL AND owner_user_id IS NULL) OR (scope = 'personal' AND owner_user_id IS NOT NULL AND workspace_id IS NULL)"


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (CheckConstraint(SCOPE_CHECK, name="category_scope"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    scope: Mapped[str] = mapped_column(String(20))
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"))
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"))
    name: Mapped[str] = mapped_column(String(80))
    visibility: Mapped[str] = mapped_column(String(20), default="workspace")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)


class CategoryGrant(Base):
    __tablename__ = "category_grants"
    category_id: Mapped[str] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    can_read: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)


class Environment(Base):
    __tablename__ = "environments"
    __table_args__ = (
        CheckConstraint(SCOPE_CHECK, name="environment_scope"),
        UniqueConstraint("workspace_id", "key"),
        UniqueConstraint("owner_user_id", "key"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    scope: Mapped[str] = mapped_column(String(20), default="team")
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"))
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    key: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(20), default="custom")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint(SCOPE_CHECK, name="resource_scope"),
        CheckConstraint("type IN ('system','bookmark')"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    scope: Mapped[str] = mapped_column(String(20), index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"))
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    name: Mapped[str] = mapped_column(String(120))
    aliases: Mapped[str] = mapped_column(String(240), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[list] = mapped_column(JSON, default=list)
    icon: Mapped[str] = mapped_column(String(30), default="globe")
    maintainer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    search_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class ResourceGrant(Base):
    __tablename__ = "resource_grants"
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    can_read: Mapped[bool] = mapped_column(Boolean, default=False)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage_accounts: Mapped[bool] = mapped_column(Boolean, default=False)


class Endpoint(Base):
    __tablename__ = "endpoints"
    __table_args__ = (UniqueConstraint("resource_id", "environment_key"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), index=True)
    environment_id: Mapped[str | None] = mapped_column(ForeignKey("environments.id"))
    environment_key: Mapped[str] = mapped_column(String(32))
    url: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class Credential(Base):
    __tablename__ = "credentials"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("endpoints.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    username_ciphertext: Mapped[str] = mapped_column(Text)
    username_nonce: Mapped[str] = mapped_column(String(32))
    password_ciphertext: Mapped[str] = mapped_column(Text)
    password_nonce: Mapped[str] = mapped_column(String(32))
    key_id: Mapped[str] = mapped_column(String(32))
    usage_note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="active")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    maintainer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)


class CredentialGrant(Base):
    __tablename__ = "credential_grants"
    credential_id: Mapped[str] = mapped_column(
        ForeignKey("credentials.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    can_read: Mapped[bool] = mapped_column(Boolean, default=False)
    can_manage: Mapped[bool] = mapped_column(Boolean, default=False)


class Favorite(Base):
    __tablename__ = "favorites"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Shortcut(Base):
    __tablename__ = "shortcuts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("endpoints.id"), primary_key=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class RecentVisit(Base):
    __tablename__ = "recent_visits"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    endpoint_id: Mapped[str] = mapped_column(ForeignKey("endpoints.id"), primary_key=True)
    visited_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"))
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resource_id: Mapped[str | None] = mapped_column(ForeignKey("resources.id"))
    action: Mapped[str] = mapped_column(String(80))
    target_id: Mapped[str] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class ResourceRevision(Base):
    __tablename__ = "resource_revisions"
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    changed_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    resource_id: Mapped[str | None] = mapped_column(ForeignKey("resources.id"))
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(120))
    url: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open")
    resolution: Mapped[str] = mapped_column(Text, default="")
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    version: Mapped[int] = mapped_column(Integer, default=1)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    reset_at: Mapped[datetime] = mapped_column(DateTime)
