from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlalchemy import select, update

from .dependencies import DB, Current, require_admin, require_superadmin, workspace_actor
from .models import Membership, SiteSettings, User, Workspace
from .permissions import audit
from .schemas import Input, Role

router = APIRouter(prefix="/api/v1")


def workspace_data(workspace, role="member"):
    return {"id": workspace.id, "name": workspace.name, "public_enabled": workspace.public_enabled,
            "active": workspace.active, "version": workspace.version, "role": role}


def available_workspaces(db, user):
    if user.is_superadmin:
        return [workspace_data(row, "admin") for row in db.scalars(select(Workspace).where(Workspace.active.is_(True)).order_by(Workspace.name, Workspace.id))]
    rows = db.execute(select(Workspace, Membership).join(Membership, Membership.workspace_id == Workspace.id).where(Membership.user_id == user.id, Membership.active.is_(True), Workspace.active.is_(True)).order_by(Workspace.name, Workspace.id)).all()
    return [workspace_data(workspace, member.role) for workspace, member in rows]


@router.get("/workspaces")
def workspaces(db: DB, actor: Current):
    return available_workspaces(db, actor.user)


@router.post("/workspaces/{workspace_id}/select")
def select_workspace(workspace_id: str, db: DB, actor: Current):
    from .auth import me_data
    selected = workspace_actor(db, actor.user, actor.session, workspace_id, explicit=True)
    if not selected.in_workspace:
        raise HTTPException(403, "你没有这个空间的成员资格，或空间已停用。")
    actor.session.active_workspace_id = workspace_id
    return me_data(db, selected)


class WorkspaceInput(Input):
    name: str = Field(min_length=1, max_length=80)
    public_enabled: bool = False
    version: int | None = Field(default=None, ge=1)


@router.patch("/workspace")
def update_workspace(data: WorkspaceInput, db: DB, actor: Current):
    require_admin(actor)
    result = db.execute(update(Workspace).where(Workspace.id == actor.workspace_id, Workspace.version == (data.version or actor.workspace.version)).values(name=data.name, public_enabled=data.public_enabled, version=Workspace.version+1))
    if result.rowcount != 1:
        raise HTTPException(409, "空间设置已被修改，请刷新后再试。")
    audit(db, actor, "workspace.updated", actor.workspace_id)
    db.refresh(actor.workspace)
    return workspace_data(actor.workspace, actor.role)


@router.post("/workspace", status_code=201)
def create_workspace(data: WorkspaceInput, db: DB, actor: Current):
    from .auth import me_data, seed_environments
    require_superadmin(actor)
    workspace = Workspace(name=data.name, public_enabled=data.public_enabled)
    db.add(workspace)
    db.flush()
    member = Membership(workspace_id=workspace.id, user_id=actor.id, role="admin")
    db.add(member)
    seed_environments(db, workspace_id=workspace.id)
    site = db.get(SiteSettings, "main")
    if site and not site.home_workspace_id:
        site.home_workspace_id = workspace.id
    actor.session.active_workspace_id = workspace.id
    db.flush()
    actor.membership, actor.workspace = member, workspace
    audit(db, actor, "workspace.created", workspace.id)
    return me_data(db, actor)


@router.post("/workspace/leave")
def leave_workspace(db: DB, actor: Current):
    from .auth import me_data
    if actor.membership:
        db.scalar(select(Workspace).where(Workspace.id == actor.workspace_id).with_for_update())
        if actor.membership.role == "admin":
            another = db.scalar(select(Membership.id).join(User, User.id == Membership.user_id).where(Membership.workspace_id == actor.workspace_id, Membership.role == "admin", Membership.active.is_(True), User.active.is_(True), Membership.user_id != actor.id).limit(1))
            if not another:
                raise HTTPException(409, "你是这个空间最后一位管理员，请先移交空间管理权限。")
        audit(db, actor, "member.left", actor.id)
        actor.membership.active = False
        actor.membership.version += 1
    actor.session.active_workspace_id = None
    actor.membership, actor.workspace = None, None
    return me_data(db, actor)


class AddMember(Input):
    username: str = Field(min_length=2, max_length=80)
    role: Role = "member"


@router.post("/workspace/members", status_code=201)
def add_existing_member(data: AddMember, db: DB, actor: Current):
    require_admin(actor)
    user = db.scalar(select(User).where(User.username == data.username.strip().lower(), User.active.is_(True)))
    if not user:
        raise HTTPException(404, "没有找到这个有效账号，请确认对方已注册及用户名是否正确。")
    member = db.scalar(select(Membership).where(Membership.workspace_id == actor.workspace_id, Membership.user_id == user.id))
    if member and member.active:
        raise HTTPException(409, "该用户已在空间中，请在成员列表修改角色。")
    if member:
        member.active, member.role, member.version = True, data.role, member.version+1
    else:
        db.add(Membership(workspace_id=actor.workspace_id, user_id=user.id, role=data.role))
    audit(db, actor, "member.added", user.id, detail={"role": data.role})
    return {"id": user.id, "display_name": user.display_name, "role": data.role}
