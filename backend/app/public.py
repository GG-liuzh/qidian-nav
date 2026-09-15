import unicodedata

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from .dependencies import DB
from .models import Category, Endpoint, Environment, Resource, SiteSettings, User, Workspace
from .permissions import public_clause, public_endpoint_clause, public_search_clause
from .resources import public_resource_data

router = APIRouter(prefix="/api/v1/public")


@router.get("/navigation")
def navigation(
    db: DB,
    owner: str | None = None,
    workspace_id: str | None = None,
    q: str = Query(default="", max_length=200),
    category_id: str | None = None,
    env: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=48, ge=1, le=100),
):
    site = db.get(SiteSettings, "main")
    if owner and workspace_id:
        raise HTTPException(422, "请选择一个个人导航页或空间。")
    workspace = (
        db.get(Workspace, workspace_id or site.home_workspace_id)
        if workspace_id or (site and site.home_workspace_id)
        else None
    )
    if workspace_id and (not workspace or not workspace.active or not workspace.public_enabled):
        raise HTTPException(404, "这个空间未开放公开导航，或已经停用。")
    if workspace and not workspace.active:
        workspace = None
    spaces = [
        {"id": row.id, "name": row.name}
        for row in db.scalars(
            select(Workspace)
            .where(Workspace.active.is_(True), Workspace.public_enabled.is_(True))
            .order_by(Workspace.name, Workspace.id)
        )
    ]
    if owner:
        person = db.get(User, owner)
        has_public = db.scalar(
            select(Resource.id).where(Resource.owner_user_id == owner, public_clause()).limit(1)
        )
        if not person or not person.active or not has_public:
            raise HTTPException(404, "这个个人导航页尚未公开，或不存在。")
        scope, title, owner_id = "personal", f"{person.display_name}的导航", person.id
    elif workspace:
        scope, title, owner_id = "team", workspace.name if workspace.public_enabled else "栖点导航", None
    else:
        person = db.get(User, site.owner_user_id) if site else None
        if person and not db.scalar(
            select(Resource.id).where(Resource.owner_user_id == person.id, public_clause()).limit(1)
        ):
            person = None
        scope, title, owner_id = (
            "personal",
            f"{person.display_name}的导航" if person else "栖点导航",
            person.id if person else None,
        )
    base = select(Resource).where(public_clause(), Resource.scope == scope)
    base = (
        base.where(Resource.workspace_id == workspace.id)
        if scope == "team"
        else base.where(Resource.owner_user_id == owner_id, owner_id is not None)
    )
    category_counts = db.execute(
        select(Resource.category_id, func.count())
        .where(Resource.id.in_(base.with_only_columns(Resource.id)))
        .group_by(Resource.category_id)
    ).all()
    categories = []
    for identifier, count in category_counts:
        category = db.get(Category, identifier) if identifier else None
        if category:
            categories.append(
                {"id": category.id, "name": category.name, "count": count, "sort_order": category.sort_order}
            )
    environment_ids = select(Endpoint.environment_id).where(
        Endpoint.resource_id.in_(base.with_only_columns(Resource.id)), public_endpoint_clause()
    )
    environments = {
        row.id: {"id": row.id, "label": row.label, "kind": row.kind, "key": row.key}
        for row in db.scalars(
            select(Environment)
            .where(Environment.id.in_(environment_ids))
            .order_by(Environment.sort_order, Environment.label, Environment.id)
        )
    }
    if category_id:
        base = base.where(Resource.category_id == category_id)
    for term in unicodedata.normalize("NFKC", q).lower().split():
        matching_envs = [
            key
            for key, value in environments.items()
            if term in (value["key"].lower(), value["label"].lower())
        ]
        if matching_envs:
            base = base.where(
                Resource.id.in_(
                    select(Endpoint.resource_id).where(
                        Endpoint.environment_id.in_(matching_envs), public_endpoint_clause()
                    )
                )
            )
        else:
            base = base.where(public_search_clause(term))
    if env:
        matching = select(Endpoint.resource_id).where(
            Endpoint.environment_id == env, public_endpoint_clause()
        )
        base = base.where((Resource.type == "bookmark") | Resource.id.in_(matching))
    total = db.scalar(select(func.count()).select_from(base.subquery()))
    rows = db.scalars(
        base.order_by(Resource.updated_at.desc(), Resource.id).offset(offset).limit(limit)
    ).all()
    items = [public_resource_data(db, resource) for resource in rows]
    return {
        "title": title,
        "workspace_id": workspace.id if workspace and workspace.public_enabled and not owner else None,
        "spaces": spaces,
        "scope": scope,
        "owner_id": owner_id,
        "items": items,
        "categories": sorted(categories, key=lambda row: (row["sort_order"], row["name"])),
        "environments": list(environments.values()),
        "total": total,
        "next_offset": offset + limit if offset + limit < total else None,
    }
