本轮于 2026-09-15 对当前项目进行了本地回归与专项测试，共复现 **6 个 bug：1 个 P1、5 个 P2**。其中 3 个后端问题在 SQLite、PostgreSQL 上均复现，另外 3 个通过 Chromium 实际页面操作复现。业务源码未修改，已添加独立复现用例。

测试环境：Windows、Python 3.11.0、Node.js 24.13.0、npm 11.6.2、PostgreSQL 16.14。测试使用临时 SQLite 数据库和项目已有的 `team_nav_test` PostgreSQL 测试库；浏览器测试由现有脚本启动 `127.0.0.1:4179` 临时实例。

| 检查 | 结果 |
| --- | --- |
| 现有后端测试，SQLite + PostgreSQL | **107 通过，2 跳过** |
| 现有浏览器回归 | **9 通过** |
| TypeScript 检查与 Vite 生产构建 | 通过 |
| Python 依赖审计 `pip_audit --local` | 未报告已知漏洞 |
| npm 依赖审计 | 0 个已知漏洞 |
| 新增后端专项测试 | 3 个场景 × 2 种数据库，**6 次预期行为断言失败** |
| 新增浏览器专项测试 | **3 次预期行为断言失败**，均保留截图和 trace |
| 新增浏览器用例的独立 TypeScript 检查 | 通过 |
| Ruff 静态检查 | 未通过；原生命令有 E902 读取错误，UTF-8 标准输入复核仍有 I001 导入排序告警 |

后端跳过的 2 项是仅适用于 POSIX 的部署文件权限和符号链接检查。新增用例按正确行为编写断言，因此当前失败用于证明下面的缺陷；这些用例位于独立目录，不改变 README 中原有两套测试命令的收集范围。Ruff 告警不计入下面的业务 bug 数量。本轮没有执行实际 Docker/HTTPS 部署或负载测试。

| 编号 | 优先级 | 问题 | 已观察到的结果 |
| --- | --- | --- | --- |
| BUG-01 | P1 | 编辑停用的公开书签会重新启用并公开链接 | `enabled: false → true`，公开接口 `404 → 200` |
| BUG-02 | P2 | 已过期的停用账号在编辑时丢失停用状态 | 保存后变为 `active`，读取接口返回 200 |
| BUG-03 | P2 | 生产环境筛选没有传递给系统标题打开的详情 | 页面筛选 `prod`，详情选中 `test` |
| BUG-04 | P2 | 停用账号被计入有效管理员数量 | 最后一位有效管理员降级成功，剩余有效空间管理员为 0 |
| BUG-05 | P2 | 退出空间没有永久撤销已签发的邀请 | 重新加入为管理员后，旧邀请可创建新的管理员账号 |
| BUG-06 | P2 | 书签导入接受非法主机名 | 无效地址未被跳过，导入后浏览器无法解析 |

**BUG-01 · P1 · 编辑停用的公开书签会重新启用并公开链接**

前提是普通书签的 `is_public=true`，但入口的 `enabled=false`。这是现有 API 支持的有效状态；并非所有未公开书签都会受影响。

复现步骤：

1. 在隔离实例通过 `POST /api/v1/resources` 建立个人普通书签，保留公开标记并停用入口。
2. 进入“个人导航”，编辑该书签，只修改名称并保存。
3. 读取资源详情及该用户的公开导航。

预期：只修改名称，入口继续停用，游客仍不可见。

实际：`configured_enabled` 从 `false` 变为 `true`；本用例的公开个人页原先返回 404，保存后返回 200，并包含该书签。

原因：[ResourceEditor.vue:107](../frontend/src/components/ResourceEditor.vue#L107) 保存普通书签时固定发送 `enabled: true`，没有保留原入口状态。

建议：编辑时保留 `configured_enabled`，仅在创建新书签时默认启用；提供明确的入口状态操作。

证据：[保存后截图](../.runtime/qa-20260915/browser-results/regressions-renaming-a-dis-68a96-reserves-its-disabled-state/test-failed-1.png)、[浏览器实测记录](../.runtime/qa-20260915/browser-results.json)。

**BUG-02 · P2 · 已过期的停用账号在编辑时丢失停用状态**

复现步骤：

1. 创建一个 `status=disabled`、有效期已经过去的业务账号。
2. 打开“编辑账号”，只修改账号名称和有效期，不操作“状态”下拉框。
3. 将有效期延长到未来并保存，再尝试读取账号。

预期：仍保持 `disabled`，须显式启用后才允许读取。

实际：列表接口只返回 `expired`，编辑器默认选中 `active`；保存后实际状态成为 `active`，账号读取接口返回 200。本次在个人账号入口复现，团队共享账号也使用同一套序列化和编辑器代码。

原因：[credentials.py:53](../backend/app/credentials.py#L53) 用计算出的“过期”状态覆盖了原始状态；[CredentialEditor.vue:20](../frontend/src/components/CredentialEditor.vue#L20) 又把 `expired` 映射为 `active`。

建议：分别返回保存的账号状态和是否过期；编辑器始终使用保存的状态作为初值。

证据：[保存后截图](../.runtime/qa-20260915/browser-results/regressions-editing-an-exp-5492d--not-silently-reactivate-it/test-failed-1.png)、[浏览器实测记录](../.runtime/qa-20260915/browser-results.json)。

**BUG-03 · P2 · 生产环境筛选没有传递给系统标题打开的详情**

复现步骤：

1. 创建含开发、测试、生产入口的业务系统。
2. 在导航页筛选“生产”，确认卡片只显示生产入口。
3. 点击系统名称打开详情。

预期：详情选中生产环境，账号区域与当前筛选一致。

实际：详情选中“测试 · TEST”，地址显示 `https://qa-test.example/`。用户需要再次切换，容易查看或复制错误环境的账号。

原因：[ResourceCard.vue:26](../frontend/src/components/ResourceCard.vue#L26) 点击标题只传资源，没有传环境；[ResourceDetails.vue:60](../frontend/src/components/ResourceDetails.vue#L60) 在未收到环境时优先选择测试入口。该问题的触发入口是系统标题。

建议：打开详情时传递当前环境筛选，并优先选择该环境对应的入口。

证据：[生产筛选下打开测试详情的截图](../.runtime/qa-20260915/browser-results/regressions-opening-a-syst-f9be2-cted-production-environment/test-failed-1.png)。

**BUG-04 · P2 · 停用账号被计入有效管理员数量**

复现步骤：

1. 准备一个只有 A、B 两位角色为管理员的空间；站点超级管理员保留站点管理能力。
2. 在站点用户管理中停用 A 的个人账号，B 此时是唯一启用的空间管理员。
3. B 把自己的空间角色改成普通成员。

预期：返回 409，要求保留至少一位有效空间管理员。

实际：返回 200，剩余启用且角色为管理员的空间成员数量为 0。SQLite 和 PostgreSQL 的结果一致。仍可由站点超级管理员恢复，但空间自身的管理员保留规则已被绕过。

原因：[auth.py:427](../backend/app/auth.py#L427) 只统计 `Membership.active` 和角色，没有关联检查 `User.active`。站点停用账号不会同时清除其成员关系。

建议：计数时关联用户表，排除已停用账号；保留现有事务锁，并验证管理员降级和移除两种操作。

用例：`test_last_active_workspace_admin_cannot_demote_self`。

**BUG-05 · P2 · 退出空间没有永久撤销已签发的邀请**

复现步骤：

1. 普通空间管理员 A 创建一个尚未使用的管理员邀请，然后主动退出空间。
2. 检查该邀请，接口此时返回 400，提示已经失效。
3. 在邀请原有有效期内，由其他管理员将 A 重新添加为空间管理员。
4. 使用退出前的旧邀请注册另一个账号。

预期：退出时撤销的邀请持续失效，重新加入后需要重新签发。

实际：旧邀请恢复有效，注册返回 201，新账号角色为 `admin`。SQLite 和 PostgreSQL 均复现。

原因：[workspaces.py:86](../backend/app/workspaces.py#L86) 主动退出只停用成员关系，没有使其签发的未使用邀请过期；邀请校验依赖签发者当前是否为管理员，重新加入后条件再次满足。通过成员管理移除/降级的路径已经有邀请撤销逻辑，主动退出路径遗漏了这一处理。

建议：主动退出时，在同一事务中撤销该用户在当前空间签发的未使用邀请。

用例：`test_leaving_permanently_revokes_issued_administrator_invitation`。

**BUG-06 · P2 · 书签导入接受非法主机名**

复现步骤：

1. 准备 Netscape HTML 书签文件，包含一个正常地址，以及 `https://invalid host.example/path`。
2. 预览书签导入，再确认导入。

预期：预览显示可导入 1 条、跳过无效地址 1 条，实际只保存正常地址。

实际：预览显示可导入 2 条、无效地址 0 条，实际保存了 2 条。SQLite 和 PostgreSQL 均复现。浏览器采用的 WHATWG URL 解析器对该地址返回 `ERR_INVALID_URL`；直接通过资源 API 保存该地址也返回 201。

原因：[schemas.py:16](../backend/app/schemas.py#L16) 只检查 `urlsplit()` 能否取得主机名，以及协议、端口等字段；`urlsplit()` 可以取得带空格的主机名，现有校验没有拒绝。

建议：补充与浏览器一致的主机名合法性校验，同时保留正常内网域名和 IPv6 地址的支持。

用例：`test_bookmark_import_skips_url_with_invalid_hostname`。

**复现用例与结果文件**

文档链接采用项目内相对路径。截图、trace 和结果文件是被 Git 忽略的本机运行产物；克隆后运行对应测试可重新生成 JUnit 结果、浏览器 JSON 报告及失败截图。实测状态保存在浏览器报告的 `observed-behavior` 附件中。

后端用例：[test_backend_regressions.py](../scripts/qa_20260915/test_backend_regressions.py)。在项目根目录执行：

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe scripts\qa_20260915\test_backend_regressions.py

# 先准备独立测试库，并设置 TEAM_NAV_TEST_DATABASE_URL，再同时测试两种数据库
# 示例 URL：postgresql+psycopg://test_user:YOUR_TEST_PASSWORD@127.0.0.1:5432/team_nav_test
.\.venv\Scripts\python.exe scripts\qa_20260915\test_backend_regressions.py --postgres
```

PostgreSQL 模式读取 `TEAM_NAV_TEST_DATABASE_URL`，遵循现有 fixture 的隔离规则，重新建立名称以 `team_nav_test` 开头的测试库内的表。克隆后需要自行提供测试数据库；历史测试集群和密码文件不随源码发布。当前代码在该模式下输出 `6 failed`，对应 BUG-04、05、06 各在两种数据库上失败一次。

浏览器用例：[regressions.spec.ts](../frontend/qa/regressions.spec.ts)，独立配置：[playwright.qa.config.ts](../frontend/playwright.qa.config.ts)。使用已构建的前端，在前端目录执行：

```powershell
cd frontend
npx.cmd playwright test --config playwright.qa.config.ts
```

当前代码输出 `3 failed`，对应 BUG-03、01、02。用例自动启动临时实例，关闭后保留结果文件。

| 结果文件 | 内容 |
| --- | --- |
| [后端 JUnit 结果](../.runtime/qa-20260915/backend-sqlite-postgresql.xml) | 6 次失败的断言、数据库类型与实际响应 |
| [浏览器 JSON 结果](../.runtime/qa-20260915/browser-results.json) | 3 个场景的断言、截图及 trace 路径 |

建议先修复 BUG-01，再处理账号状态及成员/邀请边界，最后修复环境选择和 URL 校验。修复后应让新增 9 次断言全部通过，再运行现有回归用例。
