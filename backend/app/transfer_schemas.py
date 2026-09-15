from typing import Literal

from pydantic import Field, field_validator

from .schemas import CredentialInput, Input, ResourceInput, checked_url


class TransferCategory(Input):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=80)
    parent_id: str | None = None
    sort_order: int = Field(default=0, ge=0, le=100000)


class TransferEnvironment(Input):
    id: str = Field(min_length=1, max_length=64)
    key: str = Field(min_length=1, max_length=24, pattern=r"^[a-z][a-z0-9_-]*$")
    label: str = Field(min_length=1, max_length=40)
    kind: Literal["dev", "test", "prod", "custom"]
    enabled: bool = True
    sort_order: int = Field(default=0, ge=0, le=100000)


class TransferEndpoint(Input):
    id: str = Field(min_length=1, max_length=64)
    environment_id: str | None = None
    url: str = Field(min_length=1, max_length=4096)
    enabled: bool = True
    credentials: list[CredentialInput] = Field(default_factory=list, max_length=50)
    _url = field_validator("url")(checked_url)


class TransferResource(Input):
    id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=120)
    category_id: str | None = None
    type: Literal["system", "bookmark"]
    aliases: str = Field(default="", max_length=240)
    description: str = Field(default="", max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=12)
    icon: Literal[
        "globe", "package", "wallet", "boxes", "users", "shield", "terminal", "code", "book", "compass"
    ] = "globe"
    status: Literal["active", "archived"] = "active"
    is_public: bool = False
    endpoints: list[TransferEndpoint] = Field(min_length=1, max_length=24)

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values):
        return ResourceInput.clean_tags(values)


class TransferPreferences(Input):
    theme: Literal["light", "dark", "system"] = "system"
    layout: Literal["grid", "list"] = "grid"
    record_visits: bool = True


class Bundle(Input):
    format: Literal["qidian-personal-v1"]
    package_id: str = Field(min_length=32, max_length=64, pattern=r"^[a-zA-Z0-9-]+$")
    created_at: str = Field(max_length=40)
    categories: list[TransferCategory] = Field(max_length=2000)
    environments: list[TransferEnvironment] = Field(max_length=200)
    resources: list[TransferResource] = Field(max_length=2000)
    favorites: list[str] = Field(default_factory=list, max_length=2000)
    shortcuts: list[str] = Field(default_factory=list, max_length=4000)
    preferences: TransferPreferences = Field(default_factory=TransferPreferences)


class ExportInput(Input):
    model_config = {"extra": "forbid", "str_strip_whitespace": False}
    include_credentials: bool = False
    passphrase: str | None = Field(default=None, min_length=12, max_length=256)


class ImportInput(Input):
    model_config = {"extra": "forbid", "str_strip_whitespace": False}
    package: dict
    passphrase: str | None = Field(default=None, min_length=1, max_length=256)
    duplicates: Literal["skip", "copy"] = "skip"
