# 栖点 · 个人与团队导航（qidian-nav）

基于 **Vue 3 + FastAPI + SQLAlchemy** 的导航应用。支持个人书签、多空间协作、环境入口、共享账号、公开导航和个人资料迁移。

- 目录可搜索、折叠，个人分组最多 8 层；目录区域独立滚动，设置按用途分组。
- 同一个个人账号可加入多个空间，在不同空间拥有不同角色。
- 普通成员查看空间内容和有效共享账号；维护人维护链接和账号；管理员管理目录、环境、成员及公开范围。
- 新资源默认私有 / 空间内可见，明确公开后才出现在免登录导航中。
- 用户名、密码加密保存，读取时检查当前权限和账号状态并记录审计；账号面板默认显示可用账号的用户名，密码按需显示并自动隐藏。
- 支持 Chrome 等浏览器导出的 HTML 书签，以及口令加密的个人迁移文件。

## Ubuntu 上用 Docker 部署

推荐 Ubuntu 22.04 / 24.04 LTS，安装 **Docker Engine 和 Docker Compose v2 插件**。服务器无需安装 Node.js、Python 或 PostgreSQL，构建和运行均在容器中完成。

部署仅运行应用和 PostgreSQL，应用默认提供 **`http://127.0.0.1:4180`** 的 HTTP 入口。域名、HTTPS 证书和反向代理由你在 **1Panel** 中手动管理。

Docker 安装参考 [官方 Ubuntu 安装文档](https://docs.docker.com/engine/install/ubuntu/)。先确认：

```bash
docker version
docker compose version
```

以下命令以当前账号能够运行 Docker 为前提。需要时为 Docker 命令添加 `sudo`。Compose 建议使用 v2.20 或更新版本。

### 1. 上传源码并配置应用

克隆公开仓库并准备应用的部署参数：

```bash
git clone https://github.com/GG-liuzh/qidian-nav.git
cd qidian-nav/deploy
test -f .env || cp .env.example .env
nano .env
```

`NAV_DOMAIN` 填写你在 1Panel 中使用的域名，**不要包含 `https://`、端口或路径**。此项只用于应用的 Host / Origin 白名单校验：

```dotenv
NAV_DOMAIN=nav.your-domain.com
COMPOSE_PROJECT_NAME=qidian-nav
NAV_IMAGE=qidian-nav:latest
NAV_REGISTRATION_ENABLED=false
NAV_SESSION_HOURS=12
NAV_WEB_BIND=127.0.0.1
NAV_WEB_PORT=4180
```

`NAV_REGISTRATION_ENABLED=false` 表示关闭自由注册，有效邀请仍可注册新账号。已有部署保留原来的 `.env` 和项目名，不能直接用示例文件覆盖。

### 2. 构建、初始化密钥并启动

继续在 `deploy` 目录执行：

```bash
# 构建前端与后端的完整应用镜像
docker compose build --pull web

# 首次生成部署密钥；再次运行只校验，不替换已有密钥
docker compose run --rm --no-deps secrets-init

# 启动 PostgreSQL 和应用，并等待服务就绪
docker compose up -d --wait

docker compose ps
```

首次启动必须先运行 `secrets-init`，否则应用找不到挂载的密钥文件。它使用刚构建的应用镜像，无需在 Ubuntu 主机上执行 Python 脚本。检测到已有密钥缺失或损坏时会停止，避免生成无法解密旧数据的新密钥。

应用就绪后，通过你在 1Panel 中配置的 HTTPS 域名访问。默认应用 HTTP 入口为 `127.0.0.1:4180`，容器内端口为 `4173`；可用 `NAV_WEB_BIND` / `NAV_WEB_PORT` 调整宿主机监听地址和端口。首次初始化令牌用下面的命令查看：

```bash
docker compose exec web cat /run/secrets/setup_token
```

点击页面的“初始化我的导航”，填写令牌并创建第一个超级管理员。空间名称可留空；创建后请保存一次性显示的账户恢复码。安装令牌不是登录密码。

### 3. 常用维护命令

```bash
# 查看服务和日志
docker compose ps
docker compose logs --tail=100 web db
docker compose logs -f --tail=100 web

# 仅重启，不更新镜像或配置
docker compose restart web

# 停止服务，保留数据卷与部署密钥
docker compose down

# 再次启动
docker compose up -d --wait
```

更新代码后，先按照 [Ubuntu 部署说明](docs/DEPLOY_UBUNTU.md#备份与恢复) 备份，再执行：

```bash
docker compose build --pull web
docker compose run --rm --no-deps secrets-init
docker compose up -d --wait
```

`restart` 不会采用新镜像或新的环境变量，更新时要使用 `up -d`。启动会执行所需数据库迁移。数据库卷、部署密钥和 `COMPOSE_PROJECT_NAME` 都应保留；**不要使用 `docker compose down -v` 更新服务**。

### 直接使用 docker build

也可以在**项目根目录**单独构建镜像：

```bash
docker build --pull -f deploy/Dockerfile -t qidian-nav:latest .
```

之后进入 `deploy` 目录，运行上述密钥初始化和启动命令即可。镜像同时包含编译后的网页和后端，容器内部提供 `4173` 端口的 HTTP 服务。

如果在其他机器构建，再传到 Ubuntu：

```bash
# 构建机器
docker save -o qidian-nav-image.tar qidian-nav:latest

# Ubuntu 服务器：上传应用镜像和 deploy 目录后
docker load -i qidian-nav-image.tar
cd deploy
docker compose run --rm --no-deps secrets-init
docker compose up -d --no-build --wait
```

此方式仍需能拉取 PostgreSQL 镜像。构建机器与服务器架构不同时，使用 `docker buildx build --platform linux/amd64 --load -f deploy/Dockerfile -t qidian-nav:latest .`；ARM64 服务器则将平台改为 `linux/arm64`。

## 数据保存与安全边界

Docker 部署使用 PostgreSQL 命名数据卷；本机开发默认使用 SQLite。数据不会只存在浏览器缓存或容器的可写层中。

| 内容 | Docker 部署位置 |
| --- | --- |
| 账号、目录、资源、收藏、成员与审计 | Compose 的 `database` 数据卷 |
| 数据库密码、凭据加密密钥、初始化令牌 | 项目下 `.runtime/deploy-secrets/`，以只读文件分别挂载给服务 |

镜像构建使用文件白名单，不会打包本机 `.env`、数据库、部署密钥、测试数据或 `node_modules`。本机 SQLite 资料也不会自动上传到新服务器；个人资料可通过页面中的“个人迁移”导入。

业务凭据使用 AES-256-GCM，加密密钥必须与数据库配套备份。登录密码使用 Argon2 哈希，会话、恢复码和邀请令牌以摘要形式保存。

当前按**空间角色**授权，普通成员可读取所在空间的有效共享账号。如果不同同事只能看不同资料，应拆分空间。资源标记公开后，**所有启用环境的链接都会公开**；没有逐环境公开开关。账号密码不会随链接公开。

生产配置要求 HTTPS、明确的域名与请求来源、Secure Cookie 及限流。默认不映射数据库和应用端口到公网，应用以非 root 用户运行、根文件系统只读，容器日志限制大小。服务器和密钥持有者仍有基础设施访问能力，这些保护不构成“绝对安全”的保证。详见 [安全审查报告](docs/SECURITY_REVIEW.md)。

## 本机开发

Windows 需要 Python 3.11+ 与 Node.js 22.12+。在项目根目录运行：

```powershell
.\start.ps1
```

默认访问 `http://127.0.0.1:4180/`。已经安装依赖并构建前端时，可以运行 `./start.ps1 -SkipInstall`。本机配置见 [.env.example](.env.example)；已有 `.env` 指向的数据会继续使用。

项目可以克隆到任意目录，启动脚本和默认配置会自动定位当前项目，无需修改盘符或用户名路径。首次启动可以直接使用内置默认配置；需要自定义时，再将 `.env.example` 复制为 `.env`。`.env`、运行数据、依赖和构建缓存已列入 `.gitignore`，已有本机配置应保留。

普通 SQLite 文件 URL、凭据密钥、安装令牌、数据库密码文件及前端构建目录的**相对路径统一以项目根目录为基准**，不受终端当前目录影响。例如：

```dotenv
TEAM_NAV_DATABASE_URL=sqlite:///.runtime/team-nav.db
TEAM_NAV_KEY_FILE=.runtime/secrets/credential.key
TEAM_NAV_SETUP_TOKEN_FILE=.runtime/secrets/setup-token
TEAM_NAV_FRONTEND_DIST=frontend/dist
```

程序在运行时解析这些路径；明确指定的绝对路径仍受支持。为兼容已有配置和数据，环境变量前缀及内部数据标识继续沿用原命名。整体迁移已有数据时，保留原 `.env`、数据库及配套密钥；新机器上的 Python 虚拟环境和 Node 依赖由启动脚本重新安装。

开发前端热更新时，保持后端运行，再打开另一个终端：

```powershell
cd frontend
npm.cmd run dev
```

开发页面位于 `http://127.0.0.1:5173/`，API 代理到本机 `4180`。`start.ps1` 只用于本机开发，公网 Ubuntu 部署使用上面的 Docker 方案。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe scripts\test_backend.py
.\.venv\Scripts\python.exe -m pip_audit --local
cd frontend
npm.cmd ci
npm.cmd run build
npx.cmd playwright install chromium --only-shell
npm.cmd run test:e2e
npm.cmd audit
```

后端测试默认使用临时 SQLite 数据库。验证 PostgreSQL 时，先准备可建表的独立测试数据库，再将 `TEAM_NAV_TEST_DATABASE_URL` 设置为它的连接 URL，例如 `postgresql+psycopg://test_user:YOUR_TEST_PASSWORD@127.0.0.1:5432/team_nav_test`，然后执行 `scripts/test_backend.py --postgres`。数据库名必须以 `team_nav_test` 开头；测试会重建其中的表。仓库不包含本机数据库或密码文件。浏览器测试自动使用 `4179` 上的临时实例，不使用本机服务的真实数据。

本次在改名后的项目目录完成验证：120 项后端检查通过（SQLite + PostgreSQL），2 项 POSIX 平台检查在 Windows 跳过；9 组浏览器流程与生产构建通过。部署初始化测试覆盖密钥生成、重复运行、损坏 / 缺失文件以及日志不输出密钥。

另有 6 个已确认的待修复问题，详见[测试报告与独立复现用例](docs/TEST_REPORT_2026-09-15.md)。这些复现用例按预期正确行为断言，目前会失败，不计入上述常规回归结果。

## 文档

- [Ubuntu 应用部署、升级与备份](docs/DEPLOY_UBUNTU.md)
- [当前账号、公开与迁移规则](docs/CURRENT_DESIGN.md)
- [已知问题与独立复现用例](docs/TEST_REPORT_2026-09-15.md)
- [首轮安全审查与部署边界](docs/SECURITY_REVIEW.md)
- [产品与交互设计](docs/PRODUCT_DESIGN.md)
- [视觉与布局](docs/UI_SPEC.md)
- [实现方案](docs/IMPLEMENTATION_PLAN.md)

MFA / OIDC、自动链接检测、定时备份和集合管理仍属于后续规划。
