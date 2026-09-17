import secrets
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import Field
from sqlalchemy import delete, func, or_, select, update

from .db import now
from .dependencies import DB, Current, require_superadmin
from .models import AccountReset, AuditEvent, Invitation, Membership, Session, SiteSettings, User, Workspace
from .schemas import Input, Versioned
from .security import digest, passwords, rate_limit
from .workspaces import workspace_data

router = APIRouter(prefix="/api/v1")


def site_audit(db, actor, action, target, detail=None):
    db.add(AuditEvent(actor_id=actor.id, action=action, target_id=target, detail=detail or {}))


@router.get("/admin/users")
def users(
    db: DB,
    actor: Current,
    q: str = Query(default="", max_length=80),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
):
    require_superadmin(actor)
    query = select(User).where(User.deleted_at.is_(None))
    if q.strip():
        query = query.where(
            or_(
                User.username.contains(q.strip(), autoescape=True),
                User.display_name.contains(q.strip(), autoescape=True),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(User.created_at, User.id).offset(offset).limit(limit)).all()
    items = []
    for row in rows:
        spaces = db.execute(
            select(Workspace, Membership)
            .join(Membership, Membership.workspace_id == Workspace.id)
            .where(Membership.user_id == row.id, Membership.active.is_(True))
        ).all()
        items.append(
            {
                "id": row.id,
                "username": row.username,
                "display_name": row.display_name,
                "active": row.active,
                "is_superadmin": row.is_superadmin,
                "version": row.version,
                "created_at": row.created_at.isoformat() + "Z",
                "workspaces": [
                    {"id": space.id, "name": space.name, "role": member.role} for space, member in spaces
                ],
            }
        )
    return {"items": items, "total": total, "next_offset": offset + limit if offset + limit < total else None}


class UserChange(Versioned):
    active: bool
    is_superadmin: bool


def require_other_space_admins(db, user_id):
    # Match member-management locking, so concurrent removals cannot orphan a space.
    spaces = db.scalars(
        select(Workspace)
        .join(Membership, Membership.workspace_id == Workspace.id)
        .where(Membership.user_id == user_id, Membership.active.is_(True), Membership.role == "admin")
        .order_by(Workspace.id)
        .with_for_update(of=Workspace)
    ).all()
    for space in spaces:
        another = db.scalar(
            select(Membership.id)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.workspace_id == space.id,
                Membership.user_id != user_id,
                Membership.active.is_(True),
                Membership.role == "admin",
                User.active.is_(True),
            )
            .limit(1)
        )
        if not another:
            raise HTTPException(409, f"请先为“{space.name}”指定其他有效管理员，再停用该账号。")


def revoke_user_access(db, user_id):
    db.execute(delete(Session).where(Session.user_id == user_id))
    db.execute(
        update(Invitation)
        .where(or_(Invitation.created_by == user_id, Invitation.user_id == user_id))
        .values(expires_at=now())
    )
    db.execute(
        update(AccountReset)
        .where(
            or_(AccountReset.user_id == user_id, AccountReset.created_by == user_id),
            AccountReset.used_at.is_(None),
        )
        .values(expires_at=now())
    )


@router.patch("/admin/users/{user_id}")
def update_user(user_id: str, data: UserChange, db: DB, actor: Current):
    require_superadmin(actor)
    db.scalar(select(SiteSettings).where(SiteSettings.id == "main").with_for_update())
    user = db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise HTTPException(404, "用户不存在。")
    if user.id == actor.id and (not data.active or not data.is_superadmin):
        raise HTTPException(
            409, "不能在当前会话停用自己或移除自己的超级管理员身份，请由另一位超级管理员操作。"
        )
    if user.active and user.is_superadmin and (not data.active or not data.is_superadmin):
        others = db.scalar(
            select(User.id)
            .where(User.id != user.id, User.active.is_(True), User.is_superadmin.is_(True))
            .limit(1)
        )
        if not others:
            raise HTTPException(409, "必须保留至少一位有效的超级管理员。")
    if not data.active:
        require_other_space_admins(db, user.id)
    result = db.execute(
        update(User)
        .where(User.id == user.id, User.version == data.version, User.deleted_at.is_(None))
        .values(active=data.active, is_superadmin=data.is_superadmin, version=User.version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "用户信息已修改，请刷新后重试。")
    revoke_user_access(db, user.id)
    site_audit(
        db, actor, "site.user_updated", user.id, {"active": data.active, "is_superadmin": data.is_superadmin}
    )
    return {"ok": True}


@router.post("/admin/users/{user_id}/recovery")
def issue_reset(user_id: str, request: Request, db: DB, actor: Current):
    require_superadmin(actor)
    rate_limit(request, f"admin-reset:{actor.id}", 15, 300)
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(404, "该用户不存在或已停用。")
    token = secrets.token_urlsafe(36)
    db.execute(
        update(AccountReset)
        .where(AccountReset.user_id == user_id, AccountReset.used_at.is_(None))
        .values(expires_at=now())
    )
    expires_at = now() + timedelta(hours=1)
    db.add(
        AccountReset(token_hash=digest(token), user_id=user_id, created_by=actor.id, expires_at=expires_at)
    )
    site_audit(db, actor, "site.reset_issued", user_id)
    return {"token": token, "expires_at": expires_at.isoformat() + "Z"}


class ResetByToken(Input):
    model_config = {"extra": "forbid", "str_strip_whitespace": False}
    token: str = Field(min_length=20, max_length=160)
    password: str = Field(min_length=12, max_length=256)


@router.post("/auth/reset-token")
def reset_by_token(data: ResetByToken, request: Request, response: Response, db: DB):
    from .auth import recovery_code, revoke_account_resets

    rate_limit(request, f"reset-link:{request.client.host}", 15, 300)
    record = db.scalar(select(AccountReset).where(AccountReset.token_hash == digest(data.token)))
    user = db.get(User, record.user_id) if record else None
    issuer = db.get(User, record.created_by) if record else None
    if (
        not record
        or record.used_at
        or record.expires_at <= now()
        or not user
        or not user.active
        or not issuer
        or not issuer.active
        or not issuer.is_superadmin
    ):
        raise HTTPException(400, "重置链接已失效，请联系超级管理员重新生成。")
    changed = db.execute(
        update(AccountReset)
        .where(AccountReset.id == record.id, AccountReset.used_at.is_(None), AccountReset.expires_at > now())
        .values(used_at=now())
    )
    if changed.rowcount != 1:
        raise HTTPException(400, "重置链接已经使用。")
    user.password_hash = passwords.hash(data.password)
    user.version += 1
    code = recovery_code(user)
    db.execute(delete(Session).where(Session.user_id == user.id))
    revoke_account_resets(db, user.id)
    db.add(
        AuditEvent(actor_id=user.id, owner_user_id=user.id, action="auth.password_reset", target_id=user.id)
    )
    response.delete_cookie("team_nav_session", path="/")
    return {"username": user.username, "recovery_code": code}


@router.get("/admin/workspaces")
def all_workspaces(db: DB, actor: Current):
    require_superadmin(actor)
    site = db.get(SiteSettings, "main")
    return [
        {
            **workspace_data(row, "admin"),
            "member_count": db.scalar(
                select(func.count())
                .select_from(Membership)
                .where(Membership.workspace_id == row.id, Membership.active.is_(True))
            ),
            "is_home": bool(site and site.home_workspace_id == row.id),
        }
        for row in db.scalars(select(Workspace).order_by(Workspace.name, Workspace.id))
    ]


class WorkspaceState(Versioned):
    active: bool


@router.patch("/admin/workspaces/{workspace_id}")
def set_workspace_state(workspace_id: str, data: WorkspaceState, db: DB, actor: Current):
    require_superadmin(actor)
    result = db.execute(
        update(Workspace)
        .where(Workspace.id == workspace_id, Workspace.version == data.version)
        .values(active=data.active, version=Workspace.version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "空间不存在或已更新，请刷新后重试。")
    site_audit(db, actor, "site.workspace_updated", workspace_id, {"active": data.active})
    return {"ok": True}


@router.put("/admin/home/{workspace_id}")
def set_home(workspace_id: str, db: DB, actor: Current):
    require_superadmin(actor)
    workspace = db.get(Workspace, workspace_id)
    if not workspace or not workspace.active:
        raise HTTPException(404, "请选择有效的空间。")
    db.get(SiteSettings, "main").home_workspace_id = workspace_id
    site_audit(db, actor, "site.home_updated", workspace_id)
    return {"ok": True}


@router.get("/admin/events")
def admin_events(db: DB, actor: Current):
    require_superadmin(actor)
    rows = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.action.startswith("site."))
        .order_by(AuditEvent.created_at.desc())
        .limit(100)
    ).all()
    return [
        {
            "id": row.id,
            "actor_name": db.get(User, row.actor_id).display_name,
            "action": row.action,
            "target_id": row.target_id,
            "created_at": row.created_at.isoformat() + "Z",
            "detail": row.detail,
        }
        for row in rows
    ]
