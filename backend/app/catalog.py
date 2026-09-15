from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select, update

from .db import now
from .dependencies import DB, Current, require_admin
from .models import Category, Endpoint, Environment, Resource
from .permissions import (
    audit,
    catalog_clause,
    category_visible,
    edit_category_resources,
    read_clause,
)
from .schemas import (
    CategoryCreate,
    CategoryUpdate,
    EnvironmentCreate,
    EnvironmentUpdate,
)

router = APIRouter(prefix="/api/v1")


def category_data(db, actor, item, count=0):
    return {
        "id": item.id,
        "scope": item.scope,
        "name": item.name,
        "parent_id": item.parent_id,
        "visibility": item.visibility,
        "sort_order": item.sort_order,
        "version": item.version,
        "count": count,
        "can_edit_resources": edit_category_resources(db, actor, item),
    }


def environment_data(item):
    return {
        key: getattr(item, key)
        for key in ("id", "scope", "key", "label", "kind", "enabled", "sort_order", "version")
    }


@router.get("/catalog")
def catalog(db: DB, actor: Current):
    categories = db.scalars(
        select(Category).where(catalog_clause(Category, actor)).order_by(Category.sort_order, Category.name)
    ).all()
    counts = dict(
        db.execute(
            select(Resource.category_id, func.count())
            .where(read_clause(actor), Resource.deleted_at.is_(None), Resource.status == "active")
            .group_by(Resource.category_id)
        ).all()
    )
    environments = db.scalars(
        select(Environment)
        .where(catalog_clause(Environment, actor))
        .order_by(Environment.sort_order, Environment.label)
    ).all()
    return {
        "categories": [
            category_data(db, actor, row, counts.get(row.id, 0))
            for row in categories
            if category_visible(db, actor, row)
        ],
        "environments": [environment_data(row) for row in environments],
    }


def owned_catalog_item(db, actor, model, item_id):
    item = db.get(model, item_id)
    if not item or not (
        item.owner_user_id == actor.id
        or (item.scope == "team" and actor.in_workspace and item.workspace_id == actor.workspace_id)
    ):
        raise HTTPException(404, "配置不存在。")
    if item.scope == "team":
        require_admin(actor)
    return item


def validate_category(db, actor, data, existing=None):
    if data.scope == "team":
        require_admin(actor)
        if data.parent_id:
            raise HTTPException(422, "团队业务线使用一级目录。")
        if data.visibility != "workspace":
            raise HTTPException(422, "空间成员统一查看空间内容，不再设置受限目录。")
    if existing and data.scope != existing.scope:
        raise HTTPException(422, "不能改变目录所属空间。")
    if data.scope == "personal":
        rows = {row.id: row for row in db.scalars(select(Category).where(Category.owner_user_id == actor.id))}
        seen, parent_id, depth = set(), data.parent_id, 1
        while parent_id:
            if parent_id in seen or (existing and parent_id == existing.id):
                raise HTTPException(422, "分组不能移动到自己或自己的下级分组。")
            seen.add(parent_id)
            parent = rows.get(parent_id)
            if not parent:
                raise HTTPException(422, "请选择自己的个人分组。")
            parent_id, depth = parent.parent_id, depth + 1
        subtree = 0
        if existing:
            frontier = [existing.id]
            visited = set(frontier)
            while frontier:
                children = [
                    row.id for row in rows.values() if row.parent_id in frontier and row.id not in visited
                ]
                if not children:
                    break
                subtree += 1
                visited.update(children)
                frontier = children
        if depth + subtree > 8:
            raise HTTPException(422, "个人分组最多支持 8 层，请选择更上层的分组。")


def category_descendants(db, actor, category_id):
    rows = db.scalars(select(Category).where(catalog_clause(Category, actor))).all()
    ids = {category_id}
    while True:
        children = {row.id for row in rows if row.parent_id in ids} - ids
        if not children:
            return list(ids)
        ids.update(children)


@router.post("/categories", status_code=201)
def create_category(data: CategoryCreate, db: DB, actor: Current):
    validate_category(db, actor, data)
    item = Category(
        **data.model_dump(),
        workspace_id=actor.workspace_id if data.scope == "team" else None,
        owner_user_id=actor.id if data.scope == "personal" else None,
    )
    db.add(item)
    db.flush()
    if data.scope == "team":
        audit(db, actor, "category.created", item.id, detail={"name": item.name})
    return category_data(db, actor, item)


@router.patch("/categories/{item_id}")
def update_category(item_id: str, data: CategoryUpdate, db: DB, actor: Current):
    item = owned_catalog_item(db, actor, Category, item_id)
    validate_category(db, actor, data, item)
    result = db.execute(
        update(Category)
        .where(Category.id == item.id, Category.version == data.version)
        .values(**data.model_dump(exclude={"version"}), version=Category.version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "目录已被修改，请刷新后再试。")
    if item.scope == "team":
        audit(
            db, actor, "category.updated", item.id, detail={"name": data.name, "visibility": data.visibility}
        )
    db.refresh(item)
    return category_data(db, actor, item)


@router.delete("/categories/{item_id}", status_code=204)
def delete_category(item_id: str, version: int, db: DB, actor: Current, target_id: str | None = None):
    item = owned_catalog_item(db, actor, Category, item_id)
    locked = db.execute(
        update(Category)
        .where(Category.id == item.id, Category.version == version)
        .values(version=Category.version + 1)
    )
    if locked.rowcount != 1:
        raise HTTPException(409, "目录已被修改，请刷新后再试。")
    if db.scalar(select(Category.id).where(Category.parent_id == item.id)):
        raise HTTPException(409, "请先移动或删除下级分组。")
    used = db.scalar(select(Resource.id).where(Resource.category_id == item.id).limit(1))
    if target_id:
        target = owned_catalog_item(db, actor, Category, target_id)
        if target.id == item.id or target.scope != item.scope:
            raise HTTPException(422, "请选择同一空间内的其他目录。")
        db.execute(
            update(Resource)
            .where(Resource.category_id == item.id)
            .values(category_id=target.id, version=Resource.version + 1, updated_at=now())
        )
    elif used:
        raise HTTPException(409, "目录中还有资源（包括回收站中的资源），请选择迁移目录。")
    if item.scope == "team":
        audit(db, actor, "category.deleted", item.id, detail={"moved_to": target_id})
    from .models import Feedback

    db.execute(update(Feedback).where(Feedback.category_id == item.id).values(category_id=target_id))
    db.delete(item)


@router.get("/categories/{item_id}/grants")
@router.put("/categories/{item_id}/grants/{user_id}")
def legacy_category_grants(item_id: str, db: DB, actor: Current, user_id: str | None = None):
    owned_catalog_item(db, actor, Category, item_id)
    raise HTTPException(410, "目录权限已统一按空间角色管理。")


def validate_environment(db, actor, data, existing=None):
    if data.scope == "team":
        require_admin(actor)
    if data.key == "link":
        raise HTTPException(422, "link 是普通书签保留标识。")
    if existing and (data.scope != existing.scope or data.key != existing.key):
        raise HTTPException(422, "环境所属空间和稳定标识不可修改，可以修改显示名称。")
    query = select(Environment.id).where(
        Environment.key == data.key,
        Environment.workspace_id == actor.workspace_id
        if data.scope == "team"
        else Environment.owner_user_id == actor.id,
    )
    if existing:
        query = query.where(Environment.id != existing.id)
    if db.scalar(query):
        raise HTTPException(409, "该环境标识已经存在。")


@router.post("/environments", status_code=201)
def create_environment(data: EnvironmentCreate, db: DB, actor: Current):
    validate_environment(db, actor, data)
    item = Environment(
        **data.model_dump(),
        workspace_id=actor.workspace_id if data.scope == "team" else None,
        owner_user_id=actor.id if data.scope == "personal" else None,
    )
    db.add(item)
    db.flush()
    if item.scope == "team":
        audit(db, actor, "environment.created", item.id)
    return environment_data(item)


@router.patch("/environments/{item_id}")
def update_environment(item_id: str, data: EnvironmentUpdate, db: DB, actor: Current):
    item = owned_catalog_item(db, actor, Environment, item_id)
    validate_environment(db, actor, data, item)
    result = db.execute(
        update(Environment)
        .where(Environment.id == item.id, Environment.version == data.version)
        .values(**data.model_dump(exclude={"version"}), version=Environment.version + 1)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "环境配置已被修改，请刷新后再试。")
    if item.scope == "team":
        audit(
            db, actor, "environment.updated", item.id, detail={"enabled": data.enabled, "label": data.label}
        )
    db.refresh(item)
    return environment_data(item)


@router.delete("/environments/{item_id}", status_code=204)
def delete_environment(item_id: str, version: int, db: DB, actor: Current):
    item = owned_catalog_item(db, actor, Environment, item_id)
    if item.version != version:
        raise HTTPException(409, "环境配置已被修改，请刷新后再试。")
    if db.scalar(select(Endpoint.id).where(Endpoint.environment_id == item.id).limit(1)):
        raise HTTPException(409, "该环境已经被使用，请停用环境或先迁移所有引用。")
    if item.scope == "team":
        audit(db, actor, "environment.deleted", item.id)
    db.delete(item)
