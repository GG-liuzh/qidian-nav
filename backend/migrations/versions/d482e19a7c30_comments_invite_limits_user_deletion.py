"""Chinese schema comments, reusable invitations and logical account deletion."""

import sqlalchemy as sa
from alembic import op

revision = "d482e19a7c30"
down_revision = "c3d8f7a9b641"
branch_labels = None
depends_on = None

# Frozen schema descriptions: historical migrations must not import live models.
COMMENTS = {
    "users": (
        "站点用户账号，独立于空间成员关系",
        {
            "id": "唯一标识",
            "username": "登录用户名，全站唯一",
            "display_name": "用户显示名称",
            "password_hash": "登录密码的 Argon2 哈希，不保存明文",
            "recovery_hash": "账户恢复码摘要，空表示未设置或已撤销",
            "active": "是否启用",
            "is_superadmin": "是否为站点超级管理员",
            "version": "版本号，用于并发修改校验",
            "deleted_at": "账号逻辑删除时间（UTC），删除后不可登录或重新启用，保留历史关联",
            "preferences": "用户偏好设置（JSON）",
            "created_at": "创建时间（UTC）",
        },
    ),
    "workspaces": (
        "协作空间及公开导航配置",
        {
            "id": "唯一标识",
            "name": "名称",
            "public_enabled": "是否允许空间发布公开导航",
            "active": "是否启用",
            "version": "版本号，用于并发修改校验",
            "collaboration_mode": "空间协作模式，maintainers 表示由管理员与维护人编辑",
        },
    ),
    "site_settings": (
        "站点全局设置",
        {
            "id": "站点设置固定标识 main",
            "owner_user_id": "站点初始所有者用户标识",
            "home_workspace_id": "默认公开首页空间标识，空表示使用站点所有者个人公开页",
        },
    ),
    "transfer_receipts": (
        "个人资料迁移导入记录，用于避免重复导入",
        {
            "user_id": "关联用户标识",
            "package_id": "迁移包唯一标识",
            "summary": "导入结果摘要（JSON）",
            "created_at": "创建时间（UTC）",
        },
    ),
    "memberships": (
        "用户在各协作空间的成员资格与角色",
        {
            "id": "唯一标识",
            "workspace_id": "所属协作空间标识",
            "user_id": "关联用户标识",
            "role": "空间角色：member 普通成员、maintainer 维护人、admin 管理员",
            "active": "是否启用",
            "version": "版本号，用于并发修改校验",
        },
    ),
    "sessions": (
        "用户登录会话及当前空间",
        {
            "token_hash": "登录会话令牌摘要，不保存原始令牌",
            "user_id": "关联用户标识",
            "csrf_token": "用于校验会话写入请求的防跨站请求伪造令牌",
            "expires_at": "到期时间（UTC）",
            "active_workspace_id": "会话当前选中的空间标识",
        },
    ),
    "account_resets": (
        "超级管理员签发的一次性账号密码重置链接",
        {
            "id": "唯一标识",
            "token_hash": "链接令牌摘要，不保存原始令牌",
            "user_id": "关联用户标识",
            "created_by": "创建者用户标识",
            "expires_at": "到期时间（UTC）",
            "used_at": "使用时间（UTC），空表示尚未使用",
        },
    ),
    "invitations": (
        "空间成员邀请链接及有效期、使用次数",
        {
            "max_uses": "邀请最多可成功使用的次数，空表示有效期内不限次数",
            "used_count": "邀请已成功使用次数",
            "id": "唯一标识",
            "token_hash": "链接令牌摘要，不保存原始令牌",
            "workspace_id": "所属协作空间标识",
            "role": "空间角色：member 普通成员、maintainer 维护人、admin 管理员",
            "kind": "链接类型：invite 成员邀请，保留历史类型",
            "user_id": "历史定向链接关联的用户标识，普通成员邀请为空",
            "created_by": "创建者用户标识",
            "expires_at": "到期时间（UTC）",
            "used_at": "邀请次数耗尽时间（UTC），未耗尽或不限次数时为空；兼容历史单次链接",
        },
    ),
    "categories": (
        "个人分组与空间资源目录",
        {
            "id": "唯一标识",
            "scope": "数据归属范围：team 空间、personal 个人",
            "workspace_id": "所属协作空间标识",
            "owner_user_id": "个人数据所属用户标识",
            "parent_id": "父分组标识，空表示根分组",
            "name": "名称",
            "visibility": "目录可见范围，workspace 表示空间内可见",
            "sort_order": "显示排序值，值越小越靠前",
            "version": "版本号，用于并发修改校验",
        },
    ),
    "category_grants": (
        "历史目录授权记录，当前空间按成员角色授权",
        {
            "category_id": "关联资源分组标识",
            "user_id": "关联用户标识",
            "can_read": "是否允许读取",
            "can_edit": "是否允许编辑",
        },
    ),
    "environments": (
        "个人或空间的开发、测试、生产及自定义环境",
        {
            "id": "唯一标识",
            "scope": "数据归属范围：team 空间、personal 个人",
            "workspace_id": "所属协作空间标识",
            "owner_user_id": "个人数据所属用户标识",
            "key": "环境唯一键",
            "label": "环境显示名称",
            "kind": "环境类型：dev 开发、test 测试、prod 生产、custom 自定义",
            "enabled": "是否启用",
            "sort_order": "显示排序值，值越小越靠前",
            "version": "版本号，用于并发修改校验",
        },
    ),
    "resources": (
        "个人与空间的系统入口、书签资源",
        {
            "id": "唯一标识",
            "scope": "数据归属范围：team 空间、personal 个人",
            "workspace_id": "所属协作空间标识",
            "owner_user_id": "个人数据所属用户标识",
            "category_id": "关联资源分组标识",
            "type": "资源类型：system 多环境系统、bookmark 书签",
            "is_public": "是否明确公开链接元数据，不公开业务凭据",
            "name": "名称",
            "aliases": "资源别名，用于搜索",
            "description": "详细说明",
            "tags": "资源标签列表（JSON）",
            "icon": "图标名称",
            "maintainer_id": "负责维护的用户标识",
            "search_text": "规范化的资源搜索文本",
            "status": "资源状态：active 正常、archived 已归档",
            "version": "版本号，用于并发修改校验",
            "deleted_at": "逻辑删除时间（UTC），空表示未删除",
            "created_at": "创建时间（UTC）",
            "updated_at": "最近更新时间（UTC）",
        },
    ),
    "resource_grants": (
        "历史资源授权记录，当前空间按成员角色授权",
        {
            "resource_id": "关联资源标识",
            "user_id": "关联用户标识",
            "can_read": "是否允许读取",
            "can_edit": "是否允许编辑",
            "can_manage_accounts": "是否允许管理业务账号",
        },
    ),
    "endpoints": (
        "资源在各环境下的访问入口",
        {
            "id": "唯一标识",
            "resource_id": "关联资源标识",
            "environment_id": "关联环境标识，书签入口可为空",
            "environment_key": "环境键，与资源标识共同唯一",
            "url": "访问链接地址",
            "enabled": "是否启用",
            "deleted_at": "逻辑删除时间（UTC），空表示未删除",
        },
    ),
    "credentials": (
        "资源入口下的加密业务账号凭据",
        {
            "id": "唯一标识",
            "endpoint_id": "关联资源入口标识",
            "name": "名称",
            "username_ciphertext": "AES-256-GCM 加密的业务账号用户名",
            "username_nonce": "用户名加密使用的随机数",
            "password_ciphertext": "AES-256-GCM 加密的业务账号密码",
            "password_nonce": "密码加密使用的随机数",
            "key_id": "加密密钥版本标识",
            "usage_note": "业务账号使用说明",
            "status": "业务账号状态：active 有效、pending 待确认、disabled 停用",
            "expires_at": "业务账号到期时间（UTC），空表示未设置",
            "maintainer_id": "负责维护的用户标识",
            "version": "版本号，用于并发修改校验",
            "deleted_at": "逻辑删除时间（UTC），空表示未删除",
        },
    ),
    "credential_grants": (
        "历史凭据授权记录，当前空间按成员角色授权",
        {
            "credential_id": "关联业务账号凭据标识",
            "user_id": "关联用户标识",
            "can_read": "是否允许读取",
            "can_manage": "是否允许管理凭据",
        },
    ),
    "favorites": (
        "用户收藏的资源及排序",
        {"user_id": "关联用户标识", "resource_id": "关联资源标识", "sort_order": "显示排序值，值越小越靠前"},
    ),
    "shortcuts": (
        "用户快捷入口及排序",
        {
            "user_id": "关联用户标识",
            "endpoint_id": "关联资源入口标识",
            "sort_order": "显示排序值，值越小越靠前",
        },
    ),
    "recent_visits": (
        "用户最近访问入口记录",
        {"user_id": "关联用户标识", "endpoint_id": "关联资源入口标识", "visited_at": "最近访问时间（UTC）"},
    ),
    "audit_events": (
        "账号、资源及站点管理操作审计记录",
        {
            "id": "唯一标识",
            "actor_id": "执行操作的用户标识",
            "workspace_id": "所属协作空间标识",
            "owner_user_id": "个人数据所属用户标识",
            "resource_id": "关联资源标识",
            "action": "审计操作类型",
            "target_id": "操作对象标识",
            "detail": "审计详情（JSON），不记录明文凭据",
            "created_at": "创建时间（UTC）",
        },
    ),
    "resource_revisions": (
        "资源各版本的历史快照",
        {
            "resource_id": "关联资源标识",
            "version": "版本号，用于并发修改校验",
            "snapshot": "资源该版本的快照（JSON）",
            "changed_by": "修改者用户标识",
            "created_at": "创建时间（UTC）",
        },
    ),
    "feedback": (
        "空间成员提交的链接建议与问题反馈",
        {
            "id": "唯一标识",
            "workspace_id": "所属协作空间标识",
            "created_by": "创建者用户标识",
            "resource_id": "关联资源标识",
            "category_id": "关联资源分组标识",
            "kind": "反馈类型：add 新增链接、edit 信息纠错、broken 链接失效、account 账号问题",
            "title": "反馈标题",
            "url": "访问链接地址",
            "description": "详细说明",
            "status": "反馈处理状态：open 待处理、accepted 已采纳、rejected 已拒绝、withdrawn 已撤回",
            "resolution": "反馈处理说明",
            "resolved_by": "反馈处理人用户标识",
            "created_at": "创建时间（UTC）",
            "version": "版本号，用于并发修改校验",
        },
    ),
    "rate_buckets": (
        "请求限流计数及重置时间",
        {
            "key": "限流对象与请求类型的摘要键",
            "count": "当前限流窗口内的请求次数",
            "reset_at": "限流计数重置时间（UTC）",
        },
    ),
    "alembic_version": ("数据库结构迁移版本记录", {"version_num": "当前已应用的 Alembic 迁移版本号"}),
}


def schema_comments(remove=False):
    # SQLite does not support table or column COMMENT metadata.
    if op.get_bind().dialect.name != "postgresql":
        return
    for table, (description, columns) in COMMENTS.items():
        if remove:
            op.drop_table_comment(table)
        else:
            op.create_table_comment(table, description)
        for column, description in columns.items():
            op.alter_column(table, column, comment=None if remove else description)


def upgrade():
    with op.batch_alter_table("invitations") as batch:
        batch.alter_column("max_uses", existing_type=sa.Integer(), nullable=True)
    # Support a legacy zero limit as unlimited, without reopening consumed links.
    op.execute(sa.text("UPDATE invitations SET max_uses = NULL WHERE max_uses = 0"))
    with op.batch_alter_table("invitations") as batch:
        batch.create_check_constraint("invitation_max_uses", "max_uses IS NULL OR max_uses >= 1")
        batch.create_check_constraint(
            "invitation_used_count", "used_count >= 0 AND (max_uses IS NULL OR used_count <= max_uses)"
        )
    schema_comments()


def downgrade():
    schema_comments(remove=True)
    # Reverting to single-use must not reopen links already accepted at least once.
    op.execute(
        sa.text("UPDATE invitations SET used_at = CURRENT_TIMESTAMP WHERE used_count > 0 AND used_at IS NULL")
    )
    with op.batch_alter_table("invitations") as batch:
        batch.drop_constraint("invitation_used_count", type_="check")
        batch.drop_constraint("invitation_max_uses", type_="check")
    op.execute(
        sa.text(
            "UPDATE invitations SET max_uses = CASE WHEN used_count > 0 THEN used_count ELSE 1 END WHERE max_uses IS NULL"
        )
    )
    with op.batch_alter_table("invitations") as batch:
        batch.alter_column("max_uses", existing_type=sa.Integer(), nullable=False)
