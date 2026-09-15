from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]


def project_path(path: Path) -> Path:
    path = path.expanduser()
    return (path if path.is_absolute() else ROOT / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TEAM_NAV_", env_file=ROOT / ".env", extra="ignore")

    database_url: str = "sqlite:///.runtime/team-nav.db"
    database_password_file: Path | None = None
    key_file: Path = Path(".runtime/secrets/credential.key")
    setup_token_file: Path = Path(".runtime/secrets/setup-token")
    origins: str = "http://127.0.0.1:4173,http://localhost:4173,http://127.0.0.1:4180,http://localhost:4180,http://127.0.0.1:5173,http://localhost:5173"
    allowed_hosts: str = "127.0.0.1,localhost"
    secure_cookies: bool = False
    environment: Literal["development", "production"] = "development"
    registration_enabled: bool = True
    session_hours: int = Field(default=12, ge=1, le=720)
    frontend_dist: Path = Path("frontend/dist")
    request_limit: int = Field(default=12 * 1024 * 1024, ge=1024, le=16 * 1024 * 1024)
    rate_limit_enabled: bool = True

    @field_validator("database_url")
    @classmethod
    def resolve_sqlite_path(cls, value):
        if not value.startswith("sqlite"):
            return value
        url = make_url(value)
        # Memory databases and SQLite's native file: URIs keep their own semantics.
        if not url.database or url.database == ":memory:" or url.database.startswith("file:"):
            return value
        return url.set(database=project_path(Path(url.database)).as_posix()).render_as_string(
            hide_password=False
        )

    @field_validator("database_password_file", "key_file", "setup_token_file", "frontend_dist")
    @classmethod
    def resolve_file_path(cls, value):
        return project_path(value) if value is not None else None

    @model_validator(mode="after")
    def production_boundaries(self):
        if self.environment != "production":
            return self
        if not self.secure_cookies or not self.rate_limit_enabled:
            raise ValueError("生产环境必须启用 Secure Cookie 和接口限流。")
        hosts = [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]
        if not hosts or any("*" in host for host in hosts):
            raise ValueError("生产环境必须配置明确的允许访问域名，不能使用通配符。")
        if not self.origin_list:
            raise ValueError("生产环境必须配置 HTTPS 请求来源。")
        for origin in self.origin_list:
            parsed = urlsplit(origin)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or "*" in parsed.netloc
                or parsed.username
                or parsed.password
                or parsed.path
                or parsed.query
                or parsed.fragment
                or parsed.hostname not in hosts
            ):
                raise ValueError("生产环境的请求来源必须是允许域名下的明确 HTTPS 地址。")
        return self

    @property
    def origin_list(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.origins.split(",") if origin.strip()]

    @property
    def resolved_database_url(self) -> str:
        if self.database_password_file:
            return (
                make_url(self.database_url)
                .set(password=self.database_password_file.read_text().strip())
                .render_as_string(hide_password=False)
            )
        return self.database_url
