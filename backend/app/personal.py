from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import Field
from sqlalchemy import delete, func, or_, select

from .credentials import endpoint_resource
from .db import now
from .dependencies import DB, Current
from .models import Endpoint, Favorite, RecentVisit, Resource, Shortcut
from .permissions import get_resource, internal_read_clause, public_endpoint_clause, read_clause
from .resources import endpoint_data
from .schemas import Input

router = APIRouter(prefix="/api/v1")


@router.get("/me/favorites")
def favorite_ids(db: DB, actor: Current):
    return list(
        db.scalars(
            select(Favorite.resource_id)
            .join(Resource, Resource.id == Favorite.resource_id)
            .where(Favorite.user_id == actor.id, read_clause(actor), Resource.deleted_at.is_(None))
        )
    )


@router.put("/me/favorites/{resource_id}", status_code=204)
def favorite(resource_id: str, db: DB, actor: Current):
    get_resource(db, actor, resource_id)
    if not db.get(Favorite, (actor.id, resource_id)):
        order = db.scalar(select(func.max(Favorite.sort_order)).where(Favorite.user_id == actor.id)) or 0
        db.add(Favorite(user_id=actor.id, resource_id=resource_id, sort_order=order + 1))


@router.delete("/me/favorites/{resource_id}", status_code=204)
def unfavorite(resource_id: str, db: DB, actor: Current):
    db.execute(delete(Favorite).where(Favorite.user_id == actor.id, Favorite.resource_id == resource_id))


@router.get("/me/shortcuts")
def shortcuts(db: DB, actor: Current):
    rows = db.execute(
        select(Shortcut, Endpoint, Resource)
        .join(Endpoint, Endpoint.id == Shortcut.endpoint_id)
        .join(Resource, Resource.id == Endpoint.resource_id)
        .where(
            Shortcut.user_id == actor.id,
            read_clause(actor),
            Resource.deleted_at.is_(None),
            Endpoint.deleted_at.is_(None),
            or_(internal_read_clause(actor), public_endpoint_clause()),
        )
        .order_by(Shortcut.sort_order, Resource.name)
    ).all()
    return [
        {
            **endpoint_data(db, endpoint),
            "resource_id": resource.id,
            "name": resource.name,
            "icon": resource.icon,
            "sort_order": shortcut.sort_order,
            "enabled": bool(endpoint_data(db, endpoint)["enabled"] and resource.status == "active"),
            "disabled_reason": "资源已归档"
            if resource.status == "archived"
            else endpoint_data(db, endpoint)["disabled_reason"],
        }
        for shortcut, endpoint, resource in rows
    ]


@router.put("/me/shortcuts/{endpoint_id}", status_code=204)
def pin_shortcut(endpoint_id: str, db: DB, actor: Current):
    endpoint, _ = endpoint_resource(db, actor, endpoint_id)
    if not db.get(Shortcut, (actor.id, endpoint_id)):
        order = db.scalar(select(func.max(Shortcut.sort_order)).where(Shortcut.user_id == actor.id)) or 0
        db.add(Shortcut(user_id=actor.id, endpoint_id=endpoint_id, sort_order=order + 1))


@router.delete("/me/shortcuts/{endpoint_id}", status_code=204)
def unpin_shortcut(endpoint_id: str, db: DB, actor: Current):
    db.execute(delete(Shortcut).where(Shortcut.user_id == actor.id, Shortcut.endpoint_id == endpoint_id))


class Reorder(Input):
    ids: list[str] = Field(max_length=1000)


@router.put("/me/order/{kind}", status_code=204)
def reorder(kind: Literal["favorites", "shortcuts"], data: Reorder, db: DB, actor: Current):
    model = Favorite if kind == "favorites" else Shortcut
    if len(data.ids) != len(set(data.ids)):
        raise HTTPException(422, "排序不能包含重复项。")
    for index, item_id in enumerate(data.ids):
        item = db.get(model, (actor.id, item_id))
        if not item:
            raise HTTPException(404, "排序项不存在。")
        item.sort_order = index


class Visit(Input):
    endpoint_id: str


@router.post("/me/visits", status_code=204)
def visit(data: Visit, db: DB, actor: Current):
    endpoint, _ = endpoint_resource(db, actor, data.endpoint_id)
    if actor.user.preferences.get("record_visits", True):
        row = db.get(RecentVisit, (actor.id, endpoint.id)) or RecentVisit(
            user_id=actor.id, endpoint_id=endpoint.id
        )
        row.visited_at = now()
        db.add(row)
    db.execute(
        delete(RecentVisit).where(
            RecentVisit.user_id == actor.id, RecentVisit.visited_at < now() - timedelta(days=30)
        )
    )


@router.delete("/me/visits", status_code=204)
def clear_visits(db: DB, actor: Current):
    db.execute(delete(RecentVisit).where(RecentVisit.user_id == actor.id))


class Preferences(Input):
    theme: Literal["light", "dark", "system"] | None = None
    layout: Literal["grid", "list"] | None = None
    record_visits: bool | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=80)


@router.patch("/me/preferences")
def preferences(data: Preferences, db: DB, actor: Current):
    values = data.model_dump(exclude_none=True)
    if "display_name" in values:
        actor.user.display_name = values.pop("display_name")
    actor.user.preferences = {**actor.user.preferences, **values}
    return {"preferences": actor.user.preferences, "display_name": actor.user.display_name}
