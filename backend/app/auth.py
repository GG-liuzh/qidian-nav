import secrets
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import Field
from sqlalchemy import case, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError

from .db import now
from .dependencies import DB, Current, require_admin, workspace_actor
from .models import (
    AccountReset,
    AuditEvent,
    Environment,
    Invitation,
    Membership,
    Session,
    SiteSettings,
    User,
    Workspace,
)
from .permissions import audit
from .schemas import Input, Login, Register, Role, Setup, Versioned
from .security import (
    DUMMY_HASH,
    constant_equal,
    digest,
    passwords,
    rate_limit,
    verify_password,
)

router = APIRouter(prefix="/api/v1")


def me_data(db, actor):
    from .workspaces import available_workspaces, workspace_data

    site = db.get(SiteSettings, "main")
    return {
        "id": actor.id,
        "username": actor.user.username,
        "display_name": actor.user.display_name,
        "role": actor.role,
        "workspace": workspace_data(actor.workspace, actor.role) if actor.in_workspace else None,
        "workspaces": available_workspaces(db, actor.user),
        "is_superadmin": actor.superadmin,
        "preferences": {"theme": "system", "layout": "grid", "record_visits": True, **actor.user.preferences},
        "csrf_token": actor.session.csrf_token,
        "is_site_owner": bool(site and site.owner_user_id == actor.id),
        "has_team": db.scalar(select(Workspace.id).where(Workspace.active.is_(True)).limit(1)) is not None,
        "has_recovery_code": actor.user.recovery_hash is not None,
        "public_profile_url": f"/#/u/{actor.id}",
    }


def start_session(request, response, db, user, membership, remember_me=False):
    token = secrets.token_urlsafe(48)
    hours = 24 * 30 if remember_me else request.app.state.settings.session_hours
    session = Session(
        token_hash=digest(token),
        user_id=user.id,
        csrf_token=secrets.token_urlsafe(32),
        expires_at=now() + timedelta(hours=hours),
        active_workspace_id=membership.workspace_id if membership else None,
    )
    db.add(session)
    db.execute(delete(Session).where(Session.expires_at < now()))
    response.set_cookie(
        "team_nav_session",
        token,
        httponly=True,
        secure=request.app.state.settings.secure_cookies,
        samesite="lax",
        max_age=hours * 3600,
        path="/",
    )
    return me_data(
        db,
        workspace_actor(db, user, session),
    )


def seed_environments(db, user_id=None, workspace_id=None):
    for order, (key, label) in enumerate((("dev", "开发"), ("test", "测试"), ("prod", "生产"))):
        db.add(
            Environment(
                scope="personal" if user_id else "team",
                owner_user_id=user_id,
                workspace_id=workspace_id,
                key=key,
                label=label,
                kind=key,
                sort_order=order,
            )
        )


def recovery_code(user):
    value = secrets.token_urlsafe(36)
    user.recovery_hash = digest(value)
    return value


def revoke_account_resets(db, user_id):
    db.execute(
        update(AccountReset)
        .where(AccountReset.user_id == user_id, AccountReset.used_at.is_(None))
        .values(expires_at=now())
    )


@router.get("/setup/status")
def setup_status(request: Request, db: DB):
    return {
        "needs_setup": db.get(SiteSettings, "main") is None,
        "registration_enabled": request.app.state.settings.registration_enabled,
    }


@router.post("/setup", status_code=201)
def setup(data: Setup, request: Request, response: Response, db: DB):
    rate_limit(request, f"setup:{request.client.host}", 10, 300)
    if db.get(SiteSettings, "main"):
        raise HTTPException(409, "此空间已经初始化，请登录。")
    path = request.app.state.settings.setup_token_file
    if not path.is_file() or not constant_equal(data.token, path.read_text().strip()):
        raise HTTPException(403, "安装令牌不正确。")
    user = User(
        username=data.username,
        display_name=data.display_name,
        password_hash=passwords.hash(data.password),
        is_superadmin=True,
    )
    recovery = recovery_code(user)
    membership = None
    try:
        db.add(user)
        db.flush()
        db.add(SiteSettings(id="main", owner_user_id=user.id))
        db.flush()
        seed_environments(db, user_id=user.id)
        if data.workspace_name:
            workspace = Workspace(name=data.workspace_name, public_enabled=data.public_enabled)
            db.add(workspace)
            db.flush()
            db.get(SiteSettings, "main").home_workspace_id = workspace.id
            membership = Membership(workspace_id=workspace.id, user_id=user.id, role="admin")
            db.add(membership)
            seed_environments(db, workspace_id=workspace.id)
        db.flush()
    except IntegrityError:
        raise HTTPException(409, "空间已被初始化，请刷新后登录。") from None
    db.add(AuditEvent(actor_id=user.id, owner_user_id=user.id, action="account.setup", target_id=user.id))
    return {
        **start_session(request, response, db, user, membership, data.remember_me),
        "recovery_code": recovery,
    }


@router.post("/auth/login")
def login(data: Login, request: Request, response: Response, db: DB):
    rate_limit(request, f"login-ip:{request.client.host}", 30, 300)
    rate_limit(request, f"login-user:{data.username}", 15, 300)
    user = db.scalar(select(User).where(User.username == data.username))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, data.password)
    membership = (
        db.scalar(
            select(Membership)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(Membership.user_id == user.id, Membership.active.is_(True), Workspace.active.is_(True))
            .order_by(Workspace.name, Workspace.id)
            .limit(1)
        )
        if user
        else None
    )
    if not valid or not user or not user.active:
        raise HTTPException(401, "用户名或密码不正确，或账户已停用。")
    if passwords.check_needs_rehash(user.password_hash):
        user.password_hash = passwords.hash(data.password)
    db.add(AuditEvent(actor_id=user.id, owner_user_id=user.id, action="auth.login", target_id=user.id))
    return start_session(request, response, db, user, membership, data.remember_me)


@router.get("/me")
def me(db: DB, actor: Current):
    return me_data(db, actor)


@router.post("/auth/logout", status_code=204)
def logout(response: Response, db: DB, actor: Current):
    db.delete(actor.session)
    response.delete_cookie("team_nav_session", path="/")


@router.post("/auth/logout-all", status_code=204)
def logout_all(response: Response, db: DB, actor: Current):
    db.execute(delete(Session).where(Session.user_id == actor.id))
    response.delete_cookie("team_nav_session", path="/")
    audit(db, actor, "auth.logout_all", actor.id)


class InviteInput(Input):
    role: Role = "member"
    hours: int = Field(default=72, ge=1, le=168)
    max_uses: int | None = Field(default=1, ge=1, le=10000, strict=True)


def issue_invitation(db, actor, *, role="member", hours=72, max_uses=1, kind="invite", user_id=None):
    token = secrets.token_urlsafe(36)
    item = Invitation(
        token_hash=digest(token),
        workspace_id=actor.workspace_id,
        role=role,
        kind=kind,
        user_id=user_id,
        created_by=actor.id,
        expires_at=now() + timedelta(hours=hours),
        max_uses=max_uses,
    )
    db.add(item)
    db.flush()
    audit(
        db,
        actor,
        f"auth.{kind}_created",
        item.id,
        detail={"role": role, "user_id": user_id, "max_uses": max_uses},
    )
    return {**invitation_data(item), "token": token}


def invitation_data(item):
    return {
        "id": item.id,
        "role": item.role,
        "expires_at": item.expires_at.isoformat() + "Z",
        "max_uses": item.max_uses,
        "used_count": item.used_count,
        "remaining_uses": None if item.max_uses is None else max(0, item.max_uses - item.used_count),
    }


@router.post("/invitations", status_code=201)
def invite(data: InviteInput, db: DB, actor: Current):
    require_admin(actor)
    return issue_invitation(db, actor, role=data.role, hours=data.hours, max_uses=data.max_uses)


@router.get("/invitations")
def invitations(db: DB, actor: Current):
    require_admin(actor)
    rows = db.scalars(
        select(Invitation)
        .where(
            Invitation.workspace_id == actor.workspace_id,
            Invitation.kind == "invite",
            Invitation.used_at.is_(None),
            Invitation.expires_at > now(),
            or_(Invitation.max_uses.is_(None), Invitation.used_count < Invitation.max_uses),
        )
        .order_by(Invitation.expires_at.desc())
    ).all()
    return [invitation_data(row) for row in rows]


@router.delete("/invitations/{item_id}", status_code=204)
def revoke_invite(item_id: str, db: DB, actor: Current):
    require_admin(actor)
    item = db.get(Invitation, item_id)
    if not item or item.workspace_id != actor.workspace_id:
        raise HTTPException(404, "邀请不存在。")
    item.expires_at = now()
    audit(db, actor, "auth.invite_revoked", item.id)


def consume_invitation(db, token, kind, consume=True):
    item = db.scalar(
        select(Invitation).where(Invitation.token_hash == digest(token), Invitation.kind == kind)
    )
    if (
        not item
        or item.used_at
        or item.expires_at <= now()
        or (item.max_uses is not None and item.used_count >= item.max_uses)
    ):
        raise HTTPException(400, "链接已失效或使用次数已用完，请联系管理员重新生成。")
    creator = db.get(User, item.created_by)
    workspace = db.get(Workspace, item.workspace_id)
    issuer = db.scalar(
        select(Membership).where(
            Membership.user_id == item.created_by,
            Membership.workspace_id == item.workspace_id,
            Membership.active.is_(True),
            Membership.role == "admin",
        )
    )
    if (
        not creator
        or not creator.active
        or not workspace
        or not workspace.active
        or not (creator.is_superadmin or issuer)
    ):
        raise HTTPException(400, "此链接已失效。")
    if not consume:
        return item
    result = db.execute(
        update(Invitation)
        .where(
            Invitation.id == item.id,
            Invitation.used_at.is_(None),
            Invitation.expires_at > now(),
            or_(Invitation.max_uses.is_(None), Invitation.used_count < Invitation.max_uses),
        )
        .values(
            used_count=Invitation.used_count + 1,
            used_at=case((Invitation.used_count + 1 >= Invitation.max_uses, now()), else_=None),
        )
    )
    if result.rowcount != 1:
        raise HTTPException(400, "链接已失效或使用次数已用完。")
    return item


@router.post("/auth/register", status_code=201)
def register(data: Register, request: Request, response: Response, db: DB):
    rate_limit(request, f"register:{request.client.host}", 15, 300)
    if not db.get(SiteSettings, "main"):
        raise HTTPException(409, "站点还未完成首次初始化。")
    if not request.app.state.settings.registration_enabled and not data.token:
        raise HTTPException(403, "站点已关闭自由注册，请使用空间管理员提供的邀请链接。")
    password_hash = passwords.hash(data.password)
    invitation = consume_invitation(db, data.token, "invite") if data.token else None
    if db.scalar(select(User.id).where(User.username == data.username)):
        raise HTTPException(409, "该用户名已被使用，请换一个用户名。")
    user = User(username=data.username, display_name=data.display_name, password_hash=password_hash)
    recovery = recovery_code(user)
    db.add(user)
    db.flush()
    seed_environments(db, user_id=user.id)
    membership = None
    if invitation:
        membership = Membership(workspace_id=invitation.workspace_id, user_id=user.id, role=invitation.role)
        db.add(membership)
    db.flush()
    db.add(
        AuditEvent(
            actor_id=user.id,
            workspace_id=invitation.workspace_id if invitation else None,
            owner_user_id=None if invitation else user.id,
            action="auth.join" if invitation else "account.registered",
            target_id=user.id,
        )
    )
    return {
        **start_session(request, response, db, user, membership, data.remember_me),
        "recovery_code": recovery,
    }


class PasswordChange(Input):
    model_config = {"extra": "forbid", "str_strip_whitespace": False}
    old_password: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=12, max_length=256)


@router.post("/me/password", status_code=204)
def change_password(data: PasswordChange, request: Request, response: Response, db: DB, actor: Current):
    rate_limit(request, f"reauth:{actor.id}", 10, 300)
    if not verify_password(actor.user.password_hash, data.old_password):
        raise HTTPException(400, "当前密码不正确。")
    actor.user.password_hash = passwords.hash(data.password)
    actor.user.version += 1
    db.execute(delete(Session).where(Session.user_id == actor.id))
    revoke_account_resets(db, actor.id)
    response.delete_cookie("team_nav_session", path="/")
    audit(db, actor, "auth.password_changed", actor.id)


class PasswordReset(Login):
    model_config = {"extra": "forbid", "str_strip_whitespace": False}
    recovery_code: str = Field(min_length=20, max_length=160)
    password: str = Field(min_length=12, max_length=256)


@router.post("/auth/reset")
def reset_password(data: PasswordReset, request: Request, db: DB):
    rate_limit(request, f"reset:{request.client.host}", 15, 300)
    encoded = passwords.hash(data.password)
    user = db.scalar(select(User).where(User.username == data.username))
    if (
        not user
        or not user.active
        or not user.recovery_hash
        or not constant_equal(user.recovery_hash, digest(data.recovery_code))
    ):
        raise HTTPException(400, "用户名或恢复码不正确。")
    code = secrets.token_urlsafe(36)
    changed = db.execute(
        update(User)
        .where(User.id == user.id, User.recovery_hash == digest(data.recovery_code))
        .values(password_hash=encoded, recovery_hash=digest(code), version=User.version + 1)
    )
    if changed.rowcount != 1:
        raise HTTPException(400, "恢复码已使用，请使用最新的恢复码。")
    db.execute(delete(Session).where(Session.user_id == user.id))
    revoke_account_resets(db, user.id)
    db.add(
        AuditEvent(actor_id=user.id, owner_user_id=user.id, action="auth.password_reset", target_id=user.id)
    )
    return {"recovery_code": code}


@router.get("/members")
def members(db: DB, actor: Current):
    query = (
        select(User, Membership)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.workspace_id == actor.workspace_id, User.deleted_at.is_(None))
    )
    if not actor.admin:
        query = query.where(Membership.active.is_(True), User.active.is_(True))
    return [
        {
            "id": user.id,
            "display_name": user.display_name,
            "role": member.role,
            "is_superadmin": user.is_superadmin,
            **(
                {
                    "username": user.username,
                    "active": member.active and user.active,
                    "version": member.version,
                }
                if actor.admin
                else {}
            ),
        }
        for user, member in db.execute(query.order_by(User.display_name))
    ]


class MemberChange(Versioned):
    role: Role
    active: bool


@router.patch("/members/{user_id}")
def update_member(user_id: str, data: MemberChange, db: DB, actor: Current):
    require_admin(actor)
    db.scalar(select(Workspace).where(Workspace.id == actor.workspace_id).with_for_update())
    member = db.scalar(
        select(Membership).where(Membership.workspace_id == actor.workspace_id, Membership.user_id == user_id)
    )
    user = db.get(User, user_id)
    if not member or not user or user.deleted_at is not None:
        raise HTTPException(404, "成员不存在。")
    if member.role == "admin" and member.active and (not data.active or data.role != "admin"):
        count = db.scalar(
            select(func.count())
            .select_from(Membership)
            .join(User, User.id == Membership.user_id)
            .where(
                Membership.workspace_id == actor.workspace_id,
                Membership.role == "admin",
                Membership.active.is_(True),
                User.active.is_(True),
            )
        )
        if count <= 1:
            raise HTTPException(409, "必须保留至少一位有效的空间管理员。")
    result = db.execute(
        update(Membership)
        .where(Membership.id == member.id, Membership.version == data.version)
        .values(role=data.role, active=data.active, version=Membership.version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "成员信息已经更新，请刷新后再试。")
    if not data.active or data.role != "admin":
        db.execute(
            update(Invitation)
            .where(
                Invitation.created_by == user_id,
                Invitation.workspace_id == actor.workspace_id,
                Invitation.used_at.is_(None),
            )
            .values(expires_at=now())
        )
    audit(db, actor, "member.updated", user_id, detail={"role": data.role, "active": data.active})
    return {"ok": True}


@router.post("/members/{user_id}/reset")
def member_reset(user_id: str, db: DB, actor: Current):
    require_admin(actor)
    raise HTTPException(
        403, "空间管理员不能重置个人账号密码。请使用恢复码，或联系站点超级管理员生成重置链接。"
    )


class JoinInput(Input):
    token: str = Field(min_length=20, max_length=160)


@router.post("/auth/invitation-info")
def invitation_info(data: JoinInput, request: Request, db: DB):
    rate_limit(request, f"invite-preview:{request.client.host}", 30, 300)
    item = consume_invitation(db, data.token, "invite", consume=False)
    return {
        **invitation_data(item),
        "name": db.get(Workspace, item.workspace_id).name,
    }


@router.post("/auth/join")
def join_existing(data: JoinInput, db: DB, actor: Current):
    invitation = consume_invitation(db, data.token, "invite")
    member = db.scalar(
        select(Membership).where(
            Membership.workspace_id == invitation.workspace_id, Membership.user_id == actor.id
        )
    )
    if member and member.active:
        raise HTTPException(409, "你已经是该团队的成员。")
    if member:
        member.active, member.role, member.version = True, invitation.role, member.version + 1
    else:
        member = Membership(workspace_id=invitation.workspace_id, user_id=actor.id, role=invitation.role)
        db.add(member)
    db.flush()
    actor.membership, actor.workspace = member, db.get(Workspace, member.workspace_id)
    actor.session.active_workspace_id = member.workspace_id
    audit(db, actor, "auth.join", actor.id)
    return me_data(db, actor)


class RecoveryInput(Input):
    model_config = {"extra": "forbid", "str_strip_whitespace": False}
    password: str = Field(min_length=1, max_length=256)


@router.post("/me/recovery-code")
def create_recovery_code(data: RecoveryInput, request: Request, db: DB, actor: Current):
    rate_limit(request, f"reauth:{actor.id}", 10, 300)
    if not verify_password(actor.user.password_hash, data.password):
        raise HTTPException(400, "当前密码不正确。")
    code = recovery_code(actor.user)
    db.add(
        AuditEvent(
            actor_id=actor.id, owner_user_id=actor.id, action="account.recovery_renewed", target_id=actor.id
        )
    )
    return {"recovery_code": code}
