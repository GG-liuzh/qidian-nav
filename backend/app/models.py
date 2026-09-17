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
    __table_args__ = {"comment": "站点用户账号，独立于空间成员关系"}
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    username: Mapped[str] = mapped_column(String(80), unique=True, comment="登录用户名，全站唯一")
    display_name: Mapped[str] = mapped_column(String(80), comment="用户显示名称")
    password_hash: Mapped[str] = mapped_column(Text, comment="登录密码的 Argon2 哈希，不保存明文")
    recovery_hash: Mapped[str | None] = mapped_column(
        String(64), comment="账户恢复码摘要，空表示未设置或已撤销"
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    is_superadmin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), comment="是否为站点超级管理员"
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="版本号，用于并发修改校验"
    )
    # Retained only for compatibility with historical account deletion migrations.
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="账号逻辑删除时间（UTC），删除后不可登录或重新启用，保留历史关联"
    )
    preferences: Mapped[dict] = mapped_column(JSON, default=dict, comment="用户偏好设置（JSON）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, comment="创建时间（UTC）")


class Workspace(Base):
    __tablename__ = "workspaces"
    __table_args__ = {"comment": "协作空间及公开导航配置"}
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    name: Mapped[str] = mapped_column(String(80), comment="名称")
    public_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), comment="是否允许空间发布公开导航"
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), comment="是否启用")
    version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="版本号，用于并发修改校验"
    )
    collaboration_mode: Mapped[str] = mapped_column(
        String(20),
        default="maintainers",
        server_default="maintainers",
        comment="空间协作模式，maintainers 表示由管理员与维护人编辑",
    )


class SiteSettings(Base):
    __tablename__ = "site_settings"
    __table_args__ = {"comment": "站点全局设置"}
    id: Mapped[str] = mapped_column(String(32), primary_key=True, comment="站点设置固定标识 main")
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), comment="站点初始所有者用户标识")
    home_workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id"), comment="默认公开首页空间标识，空表示使用站点所有者个人公开页"
    )


class TransferReceipt(Base):
    __tablename__ = "transfer_receipts"
    __table_args__ = {"comment": "个人资料迁移导入记录，用于避免重复导入"}
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, comment="关联用户标识")
    package_id: Mapped[str] = mapped_column(String(64), primary_key=True, comment="迁移包唯一标识")
    summary: Mapped[dict] = mapped_column(JSON, default=dict, comment="导入结果摘要（JSON）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, comment="创建时间（UTC）")


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id"),
        CheckConstraint("role IN ('member','maintainer','admin')"),
        {"comment": "用户在各协作空间的成员资格与角色"},
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), comment="所属协作空间标识")
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), comment="关联用户标识")
    role: Mapped[str] = mapped_column(
        String(20), default="member", comment="空间角色：member 普通成员、maintainer 维护人、admin 管理员"
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号，用于并发修改校验")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = {"comment": "用户登录会话及当前空间"}
    token_hash: Mapped[str] = mapped_column(
        String(64), primary_key=True, comment="登录会话令牌摘要，不保存原始令牌"
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, comment="关联用户标识")
    csrf_token: Mapped[str] = mapped_column(String(64), comment="用于校验会话写入请求的防跨站请求伪造令牌")
    expires_at: Mapped[datetime] = mapped_column(DateTime, comment="到期时间（UTC）")
    active_workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id"), comment="会话当前选中的空间标识"
    )


class AccountReset(Base):
    __tablename__ = "account_resets"
    __table_args__ = {"comment": "超级管理员签发的一次性账号密码重置链接"}
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, comment="链接令牌摘要，不保存原始令牌")
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), comment="关联用户标识")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), comment="创建者用户标识")
    expires_at: Mapped[datetime] = mapped_column(DateTime, comment="到期时间（UTC）")
    used_at: Mapped[datetime | None] = mapped_column(DateTime, comment="使用时间（UTC），空表示尚未使用")


class Invitation(Base):
    __tablename__ = "invitations"
    __table_args__ = (
        CheckConstraint("max_uses IS NULL OR max_uses >= 1", name="invitation_max_uses"),
        CheckConstraint(
            "used_count >= 0 AND (max_uses IS NULL OR used_count <= max_uses)", name="invitation_used_count"
        ),
        {"comment": "空间成员邀请链接及有效期、使用次数"},
    )
    max_uses: Mapped[int | None] = mapped_column(
        Integer().evaluates_none(),
        default=1,
        server_default="1",
        comment="邀请最多可成功使用的次数，空表示有效期内不限次数",
    )
    used_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="邀请已成功使用次数"
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, comment="链接令牌摘要，不保存原始令牌")
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), comment="所属协作空间标识")
    role: Mapped[str] = mapped_column(
        String(20), default="member", comment="空间角色：member 普通成员、maintainer 维护人、admin 管理员"
    )
    kind: Mapped[str] = mapped_column(
        String(20), default="invite", comment="链接类型：invite 成员邀请，保留历史类型"
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), comment="历史定向链接关联的用户标识，普通成员邀请为空"
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), comment="创建者用户标识")
    expires_at: Mapped[datetime] = mapped_column(DateTime, comment="到期时间（UTC）")
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="邀请次数耗尽时间（UTC），未耗尽或不限次数时为空；兼容历史单次链接"
    )


SCOPE_CHECK = "(scope = 'team' AND workspace_id IS NOT NULL AND owner_user_id IS NULL) OR (scope = 'personal' AND owner_user_id IS NOT NULL AND workspace_id IS NULL)"


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(SCOPE_CHECK, name="category_scope"),
        {"comment": "个人分组与空间资源目录"},
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    scope: Mapped[str] = mapped_column(String(20), comment="数据归属范围：team 空间、personal 个人")
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"), comment="所属协作空间标识")
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), comment="个人数据所属用户标识")
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id"), comment="父分组标识，空表示根分组"
    )
    name: Mapped[str] = mapped_column(String(80), comment="名称")
    visibility: Mapped[str] = mapped_column(
        String(20), default="workspace", comment="目录可见范围，workspace 表示空间内可见"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="显示排序值，值越小越靠前")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号，用于并发修改校验")


class CategoryGrant(Base):
    __tablename__ = "category_grants"
    __table_args__ = {"comment": "历史目录授权记录，当前空间按成员角色授权"}
    category_id: Mapped[str] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True, comment="关联资源分组标识"
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, comment="关联用户标识")
    can_read: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否允许读取")
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否允许编辑")


class Environment(Base):
    __tablename__ = "environments"
    __table_args__ = (
        CheckConstraint(SCOPE_CHECK, name="environment_scope"),
        UniqueConstraint("workspace_id", "key"),
        UniqueConstraint("owner_user_id", "key"),
        {"comment": "个人或空间的开发、测试、生产及自定义环境"},
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    scope: Mapped[str] = mapped_column(
        String(20), default="team", comment="数据归属范围：team 空间、personal 个人"
    )
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"), comment="所属协作空间标识")
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), comment="个人数据所属用户标识")
    key: Mapped[str] = mapped_column(String(32), comment="环境唯一键")
    label: Mapped[str] = mapped_column(String(40), comment="环境显示名称")
    kind: Mapped[str] = mapped_column(
        String(20), default="custom", comment="环境类型：dev 开发、test 测试、prod 生产、custom 自定义"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="显示排序值，值越小越靠前")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号，用于并发修改校验")


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint(SCOPE_CHECK, name="resource_scope"),
        CheckConstraint("type IN ('system','bookmark')"),
        {"comment": "个人与空间的系统入口、书签资源"},
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    scope: Mapped[str] = mapped_column(
        String(20), index=True, comment="数据归属范围：team 空间、personal 个人"
    )
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"), comment="所属协作空间标识")
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), index=True, comment="个人数据所属用户标识"
    )
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.id"), index=True, comment="关联资源分组标识"
    )
    type: Mapped[str] = mapped_column(String(20), comment="资源类型：system 多环境系统、bookmark 书签")
    is_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false(), comment="是否明确公开链接元数据，不公开业务凭据"
    )
    name: Mapped[str] = mapped_column(String(120), comment="名称")
    aliases: Mapped[str] = mapped_column(String(240), default="", comment="资源别名，用于搜索")
    description: Mapped[str] = mapped_column(Text, default="", comment="详细说明")
    tags: Mapped[list] = mapped_column(JSON, default=list, comment="资源标签列表（JSON）")
    icon: Mapped[str] = mapped_column(String(30), default="globe", comment="图标名称")
    maintainer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), comment="负责维护的用户标识")
    search_text: Mapped[str] = mapped_column(Text, default="", comment="规范化的资源搜索文本")
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="资源状态：active 正常、archived 已归档"
    )
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号，用于并发修改校验")
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime, index=True, comment="逻辑删除时间（UTC），空表示未删除"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, comment="创建时间（UTC）")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, comment="最近更新时间（UTC）")


class ResourceGrant(Base):
    __tablename__ = "resource_grants"
    __table_args__ = {"comment": "历史资源授权记录，当前空间按成员角色授权"}
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True, comment="关联资源标识"
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, comment="关联用户标识")
    can_read: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否允许读取")
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否允许编辑")
    can_manage_accounts: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否允许管理业务账号")


class Endpoint(Base):
    __tablename__ = "endpoints"
    __table_args__ = (
        UniqueConstraint("resource_id", "environment_key"),
        {"comment": "资源在各环境下的访问入口"},
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    resource_id: Mapped[str] = mapped_column(ForeignKey("resources.id"), index=True, comment="关联资源标识")
    environment_id: Mapped[str | None] = mapped_column(
        ForeignKey("environments.id"), comment="关联环境标识，书签入口可为空"
    )
    environment_key: Mapped[str] = mapped_column(String(32), comment="环境键，与资源标识共同唯一")
    url: Mapped[str] = mapped_column(Text, comment="访问链接地址")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, comment="逻辑删除时间（UTC），空表示未删除")


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = {"comment": "资源入口下的加密业务账号凭据"}
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    endpoint_id: Mapped[str] = mapped_column(
        ForeignKey("endpoints.id"), index=True, comment="关联资源入口标识"
    )
    name: Mapped[str] = mapped_column(String(80), comment="名称")
    username_ciphertext: Mapped[str] = mapped_column(Text, comment="AES-256-GCM 加密的业务账号用户名")
    username_nonce: Mapped[str] = mapped_column(String(32), comment="用户名加密使用的随机数")
    password_ciphertext: Mapped[str] = mapped_column(Text, comment="AES-256-GCM 加密的业务账号密码")
    password_nonce: Mapped[str] = mapped_column(String(32), comment="密码加密使用的随机数")
    key_id: Mapped[str] = mapped_column(String(32), comment="加密密钥版本标识")
    usage_note: Mapped[str] = mapped_column(Text, default="", comment="业务账号使用说明")
    status: Mapped[str] = mapped_column(
        String(20), default="active", comment="业务账号状态：active 有效、pending 待确认、disabled 停用"
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime, comment="业务账号到期时间（UTC），空表示未设置"
    )
    maintainer_id: Mapped[str] = mapped_column(ForeignKey("users.id"), comment="负责维护的用户标识")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号，用于并发修改校验")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, comment="逻辑删除时间（UTC），空表示未删除")


class CredentialGrant(Base):
    __tablename__ = "credential_grants"
    __table_args__ = {"comment": "历史凭据授权记录，当前空间按成员角色授权"}
    credential_id: Mapped[str] = mapped_column(
        ForeignKey("credentials.id", ondelete="CASCADE"), primary_key=True, comment="关联业务账号凭据标识"
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, comment="关联用户标识")
    can_read: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否允许读取")
    can_manage: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否允许管理凭据")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = {"comment": "用户收藏的资源及排序"}
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, comment="关联用户标识")
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id"), primary_key=True, comment="关联资源标识"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="显示排序值，值越小越靠前")


class Shortcut(Base):
    __tablename__ = "shortcuts"
    __table_args__ = {"comment": "用户快捷入口及排序"}
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, comment="关联用户标识")
    endpoint_id: Mapped[str] = mapped_column(
        ForeignKey("endpoints.id"), primary_key=True, comment="关联资源入口标识"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment="显示排序值，值越小越靠前")


class RecentVisit(Base):
    __tablename__ = "recent_visits"
    __table_args__ = {"comment": "用户最近访问入口记录"}
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True, comment="关联用户标识")
    endpoint_id: Mapped[str] = mapped_column(
        ForeignKey("endpoints.id"), primary_key=True, comment="关联资源入口标识"
    )
    visited_at: Mapped[datetime] = mapped_column(DateTime, default=now, comment="最近访问时间（UTC）")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = {"comment": "账号、资源及站点管理操作审计记录"}
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True, comment="执行操作的用户标识")
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("workspaces.id"), comment="所属协作空间标识")
    owner_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), comment="个人数据所属用户标识")
    resource_id: Mapped[str | None] = mapped_column(ForeignKey("resources.id"), comment="关联资源标识")
    action: Mapped[str] = mapped_column(String(80), comment="审计操作类型")
    target_id: Mapped[str] = mapped_column(String(64), comment="操作对象标识")
    detail: Mapped[dict] = mapped_column(JSON, default=dict, comment="审计详情（JSON），不记录明文凭据")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True, comment="创建时间（UTC）")


class ResourceRevision(Base):
    __tablename__ = "resource_revisions"
    __table_args__ = {"comment": "资源各版本的历史快照"}
    resource_id: Mapped[str] = mapped_column(
        ForeignKey("resources.id"), primary_key=True, comment="关联资源标识"
    )
    version: Mapped[int] = mapped_column(Integer, primary_key=True, comment="版本号，用于并发修改校验")
    snapshot: Mapped[dict] = mapped_column(JSON, comment="资源该版本的快照（JSON）")
    changed_by: Mapped[str] = mapped_column(ForeignKey("users.id"), comment="修改者用户标识")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, comment="创建时间（UTC）")


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = {"comment": "空间成员提交的链接建议与问题反馈"}
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=identifier, comment="唯一标识")
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), comment="所属协作空间标识")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"), comment="创建者用户标识")
    resource_id: Mapped[str | None] = mapped_column(ForeignKey("resources.id"), comment="关联资源标识")
    category_id: Mapped[str | None] = mapped_column(ForeignKey("categories.id"), comment="关联资源分组标识")
    kind: Mapped[str] = mapped_column(
        String(20), comment="反馈类型：add 新增链接、edit 信息纠错、broken 链接失效、account 账号问题"
    )
    title: Mapped[str] = mapped_column(String(120), comment="反馈标题")
    url: Mapped[str] = mapped_column(Text, default="", comment="访问链接地址")
    description: Mapped[str] = mapped_column(Text, default="", comment="详细说明")
    status: Mapped[str] = mapped_column(
        String(20),
        default="open",
        comment="反馈处理状态：open 待处理、accepted 已采纳、rejected 已拒绝、withdrawn 已撤回",
    )
    resolution: Mapped[str] = mapped_column(Text, default="", comment="反馈处理说明")
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), comment="反馈处理人用户标识")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, comment="创建时间（UTC）")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="版本号，用于并发修改校验")


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    __table_args__ = {"comment": "请求限流计数及重置时间"}
    key: Mapped[str] = mapped_column(String(64), primary_key=True, comment="限流对象与请求类型的摘要键")
    count: Mapped[int] = mapped_column(Integer, default=0, comment="当前限流窗口内的请求次数")
    reset_at: Mapped[datetime] = mapped_column(DateTime, comment="限流计数重置时间（UTC）")
