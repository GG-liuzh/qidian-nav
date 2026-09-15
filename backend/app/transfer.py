import base64
import hashlib
import json
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from fastapi import APIRouter, HTTPException, Request
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .db import now
from .dependencies import DB, Current
from .models import (
    AuditEvent,
    Category,
    Credential,
    Endpoint,
    Environment,
    Favorite,
    Resource,
    Shortcut,
    TransferReceipt,
    identifier,
)
from .resources import create_resource_record
from .schemas import ResourceInput
from .security import rate_limit
from .transfer_schemas import Bundle, ExportInput, ImportInput

router = APIRouter(prefix="/api/v1/me/transfer")
AAD = b"qidian-personal-transfer-v1"


def transfer_key(passphrase, salt):
    return Scrypt(salt=salt, length=32, n=2**14, r=8, p=1).derive(passphrase.encode())


def unpack(data):
    encrypted = data.package.get("format") == "qidian-personal-encrypted-v1"
    try:
        if encrypted:
            if not data.passphrase:
                raise HTTPException(422, "此迁移文件已加密，请填写迁移口令。")
            salt = base64.b64decode(data.package["salt"], validate=True)
            nonce = base64.b64decode(data.package["nonce"], validate=True)
            if len(salt) != 16 or len(nonce) != 12:
                raise ValueError
            payload = AESGCM(transfer_key(data.passphrase, salt)).decrypt(
                nonce, base64.b64decode(data.package["ciphertext"], validate=True), AAD
            )
            parsed = json.loads(payload)
        else:
            parsed = data.package
        bundle = Bundle.model_validate(parsed)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(422, "迁移文件格式不正确、口令不匹配或文件已损坏。") from None
    category_map = {item.id: item for item in bundle.categories}
    environments = {item.id for item in bundle.environments}
    resource_ids = {item.id for item in bundle.resources}
    endpoint_ids = [item.id for resource in bundle.resources for item in resource.endpoints]
    if (
        len(category_map) != len(bundle.categories)
        or len(environments) != len(bundle.environments)
        or len(resource_ids) != len(bundle.resources)
        or len(endpoint_ids) != len(set(endpoint_ids))
    ):
        raise HTTPException(422, "迁移文件包含重复标识。")
    for category in bundle.categories:
        seen, current, depth = set(), category, 0
        while current:
            if current.id in seen:
                raise HTTPException(422, "个人分组不能循环引用。")
            seen.add(current.id)
            depth += 1
            if depth > 8:
                raise HTTPException(422, "个人分组最多支持 8 层。")
            if current.parent_id and current.parent_id not in category_map:
                raise HTTPException(422, "分组引用了迁移包之外的上级分组。")
            current = category_map.get(current.parent_id)
    for resource in bundle.resources:
        if resource.category_id and resource.category_id not in category_map:
            raise HTTPException(422, "资源引用了未包含的分组。")
        seen = set()
        for endpoint in resource.endpoints:
            if (
                endpoint.environment_id in seen
                or (resource.type == "system" and endpoint.environment_id not in environments)
                or (resource.type == "bookmark" and (endpoint.environment_id or len(resource.endpoints) != 1))
            ):
                raise HTTPException(422, "资源的环境配置不正确。")
            seen.add(endpoint.environment_id)
            if endpoint.credentials and not encrypted:
                raise HTTPException(422, "含私人账号的迁移文件必须使用加密格式。")
            if any(account.username is None or account.password is None for account in endpoint.credentials):
                raise HTTPException(422, "私人账号缺少必要字段。")
    if any(item not in resource_ids for item in bundle.favorites) or any(
        item not in endpoint_ids for item in bundle.shortcuts
    ):
        raise HTTPException(422, "收藏或快捷入口引用了迁移包之外的资源。")
    if len(bundle.favorites) != len(set(bundle.favorites)) or len(bundle.shortcuts) != len(
        set(bundle.shortcuts)
    ):
        raise HTTPException(422, "收藏或快捷入口包含重复标识。")
    return bundle


@router.post("/export")
def export_personal(data: ExportInput, request: Request, db: DB, actor: Current):
    rate_limit(request, f"transfer:{actor.id}", 10, 60)
    if data.include_credentials and not data.passphrase:
        raise HTTPException(422, "包含私人账号时，请设置至少 12 位的迁移口令。")
    resources = db.scalars(
        select(Resource)
        .where(Resource.owner_user_id == actor.id, Resource.deleted_at.is_(None))
        .order_by(Resource.created_at, Resource.id)
    ).all()
    categories = db.scalars(
        select(Category).where(Category.owner_user_id == actor.id).order_by(Category.sort_order)
    ).all()
    payload = {
        "format": "qidian-personal-v1",
        "package_id": identifier(),
        "created_at": now().isoformat() + "Z",
        "categories": [
            {key: getattr(row, key) for key in ("id", "name", "parent_id", "sort_order")}
            for row in categories
        ],
        "environments": [],
        "resources": [],
        "favorites": [],
        "shortcuts": [],
        "preferences": {
            key: actor.user.preferences[key]
            for key in ("theme", "layout", "record_visits")
            if key in actor.user.preferences
        },
    }
    environment_ids, endpoint_ids = set(), set()
    for resource in resources:
        item = {
            key: getattr(resource, key)
            for key in (
                "id",
                "name",
                "category_id",
                "type",
                "aliases",
                "description",
                "tags",
                "icon",
                "status",
                "is_public",
            )
        }
        item["endpoints"] = []
        for endpoint in db.scalars(
            select(Endpoint).where(Endpoint.resource_id == resource.id, Endpoint.deleted_at.is_(None))
        ):
            endpoint_ids.add(endpoint.id)
            if endpoint.environment_id:
                environment_ids.add(endpoint.environment_id)
            record = {key: getattr(endpoint, key) for key in ("id", "environment_id", "url", "enabled")}
            record["credentials"] = []
            if data.include_credentials:
                for account in db.scalars(
                    select(Credential).where(
                        Credential.endpoint_id == endpoint.id, Credential.deleted_at.is_(None)
                    )
                ):
                    record["credentials"].append(
                        {
                            "name": account.name,
                            "username": request.app.state.vault.decrypt(account, "username"),
                            "password": request.app.state.vault.decrypt(account, "password"),
                            "usage_note": account.usage_note,
                            "status": account.status,
                            "expires_at": account.expires_at.isoformat() + "Z"
                            if account.expires_at
                            else None,
                        }
                    )
            item["endpoints"].append(record)
        payload["resources"].append(item)
    for row in db.scalars(select(Environment).where(Environment.owner_user_id == actor.id)):
        environment_ids.add(row.id)
    for row in db.scalars(select(Environment).where(Environment.id.in_(environment_ids))):
        payload["environments"].append(
            {key: getattr(row, key) for key in ("id", "key", "label", "kind", "enabled", "sort_order")}
        )
    owned_ids = {row.id for row in resources}
    payload["favorites"] = [
        row.resource_id
        for row in db.scalars(
            select(Favorite).where(Favorite.user_id == actor.id).order_by(Favorite.sort_order)
        )
        if row.resource_id in owned_ids
    ]
    payload["shortcuts"] = [
        row.endpoint_id
        for row in db.scalars(
            select(Shortcut).where(Shortcut.user_id == actor.id).order_by(Shortcut.sort_order)
        )
        if row.endpoint_id in endpoint_ids
    ]
    try:
        bundle = Bundle.model_validate(payload)
    except ValidationError:
        raise HTTPException(422, "资料数量超过当前迁移包限制，请先分批整理。") from None
    raw = bundle.model_dump_json().encode()
    if len(raw) > 7 * 1024 * 1024:
        raise HTTPException(422, "资料超过单个迁移文件大小限制，请先整理为较小的资料集合。")
    db.add(
        AuditEvent(
            actor_id=actor.id,
            owner_user_id=actor.id,
            action="personal.exported",
            target_id=actor.id,
            detail={
                "resources": len(resources),
                "encrypted": bool(data.passphrase),
                "includes_credentials": data.include_credentials,
            },
        )
    )
    if data.passphrase:
        salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
        ciphertext = AESGCM(transfer_key(data.passphrase, salt)).encrypt(nonce, raw, AAD)
        return {
            "format": "qidian-personal-encrypted-v1",
            "salt": base64.b64encode(salt).decode(),
            "nonce": base64.b64encode(nonce).decode(),
            "ciphertext": base64.b64encode(ciphertext).decode(),
        }
    return payload


def duplicate_resources(db, actor, bundle):
    existing = {}
    for resource, endpoint in db.execute(
        select(Resource, Endpoint)
        .join(Endpoint, Endpoint.resource_id == Resource.id)
        .where(
            Resource.owner_user_id == actor.id, Resource.deleted_at.is_(None), Endpoint.deleted_at.is_(None)
        )
    ):
        existing.setdefault(endpoint.url, resource)
    return {
        row.id: next((existing[endpoint.url] for endpoint in row.endpoints if endpoint.url in existing), None)
        for row in bundle.resources
    }


def preview_data(db, actor, bundle):
    duplicates = duplicate_resources(db, actor, bundle)
    return {
        "package_id": bundle.package_id,
        "resources": len(bundle.resources),
        "categories": len(bundle.categories),
        "credentials": sum(
            len(endpoint.credentials) for row in bundle.resources for endpoint in row.endpoints
        ),
        "duplicates": [
            {"id": row.id, "name": row.name, "existing_name": duplicates[row.id].name}
            for row in bundle.resources
            if duplicates[row.id]
        ],
        "already_imported": db.get(TransferReceipt, (actor.id, bundle.package_id)) is not None,
    }


@router.post("/preview")
def preview(data: ImportInput, request: Request, db: DB, actor: Current):
    rate_limit(request, f"transfer:{actor.id}", 10, 60)
    return preview_data(db, actor, unpack(data))


@router.post("/import")
def import_personal(data: ImportInput, request: Request, db: DB, actor: Current, restore_preferences: bool = True):
    rate_limit(request, f"transfer:{actor.id}", 10, 60)
    bundle = unpack(data)
    checksum = hashlib.sha256(bundle.model_dump_json().encode()).hexdigest()
    receipt = db.get(TransferReceipt, (actor.id, bundle.package_id))
    if receipt:
        if receipt.summary.get("checksum") != checksum:
            raise HTTPException(409, "迁移包标识相同但内容发生变化，请重新导出。")
        return {**receipt.summary, "already_imported": True}
    receipt = TransferReceipt(user_id=actor.id, package_id=bundle.package_id, summary={})
    try:
        db.add(receipt)
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "该迁移包正在导入或已经导入，请刷新查看结果。") from None
    category_map, environment_map, resource_map, endpoint_map = {}, {}, {}, {}
    duplicates = duplicate_resources(db, actor, bundle)
    source_categories = {row.id: row for row in bundle.categories}
    def category_depth(row):
        depth = 0
        while row.parent_id:
            depth += 1
            row = source_categories[row.parent_id]
        return depth
    for source in sorted(bundle.categories, key=category_depth):
        parent_id = category_map.get(source.parent_id)
        row = db.scalar(
            select(Category).where(
                Category.owner_user_id == actor.id,
                Category.name == source.name,
                Category.parent_id == parent_id,
            )
        )
        if not row:
            row = Category(
                scope="personal",
                owner_user_id=actor.id,
                name=source.name,
                parent_id=parent_id,
                sort_order=source.sort_order,
            )
            db.add(row)
            db.flush()
        category_map[source.id] = row.id
    for source in bundle.environments:
        row = db.scalar(
            select(Environment).where(Environment.owner_user_id == actor.id, Environment.key == source.key)
        )
        if row and (row.label != source.label or row.kind != source.kind or row.enabled != source.enabled):
            row = None
            key = source.key[:15] + "-" + identifier()[:6]
        else:
            key = source.key
        if not row:
            row = Environment(
                scope="personal",
                owner_user_id=actor.id,
                key=key,
                label=source.label,
                kind=source.kind,
                enabled=source.enabled,
                sort_order=source.sort_order,
            )
            db.add(row)
            db.flush()
        environment_map[source.id] = row.id
    imported, skipped, accounts = 0, 0, 0
    for source in bundle.resources:
        existing = duplicates[source.id] if data.duplicates == "skip" else None
        if existing:
            resource_map[source.id] = existing.id
            target_endpoints = list(
                db.scalars(
                    select(Endpoint).where(Endpoint.resource_id == existing.id, Endpoint.deleted_at.is_(None))
                )
            )
            for endpoint in source.endpoints:
                match = next((row for row in target_endpoints if row.url == endpoint.url), None)
                if match:
                    endpoint_map[endpoint.id] = match.id
            skipped += 1
            continue
        payload = source.model_dump(exclude={"id", "endpoints", "category_id", "is_public"})
        draft = ResourceInput(
            **payload,
            scope="personal",
            category_id=category_map.get(source.category_id),
            is_public=False,
            endpoints=[
                {
                    "environment_id": environment_map.get(item.environment_id),
                    "url": item.url,
                    "enabled": item.enabled,
                }
                for item in source.endpoints
            ],
        )
        target = create_resource_record(db, actor, draft)
        resource_map[source.id] = target.id
        targets = {
            row.environment_id: row
            for row in db.scalars(select(Endpoint).where(Endpoint.resource_id == target.id))
        }
        for endpoint in source.endpoints:
            target_endpoint = targets[environment_map.get(endpoint.environment_id)]
            endpoint_map[endpoint.id] = target_endpoint.id
            for secret in endpoint.credentials:
                credential_id = identifier()
                vault = request.app.state.vault
                username_ciphertext, username_nonce = vault.encrypt(
                    secret.username, credential_id, target_endpoint.id, "username"
                )
                password_ciphertext, password_nonce = vault.encrypt(
                    secret.password, credential_id, target_endpoint.id, "password"
                )
                db.add(
                    Credential(
                        id=credential_id,
                        endpoint_id=target_endpoint.id,
                        name=secret.name,
                        usage_note=secret.usage_note,
                        status=secret.status,
                        expires_at=secret.expires_at,
                        maintainer_id=actor.id,
                        key_id=vault.key_id,
                        username_ciphertext=username_ciphertext,
                        username_nonce=username_nonce,
                        password_ciphertext=password_ciphertext,
                        password_nonce=password_nonce,
                    )
                )
                accounts += 1
        imported += 1
    for order, old_id in enumerate(bundle.favorites):
        new_id = resource_map[old_id]
        if not db.get(Favorite, (actor.id, new_id)):
            db.add(Favorite(user_id=actor.id, resource_id=new_id, sort_order=order))
    for order, old_id in enumerate(bundle.shortcuts):
        new_id = endpoint_map.get(old_id)
        if new_id and not db.get(Shortcut, (actor.id, new_id)):
            db.add(Shortcut(user_id=actor.id, endpoint_id=new_id, sort_order=order))
    if restore_preferences:
        actor.user.preferences = {**actor.user.preferences, **bundle.preferences.model_dump()}
    receipt.summary = {
        "imported": imported,
        "skipped": skipped,
        "credentials": accounts,
        "checksum": checksum,
    }
    db.add(
        AuditEvent(
            actor_id=actor.id,
            owner_user_id=actor.id,
            action="personal.imported",
            target_id=actor.id,
            detail={"resources": imported, "skipped": skipped, "credentials": accounts},
        )
    )
    return {**receipt.summary, "already_imported": False}
