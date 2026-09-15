import json

from fastapi import HTTPException
from sqlalchemy import String, and_, cast, exists, func, or_, select

from .models import AuditEvent, Category, Endpoint, Environment, Membership, Resource, User, Workspace


def public_endpoint_clause():
    return and_(
        Endpoint.deleted_at.is_(None),
        Endpoint.enabled.is_(True),
        or_(
            Endpoint.environment_id.is_(None),
            exists(
                select(Environment.id)
                .where(Environment.id == Endpoint.environment_id, Environment.enabled.is_(True))
                .correlate(Endpoint)
            ),
        ),
    )


def public_clause():
    workspace_public = exists(
        select(Workspace.id).where(
            Workspace.id == Resource.workspace_id,
            Workspace.public_enabled.is_(True),
            Workspace.active.is_(True),
        )
    )
    category_public = or_(
        Resource.category_id.is_(None),
        exists(
            select(Category.id).where(Category.id == Resource.category_id, Category.visibility == "workspace")
        ),
    )
    return and_(
        Resource.is_public.is_(True),
        Resource.deleted_at.is_(None),
        Resource.status == "active",
        exists(
            select(Endpoint.id)
            .where(Endpoint.resource_id == Resource.id, public_endpoint_clause())
            .correlate(Resource)
        ),
        or_(
            and_(
                Resource.scope == "personal",
                exists(select(User.id).where(User.id == Resource.owner_user_id, User.active.is_(True))),
            ),
            and_(Resource.scope == "team", workspace_public, category_public),
        ),
    )


def internal_read_clause(actor):
    return or_(
        and_(Resource.scope == "personal", Resource.owner_user_id == actor.id),
        and_(Resource.scope == "team", actor.in_workspace, Resource.workspace_id == actor.workspace_id),
    )


def internal_resource_access(actor, resource):
    return (resource.scope == "personal" and resource.owner_user_id == actor.id) or (
        resource.scope == "team" and actor.in_workspace and resource.workspace_id == actor.workspace_id
    )


def public_search_clause(term):
    # The internal search index also contains disabled URLs. Never use it for visitors.
    return or_(
        *(
            func.lower(column).contains(term, autoescape=True)
            for column in (Resource.name, Resource.aliases, Resource.description, cast(Resource.tags, String))
        ),
        func.lower(cast(Resource.tags, String)).contains(
            json.dumps(term, ensure_ascii=True)[1:-1].lower(), autoescape=True
        ),
        exists(
            select(Endpoint.id)
            .where(
                Endpoint.resource_id == Resource.id,
                public_endpoint_clause(),
                func.lower(Endpoint.url).contains(term, autoescape=True),
            )
            .correlate(Resource)
        ),
    )


def read_clause(actor):
    return or_(internal_read_clause(actor), public_clause())


def catalog_clause(model, actor):
    return or_(
        model.owner_user_id == actor.id,
        and_(model.scope == "team", actor.in_workspace, model.workspace_id == actor.workspace_id),
    )


def category_visible(db, actor, category):
    return category.owner_user_id == actor.id or (
        category.scope == "team" and actor.in_workspace and category.workspace_id == actor.workspace_id
    )


def edit_category_resources(db, actor, category):
    if category is None:
        return actor.can_edit_team
    return category.owner_user_id == actor.id or (
        category.scope == "team" and actor.can_edit_team and category.workspace_id == actor.workspace_id
    )


def edit_resource(db, actor, resource):
    return resource.owner_user_id == actor.id or (
        resource.scope == "team" and actor.can_edit_team and resource.workspace_id == actor.workspace_id
    )


def manage_accounts(db, actor, resource):
    return edit_resource(db, actor, resource)


def credential_capabilities(db, actor, resource, credential):
    if resource.owner_user_id == actor.id:
        return True, True
    if resource.scope == "team" and actor.in_workspace and resource.workspace_id == actor.workspace_id:
        return True, actor.can_edit_team
    return False, False


def get_resource(db, actor, resource_id, *, edit=False, trash=False):
    resource = db.scalar(select(Resource).where(Resource.id == resource_id, read_clause(actor)))
    if resource is None or (not trash and resource.deleted_at is not None):
        raise HTTPException(404, "资源不存在或没有访问权限。")
    if edit and not edit_resource(db, actor, resource):
        raise HTTPException(403, "此操作需要当前空间的业务维护人或管理员权限。")
    return resource


def ensure_member(db, actor, user_id):
    user = db.get(User, user_id)
    if user and user.active and user.is_superadmin and actor.in_workspace:
        return user
    membership = db.scalar(
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(
            Membership.workspace_id == actor.workspace_id,
            Membership.user_id == user_id,
            Membership.active.is_(True),
            User.active.is_(True),
        )
    )
    if not membership:
        raise HTTPException(422, "所选人员不是当前空间的有效成员。")
    return membership


def audit(db, actor, action, target_id, resource=None, detail=None):
    db.add(
        AuditEvent(
            actor_id=actor.id,
            action=action,
            target_id=target_id,
            resource_id=resource.id if resource else None,
            workspace_id=resource.workspace_id if resource else actor.workspace_id,
            owner_user_id=resource.owner_user_id
            if resource
            else (actor.id if not actor.in_workspace else None),
            detail=detail or {},
        )
    )
