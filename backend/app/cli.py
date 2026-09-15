import argparse
import os
import secrets
import shutil
import sqlite3
import subprocess
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from .config import ROOT, Settings


def migrate(settings):
    config = Config(str(ROOT / "backend" / "alembic.ini"))
    config.attributes["database_url"] = settings.resolved_database_url
    command.upgrade(config, "head")


def initialize(settings):
    for path, value in (
        (settings.key_file, secrets.token_bytes(32)),
        (settings.setup_token_file, secrets.token_urlsafe(36).encode()),
    ):
        if path.exists():
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            continue
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
    url = make_url(settings.resolved_database_url)
    if url.drivername.startswith("sqlite"):
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    migrate(settings)


def pg_tool(name):
    found = shutil.which(name)
    if found:
        return found
    program_files = os.environ.get("ProgramFiles")
    installations = Path(program_files) / "PostgreSQL" if program_files else None
    if installations and installations.is_dir():
        for folder in sorted(installations.iterdir(), reverse=True):
            candidate = folder / "bin" / f"{name}.exe"
            if candidate.is_file():
                return str(candidate)
    raise RuntimeError(f"需要安装 PostgreSQL 客户端工具：{name}")


def database_backup(settings, destination):
    path = Path(destination).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RuntimeError("备份文件已存在，请使用新文件名。")
    url = make_url(settings.resolved_database_url)
    if url.drivername.startswith("sqlite"):
        with sqlite3.connect(url.database) as source, sqlite3.connect(path) as target:
            source.backup(target)
    else:
        env = {**os.environ, "PGPASSWORD": url.password or ""}
        subprocess.run(
            [
                pg_tool("pg_dump"),
                "--host",
                url.host or "localhost",
                "--port",
                str(url.port or 5432),
                "--username",
                url.username or "postgres",
                "--dbname",
                url.database,
                "--format=custom",
                "--file",
                str(path),
            ],
            env=env,
            check=True,
        )
    print(f"数据库备份已写入 {path}。凭据保持密文，请另行保管 credential.key。")


def main():
    parser = argparse.ArgumentParser(description="栖点数据库与服务管理")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    subparsers.add_parser("migrate")
    serve = subparsers.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=4180)
    backup = subparsers.add_parser("backup")
    backup.add_argument("destination")
    args = parser.parse_args()
    settings = Settings()
    if args.command == "init":
        initialize(settings)
        print(f"初始化完成。首次安装令牌位于 {settings.setup_token_file}")
    elif args.command == "migrate":
        migrate(settings)
    elif args.command == "backup":
        database_backup(settings, args.destination)
    else:
        initialize(settings)
        if not settings.frontend_dist.is_dir():
            raise RuntimeError("尚未构建前端，请先在 frontend 目录执行 npm ci 和 npm run build。")
        import uvicorn

        uvicorn.run("app.main:create_app", factory=True, host=args.host, port=args.port, proxy_headers=False)


if __name__ == "__main__":
    main()
