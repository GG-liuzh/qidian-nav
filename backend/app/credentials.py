from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, update

from .db import now
from .dependencies import DB, Current
from .models import Credential, CredentialGrant, Endpoint, Environment
from .permissions import (
    audit,
    credential_capabilities,
    get_resource,
    internal_resource_access,
    manage_accounts,
    public_endpoint_clause,
)
from .schemas import (
    CredentialAccess,
    CredentialInput,
    CredentialUpdate,
)

router = APIRouter(prefix="/api/v1")


def endpoint_resource(db, actor, endpoint_id):
    endpoint = db.get(Endpoint, endpoint_id)
    if not endpoint or endpoint.deleted_at:
        raise HTTPException(404, "入口不存在。")
    resource = get_resource(db, actor, endpoint.resource_id)
    if not internal_resource_access(actor, resource) and not db.scalar(
        select(Endpoint.id).where(Endpoint.id == endpoint.id, public_endpoint_clause())
    ):
        raise HTTPException(404, "入口不存在或没有访问权限。")
    return endpoint, resource


def credential_record(db, actor, credential_id):
    credential = db.get(Credential, credential_id)
    if not credential or credential.deleted_at:
        raise HTTPException(404, "账号不存在。")
    endpoint, resource = endpoint_resource(db, actor, credential.endpoint_id)
    return credential, endpoint, resource


def credential_data(db, actor, resource, row):
    can_read, can_manage = credential_capabilities(db, actor, resource, row)
    return {
        "id": row.id,
        # Secrets are returned only by the audited, status-checked access endpoint.
        "username": None,
        "endpoint_id": row.endpoint_id,
        "name": row.name,
        "usage_note": row.usage_note,
        "status": "expired" if row.expires_at and row.expires_at <= now() else row.status,
        "expires_at": row.expires_at.isoformat() + "Z" if row.expires_at else None,
        "version": row.version,
        "can_read": can_read,
        "can_manage": can_manage,
        "can_grant": False,
    }


@router.get("/endpoints/{endpoint_id}/credentials")
def credentials(endpoint_id: str, db: DB, actor: Current):
    _, resource = endpoint_resource(db, actor, endpoint_id)
    rows = db.scalars(
        select(Credential)
        .where(Credential.endpoint_id == endpoint_id, Credential.deleted_at.is_(None))
        .order_by(Credential.name)
    ).all()
    return [
        credential_data(db, actor, resource, row)
        for row in rows
        if any(credential_capabilities(db, actor, resource, row))
    ]


@router.post("/endpoints/{endpoint_id}/credentials", status_code=201)
def create_credential(endpoint_id: str, data: CredentialInput, request: Request, db: DB, actor: Current):
    from .models import identifier

    _, resource = endpoint_resource(db, actor, endpoint_id)
    if not manage_accounts(db, actor, resource):
        raise HTTPException(403, "需要单独的账号管理权限。")
    if data.username is None or data.password is None:
        raise HTTPException(422, "新增账号时需要填写用户名与密码。")
    vault = request.app.state.vault
    credential_id = identifier()
    user_cipher, user_nonce = vault.encrypt(data.username, credential_id, endpoint_id, "username")
    pass_cipher, pass_nonce = vault.encrypt(data.password, credential_id, endpoint_id, "password")
    row = Credential(
        id=credential_id,
        endpoint_id=endpoint_id,
        name=data.name,
        usage_note=data.usage_note,
        expires_at=data.expires_at,
        status=data.status,
        maintainer_id=actor.id,
        key_id=vault.key_id,
        username_ciphertext=user_cipher,
        username_nonce=user_nonce,
        password_ciphertext=pass_cipher,
        password_nonce=pass_nonce,
    )
    db.add(row)
    db.flush()
    if resource.scope == "team":
        db.add(CredentialGrant(credential_id=row.id, user_id=actor.id, can_manage=True, can_read=False))
        db.flush()
    audit(db, actor, "credential.created", row.id, resource)
    return credential_data(db, actor, resource, row)


@router.patch("/credentials/{credential_id}")
def update_credential(credential_id: str, data: CredentialUpdate, request: Request, db: DB, actor: Current):
    row, _, resource = credential_record(db, actor, credential_id)
    if not credential_capabilities(db, actor, resource, row)[1]:
        raise HTTPException(403, "没有此账号的管理权限。")
    fields = data.model_dump(exclude={"username", "password", "version"})
    vault = request.app.state.vault
    if (
        row.key_id != vault.key_id
        and (data.username is not None or data.password is not None)
        and (data.username is None or data.password is None)
    ):
        raise HTTPException(409, "旧密钥不可用，请同时重新填写用户名与密码，或恢复原来的密钥。")
    for name in ("username", "password"):
        value = getattr(data, name)
        if value is not None:
            fields[f"{name}_ciphertext"], fields[f"{name}_nonce"] = vault.encrypt(
                value, row.id, row.endpoint_id, name
            )
    if data.username is not None or data.password is not None:
        fields["key_id"] = vault.key_id
    result = db.execute(
        update(Credential)
        .where(Credential.id == row.id, Credential.version == data.version, Credential.deleted_at.is_(None))
        .values(**fields, version=Credential.version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "账号已被修改，请重新打开编辑面板。")
    db.refresh(row)
    audit(db, actor, "credential.updated", row.id, resource, {"status": row.status})
    return credential_data(db, actor, resource, row)


@router.delete("/credentials/{credential_id}", status_code=204)
def delete_credential(credential_id: str, version: int, db: DB, actor: Current):
    row, _, resource = credential_record(db, actor, credential_id)
    if not credential_capabilities(db, actor, resource, row)[1]:
        raise HTTPException(403, "没有此账号的管理权限。")
    result = db.execute(
        update(Credential)
        .where(Credential.id == row.id, Credential.version == version, Credential.deleted_at.is_(None))
        .values(deleted_at=now(), status="disabled", version=Credential.version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "账号已经修改，请刷新后再试。")
    audit(db, actor, "credential.deleted", row.id, resource)


@router.post("/credentials/{credential_id}/access")
def access_credential(credential_id: str, data: CredentialAccess, request: Request, db: DB, actor: Current):
    from .security import rate_limit

    rate_limit(request, f"credential:{actor.id}", 40, 60)
    row, endpoint, resource = credential_record(db, actor, credential_id)
    environment = db.get(Environment, endpoint.environment_id) if endpoint.environment_id else None
    allowed = credential_capabilities(db, actor, resource, row)[0]
    active = (
        row.status == "active"
        and (not row.expires_at or row.expires_at > now())
        and endpoint.enabled
        and (not environment or environment.enabled)
        and resource.status == "active"
    )
    if not allowed or not active:
        audit(db, actor, "credential.access_denied", row.id, resource, {"field": data.field})
        db.commit()
        raise HTTPException(403, "无权读取此账号，或账号、入口已过期或停用。")
    value = request.app.state.vault.decrypt(row, data.field)
    audit(db, actor, "credential.access", row.id, resource, {"field": data.field, "purpose": data.purpose})
    return {"value": value}


@router.get("/credentials/{credential_id}/grants")
@router.put("/credentials/{credential_id}/grants/{user_id}")
def legacy_credential_grants(credential_id: str, db: DB, actor: Current, user_id: str | None = None):
    credential_record(db, actor, credential_id)
    raise HTTPException(410, "账号权限已统一按空间角色管理。普通成员可读取，维护人和管理员可维护。")
