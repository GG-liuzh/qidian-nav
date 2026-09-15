import unicodedata
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

Scope = Literal["team", "personal"]
Role = Literal["member", "maintainer", "admin"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def checked_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or any(ord(c) < 32 or c == "\\" for c in value)
        ):
            raise ValueError
        _ = parsed.port
    except ValueError:
        raise ValueError("请输入完整的 HTTP/HTTPS 地址，且不要在地址中嵌入账号密码。") from None
    return value


class Login(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    username: str = Field(min_length=2, max_length=80, pattern=r"^[a-zA-Z0-9_.@-]+$")
    password: str = Field(min_length=1, max_length=256)
    remember_me: bool = False

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value):
        return unicodedata.normalize("NFKC", value).strip().lower()

    @field_validator("password", mode="before")
    @classmethod
    def keep_password(cls, value):
        # Passwords use their exact bytes, including intentional whitespace.
        return value


class Register(Login):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=80)
    token: str | None = Field(default=None, min_length=20, max_length=160)

    @field_validator("display_name")
    @classmethod
    def nonempty_name(cls, value):
        if not value.strip():
            raise ValueError("请输入姓名。")
        return value.strip()


class Setup(Register):
    token: str = Field(min_length=20, max_length=160)
    workspace_name: str = Field(default="", max_length=80)
    public_enabled: bool = False
    collaboration_mode: Literal["maintainers", "members"] = "maintainers"

    @field_validator("workspace_name")
    @classmethod
    def nonempty_workspace(cls, value):
        return value.strip()


class Versioned(Input):
    version: int = Field(ge=1)


class CategoryCreate(Input):
    scope: Scope
    name: str = Field(min_length=1, max_length=80)
    parent_id: str | None = None
    visibility: Literal["workspace", "restricted"] = "workspace"
    sort_order: int = Field(default=0, ge=0, le=100000)


class CategoryUpdate(CategoryCreate, Versioned):
    pass


class EnvironmentCreate(Input):
    scope: Scope = "team"
    key: str = Field(min_length=1, max_length=24, pattern=r"^[a-z][a-z0-9_-]*$")
    label: str = Field(min_length=1, max_length=40)
    kind: Literal["dev", "test", "prod", "custom"] = "custom"
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0, le=100000)


class EnvironmentUpdate(EnvironmentCreate, Versioned):
    pass


class EndpointInput(Input):
    environment_id: str | None = None
    url: str = Field(min_length=1, max_length=4096)
    enabled: bool = True
    _check_url = field_validator("url")(checked_url)


class ResourceInput(Input):
    scope: Scope
    type: Literal["system", "bookmark"]
    is_public: bool = False
    category_id: str | None = None
    name: str = Field(min_length=1, max_length=120)
    aliases: str = Field(default="", max_length=240)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    icon: Literal[
        "globe", "package", "wallet", "boxes", "users", "shield", "terminal", "code", "book", "compass"
    ] = "globe"
    maintainer_id: str | None = None
    endpoints: list[EndpointInput] = Field(min_length=1, max_length=24)
    status: Literal["active", "archived"] = "active"

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values):
        if any(len(value.strip()) > 30 for value in values):
            raise ValueError("每个标签最多 30 个字符。")
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class ResourceUpdate(ResourceInput, Versioned):
    pass


class CredentialInput(Input):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=False)
    name: str = Field(min_length=1, max_length=80)
    username: str | None = Field(default=None, min_length=1, max_length=256)
    password: str | None = Field(default=None, min_length=1, max_length=4096)
    usage_note: str = Field(default="", max_length=1000)
    expires_at: datetime | None = None
    status: Literal["active", "pending", "disabled"] = "active"

    @field_validator("name")
    @classmethod
    def nonempty_credential_name(cls, value):
        if not value.strip():
            raise ValueError("请输入账号名称。")
        return value.strip()

    @field_validator("expires_at")
    @classmethod
    def utc_expiry(cls, value):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value and value.tzinfo else value


class CredentialUpdate(CredentialInput, Versioned):
    pass


class CredentialAccess(Input):
    field: Literal["username", "password"]
    purpose: Literal["copy", "reveal"]


class GrantInput(Input):
    can_read: bool = False
    can_edit: bool = False
    can_manage_accounts: bool = False


class AccountGrantInput(Input):
    can_read: bool = False
    can_manage: bool = False
