from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from .db import now
from .models import Membership, Session, User, Workspace
from .security import constant_equal, digest


def get_db(request: Request):
    with request.app.state.sessions() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise


DB = Annotated[DbSession, Depends(get_db, scope="function")]


@dataclass
class Actor:
    user: User
    membership: Membership | None
    session: Session
    workspace: Workspace | None = None

    @property
    def id(self):
        return self.user.id

    @property
    def workspace_id(self):
        return self.workspace.id if self.workspace else None

    @property
    def superadmin(self):
        return bool(self.user.is_superadmin)

    @property
    def in_workspace(self):
        return bool(self.workspace and self.workspace.active and (self.membership or self.superadmin))

    @property
    def admin(self):
        return bool(self.in_workspace and (self.superadmin or self.membership.role == "admin"))

    @property
    def role(self):
        return "admin" if self.admin else self.membership.role if self.in_workspace else "personal"

    @property
    def can_edit_team(self):
        return self.in_workspace and self.role in ("admin", "maintainer")


def workspace_actor(db, user, session, workspace_id=None, *, explicit=False):
    selected = workspace_id or session.active_workspace_id
    workspace = db.get(Workspace, selected) if selected else None
    member = db.scalar(select(Membership).where(Membership.user_id == user.id, Membership.workspace_id == selected, Membership.active.is_(True))) if selected else None
    if workspace and workspace.active and (member or user.is_superadmin):
        return Actor(user, member, session, workspace)
    if explicit:
        return Actor(user, None, session)
    first = db.execute(select(Membership, Workspace).join(Workspace, Workspace.id == Membership.workspace_id).where(Membership.user_id == user.id, Membership.active.is_(True), Workspace.active.is_(True)).order_by(Workspace.name, Workspace.id).limit(1)).first()
    return Actor(user, first[0] if first else None, session, first[1] if first else None)


def current_actor(request: Request, db: DB) -> Actor:
    token = request.cookies.get("team_nav_session", "")
    session = db.get(Session, digest(token)) if token else None
    if not session or session.expires_at <= now():
        raise HTTPException(401, "请先登录。")
    user = db.get(User, session.user_id)
    if not user or not user.active:
        raise HTTPException(401, "账户已停用，请联系管理员。")
    if request.method not in ("GET", "HEAD", "OPTIONS") and not constant_equal(
        request.headers.get("X-CSRF-Token", ""), session.csrf_token
    ):
        raise HTTPException(403, "登录校验已失效，请刷新页面后重试。")
    requested = request.headers.get("X-Workspace-ID") or (request.query_params.get("workspace_id") if request.url.path == "/api/v1/exports" else None)
    # Profile refresh must let a removed member recover to their personal account.
    explicit = bool(requested and request.url.path not in ("/api/v1/me", "/api/v1/workspaces") and not request.url.path.startswith("/api/v1/admin/"))
    return workspace_actor(db, user, session, requested, explicit=explicit)


Current = Annotated[Actor, Depends(current_actor)]


def require_admin(actor: Actor):
    if not actor.admin:
        raise HTTPException(403, "此操作需要空间管理员权限。")


def require_superadmin(actor: Actor):
    if not actor.superadmin:
        raise HTTPException(403, "此操作需要站点超级管理员权限。")
