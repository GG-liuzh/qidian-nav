import unicodedata
from datetime import timedelta
from typing import Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query
from pypinyin import Style, lazy_pinyin
from sqlalchemy import and_, exists, func, or_, select, update

from .db import now
from .dependencies import DB, Current
from .models import (
    Category,
    Credential,
    Endpoint,
    Environment,
    Favorite,
    RecentVisit,
    Resource,
    ResourceRevision,
    User,
)
from .permissions import (
    audit,
    catalog_clause,
    category_visible,
    edit_category_resources,
    edit_resource,
    ensure_member,
    get_resource,
    internal_read_clause,
    internal_resource_access,
    manage_accounts,
    public_endpoint_clause,
    public_search_clause,
    read_clause,
)
from .schemas import ResourceInput, ResourceUpdate, Versioned

router = APIRouter(prefix="/api/v1")


def endpoint_data(db, endpoint):
    env = db.get(Environment, endpoint.environment_id) if endpoint.environment_id else None
    enabled = endpoint.enabled and not endpoint.deleted_at and (env is None or env.enabled)
    return {
        "id": endpoint.id,
        "environment_id": endpoint.environment_id,
        "env_key": env.key if env else "link",
        "env_label": env.label if env else "通用",
        "env_kind": env.kind if env else "link",
        "url": endpoint.url,
        "enabled": bool(enabled),
        "configured_enabled": endpoint.enabled,
        "disabled_reason": "环境已停用" if env and not env.enabled else "入口已停用" if not enabled else "",
    }


def public_resource_data(db, resource):
    category = db.get(Category, resource.category_id) if resource.category_id else None
    maintainer = db.get(User, resource.maintainer_id)
    endpoints = db.scalars(
        select(Endpoint)
        .outerjoin(Environment, Environment.id == Endpoint.environment_id)
        .where(Endpoint.resource_id == resource.id, public_endpoint_clause())
        .order_by(Environment.sort_order, Environment.label, Environment.id, Endpoint.id)
    ).all()
    return {
        "id": resource.id,
        "scope": resource.scope,
        "type": resource.type,
        "name": resource.name,
        "description": resource.description,
        "aliases": resource.aliases,
        "tags": resource.tags,
        "icon": resource.icon,
        "category_id": resource.category_id,
        "category_name": category.name if category else "未分组",
        "maintainer_name": maintainer.display_name if maintainer else "待移交",
        "endpoints": [
            {
                key: value
                for key, value in endpoint_data(db, row).items()
                if key not in ("configured_enabled", "disabled_reason")
            }
            for row in endpoints
        ],
        "is_public": True,
        "favorite": False,
        "can_edit": False,
        "can_manage_accounts": False,
        "can_grant": False,
    }


def serialize_resource(db, actor, resource):
    if not internal_resource_access(actor, resource):
        return {
            **public_resource_data(db, resource),
            "favorite": db.get(Favorite, (actor.id, resource.id)) is not None,
        }
    category = db.get(Category, resource.category_id) if resource.category_id else None
    owner = db.get(User, resource.maintainer_id)
    endpoints = db.scalars(
        select(Endpoint)
        .outerjoin(Environment, Environment.id == Endpoint.environment_id)
        .where(Endpoint.resource_id == resource.id, Endpoint.deleted_at.is_(None))
        .order_by(Environment.sort_order, Environment.label, Environment.id, Endpoint.id)
    ).all()
    return {
        "id": resource.id,
        "scope": resource.scope,
        "type": resource.type,
        "name": resource.name,
        "is_public": resource.is_public,
        "aliases": resource.aliases,
        "description": resource.description,
        "tags": resource.tags,
        "icon": resource.icon,
        "category_id": resource.category_id,
        "category_name": category.name if category else "未分组",
        "maintainer_id": resource.maintainer_id,
        "maintainer_name": owner.display_name if owner else "待移交",
        "status": resource.status,
        "version": resource.version,
        "updated_at": resource.updated_at.isoformat() + "Z",
        "deleted_at": resource.deleted_at.isoformat() + "Z" if resource.deleted_at else None,
        "endpoints": [endpoint_data(db, row) for row in endpoints],
        "favorite": db.get(Favorite, (actor.id, resource.id)) is not None,
        "can_edit": edit_resource(db, actor, resource),
        "can_manage_accounts": manage_accounts(db, actor, resource),
        "can_grant": False,
    }


def search_text(data):
    source = " ".join(
        [data.name, data.aliases, data.description, *data.tags, *(item.url for item in data.endpoints)]
    )
    pinyin = "".join(lazy_pinyin(data.name))
    initials = "".join(lazy_pinyin(data.name, style=Style.FIRST_LETTER))
    return unicodedata.normalize("NFKC", f"{source} {pinyin} {initials}").lower()


def validate_resource(db, actor, data, existing=None):
    if data.scope == "team" and not actor.in_workspace:
        raise HTTPException(403, "请先加入团队；个人使用可以保存到自己的导航。")
    if existing and (data.scope != existing.scope or data.type != existing.type):
        raise HTTPException(422, "编辑时不能改变资源类型或所属空间。")
    category = db.get(Category, data.category_id) if data.category_id else None
    if data.category_id and (
        not category or category.scope != data.scope or not category_visible(db, actor, category)
    ):
        raise HTTPException(422, "所选目录不存在或不属于当前空间。")
    if data.scope == "personal" and category and category.owner_user_id != actor.id:
        raise HTTPException(422, "请选择自己的个人分组。")
    if (
        data.scope == "team"
        and (not existing or data.category_id != existing.category_id)
        and not edit_category_resources(db, actor, category)
    ):
        raise HTTPException(403, "没有所选目录的维护权限。")
    if data.scope == "team":
        ensure_member(db, actor, data.maintainer_id or actor.id)
        if data.is_public != (existing.is_public if existing else False) and not actor.admin:
            raise HTTPException(403, "团队链接的公开状态由管理员设置。")
        if data.is_public and (not existing or not existing.is_public):
            if not actor.workspace or not actor.workspace.public_enabled:
                raise HTTPException(422, "请先在团队设置中开启游客访问。")
            if category and category.visibility == "restricted":
                raise HTTPException(422, "受限业务线中的资源不能公开。")
    if data.type == "bookmark" and (len(data.endpoints) != 1 or data.endpoints[0].environment_id is not None):
        raise HTTPException(422, "普通书签使用一个不区分环境的入口。")
    seen = set()
    for endpoint in data.endpoints:
        if data.type == "system":
            env = db.get(Environment, endpoint.environment_id) if endpoint.environment_id else None
            if not env or not (
                (
                    data.scope == "team"
                    and actor.in_workspace
                    and env.scope == "team"
                    and env.workspace_id == actor.workspace_id
                )
                or (data.scope == "personal" and env.scope == "personal" and env.owner_user_id == actor.id)
            ):
                raise HTTPException(422, "所选环境不存在或不属于当前空间。")
        if endpoint.environment_id in seen:
            raise HTTPException(422, "同一个环境只能配置一个主入口。")
        seen.add(endpoint.environment_id)


def suspend_credentials(db, endpoint_ids):
    if endpoint_ids:
        db.execute(
            update(Credential)
            .where(Credential.endpoint_id.in_(endpoint_ids), Credential.deleted_at.is_(None))
            .values(status="pending", version=Credential.version + 1)
        )


def origin(url):
    parsed = urlsplit(url)
    return (
        parsed.scheme.lower(),
        parsed.hostname.lower(),
        parsed.port or (443 if parsed.scheme == "https" else 80),
    )


def sync_endpoints(db, resource, data):
    existing = {
        row.environment_key: row
        for row in db.scalars(select(Endpoint).where(Endpoint.resource_id == resource.id))
    }
    submitted = set()
    suspended = []
    for value in data.endpoints:
        key = value.environment_id or "link"
        submitted.add(key)
        endpoint = existing.get(key)
        if endpoint:
            if (
                origin(endpoint.url) != origin(value.url)
                or (endpoint.enabled and not value.enabled)
                or endpoint.deleted_at
            ):
                suspended.append(endpoint.id)
            endpoint.url, endpoint.enabled, endpoint.deleted_at = value.url, value.enabled, None
        else:
            db.add(
                Endpoint(
                    resource_id=resource.id,
                    environment_id=value.environment_id,
                    environment_key=key,
                    url=value.url,
                    enabled=value.enabled,
                )
            )
    for key, endpoint in existing.items():
        if key not in submitted and endpoint.deleted_at is None:
            endpoint.deleted_at, endpoint.enabled = now(), False
            suspended.append(endpoint.id)
    suspend_credentials(db, suspended)
    db.flush()


def snapshot(db, resource, actor_id):
    if db.get(ResourceRevision, (resource.id, resource.version)):
        return
    fields = {
        key: getattr(resource, key)
        for key in (
            "scope",
            "type",
            "category_id",
            "name",
            "aliases",
            "description",
            "tags",
            "icon",
            "maintainer_id",
            "status",
            "is_public",
        )
    }
    fields["endpoints"] = [
        {"environment_id": row.environment_id, "url": row.url, "enabled": row.enabled}
        for row in db.scalars(
            select(Endpoint).where(Endpoint.resource_id == resource.id, Endpoint.deleted_at.is_(None))
        )
    ]
    db.add(
        ResourceRevision(
            resource_id=resource.id, version=resource.version, snapshot=fields, changed_by=actor_id
        )
    )


def create_resource_record(db, actor, data):
    validate_resource(db, actor, data)
    fields = data.model_dump(exclude={"endpoints", "maintainer_id"})
    resource = Resource(
        **fields,
        workspace_id=actor.workspace_id if data.scope == "team" else None,
        owner_user_id=actor.id if data.scope == "personal" else None,
        maintainer_id=(data.maintainer_id or actor.id) if data.scope == "team" else actor.id,
        search_text=search_text(data),
    )
    db.add(resource)
    db.flush()
    sync_endpoints(db, resource, data)
    snapshot(db, resource, actor.id)
    audit(db, actor, "resource.created", resource.id, resource)
    return resource


@router.post("/resources", status_code=201)
def create_resource(data: ResourceInput, db: DB, actor: Current):
    return serialize_resource(db, actor, create_resource_record(db, actor, data))


@router.get("/resources")
def resources(
    db: DB,
    actor: Current,
    view: Literal["team", "personal", "favorites", "recent"] = "team",
    q: str = Query(default="", max_length=200),
    url: str = Query(default="", max_length=4096),
    category_id: str | None = None,
    env: str | None = None,
    sort: Literal["default", "name", "updated"] = "default",
    status: Literal["active", "archived"] = "active",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
):
    query = select(Resource).where(
        read_clause(actor), Resource.deleted_at.is_(None), Resource.status == status
    )
    if view in ("team", "personal"):
        query = query.where(Resource.scope == view)
        if view == "personal":
            query = query.where(Resource.owner_user_id == actor.id)
        else:
            query = query.where(Resource.workspace_id == actor.workspace_id, actor.in_workspace)
    elif view == "favorites":
        query = query.where(
            exists(
                select(Favorite.resource_id).where(
                    Favorite.user_id == actor.id, Favorite.resource_id == Resource.id
                )
            )
        )
    else:
        query = query.where(
            exists(
                select(RecentVisit.endpoint_id)
                .join(Endpoint, Endpoint.id == RecentVisit.endpoint_id)
                .where(
                    RecentVisit.user_id == actor.id,
                    RecentVisit.visited_at > now() - timedelta(days=30),
                    Endpoint.resource_id == Resource.id,
                    Endpoint.deleted_at.is_(None),
                )
            )
        )
    if category_id:
        from .catalog import category_descendants

        query = query.where(Resource.category_id.in_(category_descendants(db, actor, category_id)))
    if url:
        query = query.where(
            exists(
                select(Endpoint.id)
                .where(
                    Endpoint.resource_id == Resource.id,
                    Endpoint.url == url,
                    Endpoint.deleted_at.is_(None),
                    or_(internal_read_clause(actor), public_endpoint_clause()),
                )
                .correlate(Resource)
            )
        )
    terms = unicodedata.normalize("NFKC", q).lower().split()
    for term in terms:
        matched_envs = db.scalars(
            select(Environment.id).where(
                catalog_clause(Environment, actor),
                or_(func.lower(Environment.key) == term, Environment.label == term),
            )
        ).all()
        if matched_envs:
            query = query.where(
                exists(
                    select(Endpoint.id).where(
                        Endpoint.resource_id == Resource.id,
                        Endpoint.environment_id.in_(matched_envs),
                        Endpoint.deleted_at.is_(None),
                        or_(internal_read_clause(actor), public_endpoint_clause()),
                    )
                )
            )
        else:
            query = query.where(
                or_(
                    and_(internal_read_clause(actor), Resource.search_text.contains(term, autoescape=True)),
                    public_search_clause(term),
                )
            )
    if env:
        query = query.where(
            or_(
                Resource.type == "bookmark",
                exists(
                    select(Endpoint.id).where(
                        Endpoint.resource_id == Resource.id,
                        Endpoint.environment_id == env,
                        Endpoint.deleted_at.is_(None),
                        or_(internal_read_clause(actor), public_endpoint_clause()),
                    )
                ),
            )
        )
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    if sort == "name":
        query = query.order_by(Resource.name, Resource.id)
    elif view == "recent":
        latest = (
            select(func.max(RecentVisit.visited_at))
            .join(Endpoint, Endpoint.id == RecentVisit.endpoint_id)
            .where(RecentVisit.user_id == actor.id, Endpoint.resource_id == Resource.id)
            .scalar_subquery()
        )
        query = query.order_by(latest.desc(), Resource.id)
    elif view == "favorites" and sort == "default":
        favorite_order = (
            select(Favorite.sort_order)
            .where(Favorite.user_id == actor.id, Favorite.resource_id == Resource.id)
            .scalar_subquery()
        )
        query = query.order_by(favorite_order, Resource.name, Resource.id)
    else:
        query = query.order_by(Resource.updated_at.desc(), Resource.id)
    rows = db.scalars(query.offset(offset).limit(limit)).all()
    return {
        "items": [serialize_resource(db, actor, row) for row in rows],
        "total": total,
        "next_offset": offset + limit if offset + limit < total else None,
    }


@router.get("/resources/{resource_id}")
def resource_detail(resource_id: str, db: DB, actor: Current):
    return serialize_resource(db, actor, get_resource(db, actor, resource_id))


def update_resource_record(db, actor, resource, data):
    validate_resource(db, actor, data, resource)
    fields = data.model_dump(exclude={"endpoints", "version", "maintainer_id"})
    result = db.execute(
        update(Resource)
        .where(Resource.id == resource.id, Resource.version == data.version, Resource.deleted_at.is_(None))
        .values(
            **fields,
            maintainer_id=(data.maintainer_id or actor.id) if resource.scope == "team" else actor.id,
            search_text=search_text(data),
            updated_at=now(),
            version=Resource.version + 1,
        )
    )
    if result.rowcount != 1:
        db.refresh(resource)
        raise HTTPException(
            409,
            {
                "message": "其他人已修改此资源，请比较最新版本后重新保存。",
                "current": serialize_resource(db, actor, resource),
            },
        )
    db.refresh(resource)
    sync_endpoints(db, resource, data)
    snapshot(db, resource, actor.id)
    audit(db, actor, "resource.updated", resource.id, resource, {"version": resource.version})
    return resource


@router.patch("/resources/{resource_id}")
def update_resource(resource_id: str, data: ResourceUpdate, db: DB, actor: Current):
    resource = get_resource(db, actor, resource_id, edit=True)
    return serialize_resource(db, actor, update_resource_record(db, actor, resource, data))


@router.delete("/resources/{resource_id}", status_code=204)
def delete_resource(resource_id: str, version: int, db: DB, actor: Current):
    resource = get_resource(db, actor, resource_id, edit=True)
    result = db.execute(
        update(Resource)
        .where(Resource.id == resource.id, Resource.version == version, Resource.deleted_at.is_(None))
        .values(deleted_at=now(), version=Resource.version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "资源已经修改，请刷新后再试。")
    suspend_credentials(db, list(db.scalars(select(Endpoint.id).where(Endpoint.resource_id == resource.id))))
    audit(db, actor, "resource.deleted", resource.id, resource)


@router.get("/trash")
def trash(db: DB, actor: Current):
    rows = db.scalars(
        select(Resource)
        .where(read_clause(actor), Resource.deleted_at > now() - timedelta(days=30))
        .order_by(Resource.deleted_at.desc())
    ).all()
    return [serialize_resource(db, actor, row) for row in rows if edit_resource(db, actor, row)]


@router.post("/trash/{resource_id}/restore")
def restore_resource(resource_id: str, data: Versioned, db: DB, actor: Current):
    resource = get_resource(db, actor, resource_id, edit=True, trash=True)
    if not resource.deleted_at or resource.deleted_at <= now() - timedelta(days=30):
        raise HTTPException(409, "此资源不在可恢复期限内。")
    result = db.execute(
        update(Resource)
        .where(Resource.id == resource.id, Resource.version == data.version)
        .values(deleted_at=None, version=Resource.version + 1, updated_at=now())
    )
    if result.rowcount != 1:
        raise HTTPException(409, "资源已经修改，请刷新后再试。")
    db.refresh(resource)
    audit(db, actor, "resource.restored", resource.id, resource)
    return serialize_resource(db, actor, resource)


@router.get("/resources/{resource_id}/revisions")
def revisions(resource_id: str, db: DB, actor: Current):
    resource = get_resource(db, actor, resource_id, edit=True)
    rows = db.scalars(
        select(ResourceRevision)
        .where(ResourceRevision.resource_id == resource.id)
        .order_by(ResourceRevision.version.desc())
        .limit(50)
    ).all()
    return [
        {
            "version": row.version,
            "snapshot": row.snapshot,
            "changed_by": db.get(User, row.changed_by).display_name,
            "created_at": row.created_at.isoformat() + "Z",
        }
        for row in rows
    ]


@router.post("/resources/{resource_id}/revisions/{revision}/restore")
def restore_revision(resource_id: str, revision: int, data: Versioned, db: DB, actor: Current):
    resource = get_resource(db, actor, resource_id, edit=True)
    previous = db.get(ResourceRevision, (resource.id, revision))
    if not previous:
        raise HTTPException(404, "版本不存在。")
    draft = ResourceUpdate(**previous.snapshot, version=data.version)
    return serialize_resource(db, actor, update_resource_record(db, actor, resource, draft))


@router.get("/resources/{resource_id}/grants")
@router.put("/resources/{resource_id}/grants/{user_id}")
def legacy_resource_grants(resource_id: str, db: DB, actor: Current, user_id: str | None = None):
    get_resource(db, actor, resource_id)
    raise HTTPException(410, "权限已统一按空间角色管理，请在成员管理中设置角色。")
