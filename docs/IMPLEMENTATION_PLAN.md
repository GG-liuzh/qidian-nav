# 栖点 · 实现方案与开发顺序

版本：v1.1 · 2026-09-14\
当前已实现 Vue / FastAPI 应用、SQLite / PostgreSQL、账号与权限、匿名公开导航、资源与凭据管理、个人迁移、反馈、回收站和审计。实际启动与验证见 [README](../README.md)，当前产品边界见 [当前设计](CURRENT_DESIGN.md)。下文仍包含尚未交付的扩展规划。

## 1. 技术选型

采用前后端分离、同域部署的模块化单体，便于在当前 Python 工作区继续开发。

| 层 | 选择 | 说明 |
| --- | --- | --- |
| 前端 | Vue 3 + TypeScript + Vite | 组件化实现首页、账号抽屉与管理页 |
| 路由与状态 | Vue Router、Pinia、TanStack Vue Query | URL 保存可分享筛选，服务端状态与个人 UI 偏好分离 |
| 界面 | CSS variables + Reka UI + Lucide | 依据视觉稿定制，使用成熟的可访问弹层基础组件 |
| 后端 | FastAPI + Pydantic 2 | 资源、权限、凭据、导入与审计模块 |
| 数据层 | SQLAlchemy 2 + Alembic | 约束、事务和可复现的迁移 |
| 数据库 | 默认 SQLite，可配置 PostgreSQL | 两种数据库均执行集成测试；数据库连接由 `.env` 配置 |
| 本地开发 | 可选 SQLite | 便于个人体验；涉及权限、并发、迁移的验收以 PostgreSQL 为准 |
| 登录 | 独立个人注册 + 可选部门邀请 + Argon2id | 个人账号可自助注册；恢复码由本人保管；OIDC 尚未实现 |
| 凭据加密 | cryptography AES-256-GCM | 服务端按需解密，密钥独立于数据库 |
| 部署 | Docker Compose（应用 + PostgreSQL） | 应用提供 HTTP 端口；域名与 HTTPS 由 1Panel 手动管理，数据库独立持久化 |
| 定时任务（规划） | 单独的任务进程 + 数据库任务表 | 当前未实现自动检测、提醒或定时备份 |

首期无需引入微服务、Elasticsearch 或 Redis。搜索优先数据库授权过滤 + 中文 / 拼音 / 别名索引；先用真实资源数量验证，再根据瓶颈扩展。

## 2. 目录与后续扩展

```text
qidian-nav/
├── README.md
├── docs/                         # 产品与原型文档
│   ├── PRODUCT_DESIGN.md
│   ├── UI_SPEC.md
│   ├── IMPLEMENTATION_PLAN.md
│   └── prototype/
├── frontend/                     # 已有实际实现
│   └── src/
│       ├── pages/
│       ├── features/             # navigation / credentials / import / settings
│       ├── components/
│       ├── api/
│       └── styles/
├── backend/                      # 已有实际实现
│   ├── app/
│   │   ├── auth/
│   │   ├── resources/
│   │   ├── credentials/
│   │   ├── permissions/
│   │   ├── imports/
│   │   ├── maintenance/
│   │   └── audit/
│   ├── migrations/
│   └── tests/
└── deploy/                       # 已有实际实现
```

## 当前新增模型与接口

- `SiteSettings`：首次安装所有者；`User.recovery_hash`：独立账号恢复；`Membership.active`：部门成员资格。
- `Workspace.public_enabled / collaboration_mode`：游客与共同维护开关；`Resource.is_public`：逐资源发布；`TransferReceipt`：导入幂等记录。
- `GET /api/v1/public/navigation`：匿名公开元数据；`POST /auth/register` 无邀请可注册个人账号；`POST /auth/join` 接受部门邀请。
- `POST /workspace` 可选创建部门；`POST /workspace/leave` 离开；`POST /me/recovery-code` 换发恢复码。
- `POST /me/transfer/export|preview|import`：个人迁移。包含凭据的迁移包由 Scrypt 派生密钥并用 AES-GCM 加密；导入事务校验引用、归属和幂等标识。
- `9cbed07c5915` 迁移保持已有内容私有，将个人系统的部门环境引用复制为个人环境，保留入口标识与凭据绑定。

以上路径除特别注明外均以 `/api/v1` 为前缀。已实现模块位于 `backend/app/*.py`，前端在 `frontend/src`。浏览器收藏夹导入、OIDC、自动任务与多部门仍未实现。

## 3. 数据模型

| 实体 | 核心字段 / 关系 |
| --- | --- |
| User | id、display_name、login_identity、status |
| Workspace | id、name、settings；首期一个部门一个共享空间 |
| Membership | workspace_id、user_id、role、status |
| Group / GroupMember | 部门内成员组及成员关系，用于业务线和账号授权 |
| BusinessLine | workspace_id、name、slug、owner_id、sort_order |
| Environment | workspace_id、key、label、kind、color、sort_order、enabled |
| Resource | id、scope、workspace_id / owner_user_id、business_line_id、type、name、aliases、description、icon、maintainer_id、version、status、deleted_at |
| Endpoint | id、resource_id、environment_id、url、label、status、verified_at、verified_by |
| Credential | id、endpoint_id、name、username_ciphertext、username_nonce、password_ciphertext、password_nonce、key_id、usage_note、expires_at、status、maintainer_id、version |
| ResourceGrant | 资源 / 业务线的主体、读取 / 编辑能力 |
| CredentialGrant | credential_id、group_id / user_id、read / manage；不能扩大 ResourceGrant |
| Tag / ResourceTag | 空间内标签及多对多关系 |
| Collection / CollectionItem | 场景集合，引用资源或具体入口 |
| Favorite | user_id、resource_id、sort_order；同用户资源唯一 |
| Shortcut | user_id、endpoint_id、sort_order；固定到具体环境 |
| RecentVisit | user_id、endpoint_id、last_visited_at；私有，可清除 |
| ResourceRevision | resource_id、version、非敏感字段快照、changed_by |
| Feedback / Suggestion | resource_id、endpoint_id、type、status、assignee_id、说明 |
| ImportJob / ImportRow | 批次、状态、目标空间、映射、成功 / 失败行、幂等标识 |
| AuditEvent | actor_id、action、target_type/id、result、timestamp、必要请求元数据 |
| Session | user_id、token_hash、expires_at、revoked_at |

### 必须建立的约束

- Resource 为团队类型时具有 workspace_id，私人类型时具有 owner_user_id，两者互斥；团队业务线与环境必须属于同一个空间。
- 系统 Endpoint 的 `(resource_id, environment_id)` 唯一；普通书签仅有一个无环境 Endpoint。
- 私人书签可使用本人配置的环境或公共环境定义，但引用环境定义不会带来团队资源权限。
- Credential 必须指向现存入口；任何 API 都先校验资源范围，再校验凭据授权。
- 私人凭据直接受资源所有者权限约束，不经过团队授权通道；团队管理员不能给自己授予私人凭据权限。
- Grant 的授权主体必须属于对应空间；移除成员立即使所有派生授权失效。
- 编辑带 `version`，采用事务条件更新；版本不匹配返回 409。
- 密文修改、账号停用与授权变更即时生效；普通资源版本不包含凭据内容。
- 软删除的资源、入口和凭据在所有普通查询中统一排除；恢复走独立服务和权限检查。
- 唯一键和外键在数据库层保障，不能只依靠前端表单。

## 4. API 轮廓

统一前缀 `/api/v1`。列表默认分页；筛选在数据库端先做权限约束。跨空间越权查询统一返回 404，避免确认隐藏对象存在。

| 方法与路径 | 行为 |
| --- | --- |
| POST /auth/login、/auth/logout | 登录、退出，轮换 / 撤销会话 |
| GET /me | 用户、空间、能力和偏好，不包含任何凭据 |
| GET /resources | q、scope、business_line、env、tag、type、cursor |
| POST /resources | 创建资源和入口，事务保存 |
| GET /resources/{id} | 元数据、入口、当前用户可用的能力标记 |
| PATCH /resources/{id} | 携带 version 更新 |
| DELETE /resources/{id} | 软删除，并停止所有关联账号取密 |
| GET /endpoints/{id}/credentials | 仅返回当前用户获准的账号元信息；无明文用户名和密码 |
| POST /credentials/{id}/access | 指定 field=username/password、purpose=copy/reveal；再次授权、记录审计，按需返回一个明文字段 |
| POST /credentials | 新增凭据，独立账号管理权限 |
| PATCH /credentials/{id} | 轮换凭据或修改用途；支持版本号 |
| DELETE /credentials/{id} | 停用 / 软删除，禁止继续获取明文 |
| PUT、DELETE /me/favorites/{resource_id} | 幂等收藏与取消 |
| PUT、DELETE /me/shortcuts/{endpoint_id} | 固定、移除明确入口 |
| POST /me/visits | 记录自己的入口访问，遵守个人开关 |
| DELETE /me/visits | 清空本人历史 |
| POST /imports/preview | 上传受限大小文件并生成预览，不直接发布 |
| POST /imports/{id}/commit | 提交确认映射、选择项和幂等键 |
| GET /exports | 仅导出授权范围的元数据，排除凭据和个人历史 |
| POST /feedback | 反馈链接 / 账号问题，不提交密码 |
| GET /trash、POST /trash/{id}/restore | 授权范围的回收站与恢复 |
| GET /audit-events | 可见范围内操作记录 |

新增资源可以先保存基本链接，再由独立接口配置账号。若界面选择一起保存，由后端组合服务统一校验并在同一事务完成，避免“链接保存了、账号失败但页面称全部成功”。

获取明文接口使用 `Cache-Control: no-store`，敏感页面不被 Service Worker 缓存。账号列表不使用提前返回密文再让前端解密的模式。

## 5. 账号与权限实现规则

1. **访问**：登录态使用随机会话令牌，服务端只存令牌哈希；Cookie 采用 HttpOnly、Secure、SameSite。修改和取密请求检查 Origin 与 CSRF token，登录和取密有速率限制。
2. **存储**：用户名和密码用成熟库分别加密。两个字段各自保存独立的随机 96-bit nonce，每次重加密都重新生成；同一密钥下不能复用 nonce。AAD 绑定 credential ID、endpoint ID 和字段名，防止密文被挪到另一个账号。
3. **密钥**：密钥从部署 secret / 受限挂载文件读取，不进入 Git、数据库明文字段或前端配置。密文记录 key_id；支持密钥轮换及旧密文重新加密。
4. **取密**：每次请求检查成员状态、资源可见性、账号授权、账号状态和有效期，服务端解密后只返回明确请求的字段。
5. **前端**：明文只在当前操作闭包或短时组件状态内存在，不进入全局持久化 store、URL、localStorage、IndexedDB、埋点或崩溃报告。
6. **复制**：成功提示依据浏览器剪贴板结果。审计区分“明文访问获准”和客户端可选报告的“复制成功”；服务端不把一次请求等同于操作系统已经复制。
7. **生命周期**：显示 20 秒后隐藏；窗口失焦、页面隐藏、抽屉关闭、环境切换或退出立即清除。权限撤销无法追回已经展示、记住或复制的旧值，需要目标系统轮换密码。
8. **审计**：记录谁对哪个账号执行了访问 / 管理及结果；不记录明文、请求敏感体、剪贴板内容或完整账号秘密备注。默认团队操作记录保留 180 天，可配置。
9. **管理**：账号管理、账号读取与资源编辑分开控制。URL 主机或环境变更后，已有凭据绑定先停用等待确认，取密时再次核验绑定。
10. **备份**：数据库备份保持凭据密文，备份加密与密钥保管分开；恢复后不绕过成员状态及凭据有效期，定期演练恢复。

共享账号是本产品核心，因此需要后端能力。静态站或只用浏览器 localStorage 的版本不能作为团队凭据的正式实现。

## 6. URL、导入与自动检测

- 输入 URL 使用标准解析器，严格限制 HTTP/HTTPS；图标默认使用站内图标或字母，不向第三方 favicon 服务发送内网域名。
- 描述默认纯文本。若增加 Markdown，禁用原始 HTML并使用成熟 sanitizer；所有用户字符串避免拼接为 HTML。
- 导入只解析用户上传内容，不执行 HTML 中的脚本、不主动抓取其中地址；限制文件大小、记录数、层级与编码。
- CSV 导出对公式前缀做文本转义，避免在电子表格软件中执行公式。
- 自动检测单独启用，使用明确的公司域名 / CIDR 允许列表。允许业务内网地址，但拒绝回环、链路本地、云元数据和未授权网段；IPv4 / IPv6 都检查。
- 每次 DNS 解析、连接与重定向都校验目的地，防止重绑定。限定端口、超时、响应大小、跳转次数与并发数；检测不携带共享账号、不自动登录。
- 检测结果存来源、时间和状态；无公网连通性、VPN 隔离和登录门槛均有独立状态，不伪造健康结论。

## 7. 开发顺序与退出条件

所有阶段合起来构成完整设计。A 阶段完成后才能投入含真实账号的团队使用。

### A. 可以正式使用的完整路径

登录与邀请、部门 / 个人边界、业务线与环境配置、资源增删改查、搜索与筛选、收藏 / 快捷入口、账号管理与按需复制、基础权限与审计、回收站、备份恢复、响应式 UI。

退出条件：产品设计中的核心验收场景通过，直接 API 越权测试通过，真实三环境跳转准确，账号不出现在初始响应或长期存储中，备份可以恢复。

### B. 大量书签与日常协作

书签 / CSV / JSON 导入与预览、批量整理、重复项处理、普通导出、个人最近访问、场景集合、建议与反馈、维护待办、资源版本差异、完整个人偏好。

退出条件：用至少 1000 个样例资源验证搜索和批量操作；重复导入幂等；个人内容不会被团队导出泄露。

### C. 部门治理与组织集成

自助权限申请及处理、组织 OIDC / SSO、自动连通性检测、到期提醒、成员离职移交、按业务线细化授权、密钥轮换流程、管理统计。

退出条件：检测网络边界和重定向规则有效，组织成员撤权立即生效，自动任务不会重复执行，统计不包含私人历史或敏感凭据。

阶段 A 使用管理员直接授权，不依赖阶段 C 的权限申请流程。阶段 A 的登录不依赖组织 SSO，后续接入不会改变资源的稳定 ID。

## 8. 验证策略

- 服务端集成测试覆盖权限矩阵、跨空间访问、账号绑定、过期与停用、版本冲突、软删除与恢复。
- 前端关键流程验证真实跳转 URL、环境不回退、复制成功 / 失败分支、敏感状态清除、表单保留与键盘焦点。
- 导入测试使用重复、深层目录、异常编码、恶意 HTML 和无效 URL 样例；检测测试使用重定向、IPv6 与 DNS 变化样例。
- PostgreSQL 环境验证迁移、唯一约束、事务、并发编辑与任务锁；SQLite 不替代这些结论。
- 真实部署做 HTTPS、会话过期、密钥加载、备份恢复与授权撤回检查。
- 界面稿阶段仅检查页面渲染、交互、响应式和脚本错误，不把模拟成功当成正式系统验收。
