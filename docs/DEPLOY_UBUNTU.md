# Ubuntu Docker 部署说明

配置文件：`deploy/Dockerfile`、`deploy/compose.yaml`、`deploy/.env.example`。项目可放在服务器任意目录；维护命令在项目的 `deploy` 目录执行，使用 Docker Compose v2。

项目负责应用和数据库的部署。域名、HTTPS 证书与反向代理由你在 1Panel 中手动管理。

## 服务结构

```text
宿主机 HTTP :4180 → web :4173 → PostgreSQL :5432
                       backend 内部网络
```

- `web`：Python 3.12 镜像内包含编译后的 Vue 页面与 FastAPI 后端，默认映射到宿主机 `127.0.0.1:4180`。以 UID/GID 10001 运行、根文件系统只读；启动时执行 Alembic 迁移，健康检查包含数据库连接。
- `db`：PostgreSQL 16，数据写入命名卷。没有宿主机端口映射。
- `secrets-init`：手动运行的工具容器，使用相同应用镜像。没有网络，唯一可写挂载是部署密钥目录。默认 `up` 不会启动它。

`web`、`db` 通过 `internal: true` 的 `backend` 网络通信。`web` 另外加入普通桥接网络 `app`，用于宿主机访问应用 HTTP 端口；`db` 只加入内部网络。

## 首次部署

先安装 [Docker Engine 与 Compose 插件](https://docs.docker.com/engine/install/ubuntu/)，上传项目源码。从项目根目录进入 `deploy` 并准备应用配置：

```bash
cd deploy
test -f .env || cp .env.example .env
nano .env
docker compose build --pull web
docker compose run --rm --no-deps secrets-init
docker compose up -d --wait
docker compose ps
docker compose exec web cat /run/secrets/setup_token
```

在 `.env` 中填写最终访问域名 `NAV_DOMAIN`，仅用于应用的 Host / Origin 白名单。应用启动后默认提供 `http://127.0.0.1:4180`，通过你在 1Panel 中配置的 HTTPS 域名使用页面。宿主机监听地址和端口可由 `NAV_WEB_BIND` / `NAV_WEB_PORT` 调整。

首次页面初始化创建站点超级管理员，之后保存恢复码。初始化令牌仅用于首次安装；不要将它作为登录密码或放入浏览器公开书签。

## 部署参数

| 参数 | 默认值 | 用途 |
| --- | --- | --- |
| `NAV_DOMAIN` | 示例值必须修改 | 应用允许的访问域名，用于 Host / Origin 校验，不包含协议、端口和路径 |
| `COMPOSE_PROJECT_NAME` | 新示例为 `qidian-nav` | 容器与数据卷的项目前缀；首次部署后保持不变 |
| `NAV_IMAGE` | `qidian-nav:latest` | 构建和启动使用的应用镜像名 |
| `NAV_REGISTRATION_ENABLED` | `false` | 是否允许不带邀请的自由注册 |
| `NAV_SESSION_HOURS` | `12` | 普通登录会话时长；用户主动选择长期登录仍为 30 天 |
| `NAV_WEB_BIND` | `127.0.0.1` | 应用 HTTP 服务在宿主机上的监听地址 |
| `NAV_WEB_PORT` | `4180` | 应用 HTTP 服务在宿主机上的端口；容器内端口为 `4173` |

应用配置在 Compose 中启用生产模式、Secure Cookie 和限流，允许来源为 `https://${NAV_DOMAIN}`。容器提供 HTTP 服务，上游请求需保留最终访问域名的 `Host`。部署参数使用 `deploy/.env`，与本机开发的根目录 `.env` 分开。

Compose 的宿主机文件路径相对于部署文件解析；`/app`、`/run/secrets` 等是容器内部约定路径，与宿主机源码所在目录无关。

## 密钥与 Ubuntu 文件权限

`secrets-init` 在项目目录下 `.runtime/deploy-secrets/` 生成三份文件：

- `db-password`：PostgreSQL 密码，仅挂载给数据库与应用。
- `credential.key`：32 字节凭据加密密钥，仅挂载给应用。
- `setup-token`：首次初始化令牌，仅挂载给应用。

目录在 Linux 上使用 `0700` 权限，文件使用 `0644`。这是为兼容普通 Compose 的**单文件只读绑定挂载**：非 root 的应用用户需要读取挂载文件，而宿主机其他普通用户会被私有父目录阻止。普通 Compose 文件 secrets 不等同于 Swarm 的加密秘密存储，也不要依赖其 `uid/gid/mode` 属性替宿主机文件改权限。

工具容器短暂以 root 运行以创建 / 修正宿主机目录权限，只保留处理这些权限需要的能力；业务应用始终以非 root 用户运行。整个初始化过程不打印数据库密码或凭据密钥。

再次运行工具会保留所有有效的原始文件。若三份文件只有部分存在、加密密钥长度错误或令牌损坏，工具会失败并要求恢复原文件，不会自动“修好”为一套新密钥。**保留旧数据库时不能重新生成加密密钥或数据库密码。**

## 更新已有部署

1. 先备份数据库、对应密钥和 `deploy/.env`。
2. 替换源码，保留原 `.env`、`.runtime/deploy-secrets/` 和 Docker 数据卷。
3. 执行以下命令：

```bash
docker compose build --pull web
docker compose run --rm --no-deps secrets-init
docker compose up -d --wait
docker compose ps
```

新的网络、环境变量和镜像需要 `up -d` 才会生效；单独 `restart` 不足以完成升级。迁移失败或健康检查不通过时，先查看 `docker compose logs --tail=150 web db`，不要删除数据库重新初始化。

已运行过旧版代理容器的部署，在切换到 1Panel 前单独停用旧代理容器，保留原数据库卷和部署密钥。

旧版在名为 `deploy` 的目录中运行时，项目名通常也是 `deploy`。继续保留原 `.env` 即可保留默认名称；如要明确设置，使用原来的 `COMPOSE_PROJECT_NAME=deploy`，或在命令中传 `-p deploy`。**不要因为新示例写了 `qidian-nav` 就改变已有项目名**，否则会创建新的空数据卷。可先用 `docker compose ls`、`docker volume ls` 确认旧名称。

定期更新 PostgreSQL 补丁镜像时，可以先备份，再运行 `docker compose pull db` 和 `docker compose up -d --wait`。PostgreSQL 仍保持 16 大版本；跨大版本升级需要单独的数据迁移方案。

## 备份与恢复

以下是 **Ubuntu Bash** 命令；`pg_dump` 在数据库容器中执行，无需主机安装数据库工具。先创建私有备份目录：

```bash
umask 077
backup_dir="../backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"

docker compose exec -T db pg_dump -U team_nav -d team_nav -Fc > "$backup_dir/database.dump"
docker compose run --rm -T --no-deps --entrypoint tar secrets-init \
  -C /secrets -czf - db-password credential.key setup-token > "$backup_dir/deploy-secrets.tar.gz"
cp .env "$backup_dir/deploy.env"
```

每条命令都应成功后再继续，确认备份文件不是空文件并将它们保存到服务器之外的受控位置。密钥归档本身包含原始密钥，不能作为公开附件、放进镜像或上传到公开仓库。

恢复时，数据库备份与密钥归档必须来自同一部署。先在**另一个项目目录、独立项目名和新数据卷**中恢复演练：将密钥归档恢复到该目录的 `.runtime/deploy-secrets/`，运行 `secrets-init` 校验，启动 `db`，再使用 `pg_restore` 导入。确认数据库完整后启动 `web`，并验证账号登录和旧凭据可读取，再切换正式流量。仅更换项目名而共用源码目录仍会共用宿主机密钥路径，因此演练应使用单独目录。

不要使用 `docker compose down -v` 做重启或升级，它会删除 Compose 数据卷。若需要回滚代码，先确认新版本是否已经运行数据库迁移；旧镜像不一定能读取迁移后的结构。

## 故障定位

| 现象 | 检查 |
| --- | --- |
| `secrets-init` 找不到镜像 | 先 `docker compose build --pull web`，或 `docker load` 导入与 `NAV_IMAGE` 同名的镜像 |
| 密钥文件不存在或挂载失败 | 首次 `up` 之前必须成功运行 `secrets-init`；已有部署缺文件时从对应备份恢复 |
| 应用提示 `Permission denied` | 重新运行 `secrets-init` 校验文件模式；不要直接给整个项目递归 `chmod 777` |
| 应用 HTTP 端口无法连接 | 检查 `NAV_WEB_BIND` / `NAV_WEB_PORT` 和 `docker compose ps` 中的端口映射 |
| 写入返回“请求来源不受信任” | 检查浏览器实际地址是否正是 `https://${NAV_DOMAIN}`；更改 `.env` 后重新 `up -d` |
| 健康检查失败 | 查看 `docker compose logs --tail=150 web db`，确认数据库启动、密码文件及迁移结果 |
| 更新后页面未变化 | 确认已经重建镜像并 `up -d`，再强制刷新浏览器 |
| 更新后像是新站点 | 先检查项目名及挂载卷是否与旧部署一致，不要直接重新创建账号或删除旧卷 |

这些文件用于 Ubuntu 的 Linux 容器部署。
