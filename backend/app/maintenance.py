import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import Field
from sqlalchemy import and_, or_, select, update

from .dependencies import DB, Current
from .models import (
    AuditEvent,
    Category,
    Feedback,
    Resource,
    User,
)
from .permissions import (
    audit,
    category_visible,
    get_resource,
    read_clause,
)
from .resources import create_resource_record, serialize_resource
from .schemas import Input, ResourceInput, Versioned, checked_url

router = APIRouter(prefix="/api/v1")


@router.get("/audit-events")
def audit_events(db: DB, actor: Current):
    allowed = or_(
        AuditEvent.owner_user_id == actor.id,
        and_(
            actor.in_workspace,
            AuditEvent.workspace_id == actor.workspace_id,
            or_(
                actor.admin,
                AuditEvent.actor_id == actor.id,
                and_(actor.role == "maintainer", AuditEvent.resource_id.is_not(None)),
            ),
        ),
    )
    rows = db.scalars(
        select(AuditEvent).where(allowed).order_by(AuditEvent.created_at.desc()).limit(200)
    ).all()
    return [
        {
            "id": row.id,
            "actor_name": db.get(User, row.actor_id).display_name,
            "action": row.action,
            "target_id": row.target_id,
            "target_name": db.get(Resource, row.resource_id).name if row.resource_id else "",
            "detail": row.detail,
            "created_at": row.created_at.isoformat() + "Z",
        }
        for row in rows
    ]


class FeedbackInput(Input):
    kind: Literal["add", "edit", "broken", "account"]
    resource_id: str | None = None
    category_id: str | None = None
    title: str = Field(min_length=1, max_length=120)
    url: str = Field(default="", max_length=4096)
    description: str = Field(default="", max_length=2000)


def feedback_data(db, item, can_handle):
    return {
        **{
            key: getattr(item, key)
            for key in (
                "id",
                "kind",
                "title",
                "url",
                "description",
                "status",
                "resolution",
                "resource_id",
                "category_id",
                "version",
                "created_by",
            )
        },
        "creator_name": db.get(User, item.created_by).display_name,
        "created_at": item.created_at.isoformat() + "Z",
        "can_handle": can_handle,
    }


def handle_feedback(db, actor, item):
    return bool(actor.can_edit_team and item.workspace_id == actor.workspace_id)


@router.post("/feedback", status_code=201)
def create_feedback(data: FeedbackInput, db: DB, actor: Current):
    if not actor.in_workspace:
        raise HTTPException(403, "请先通过邀请加入团队，再参与团队建议与维护。")
    if data.resource_id:
        resource = get_resource(db, actor, data.resource_id)
        if resource.scope != "team" or resource.workspace_id != actor.workspace_id:
            raise HTTPException(422, "私人内容请在个人空间维护。推荐到团队时仅填写选定的链接信息。")
    if data.category_id:
        category = db.get(Category, data.category_id)
        if not category or category.scope != "team" or not category_visible(db, actor, category):
            raise HTTPException(422, "所选业务线不可用。")
    if data.url:
        try:
            checked_url(data.url)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
    if data.kind == "add" and not data.url:
        raise HTTPException(422, "请填写建议添加的链接地址。")
    item = Feedback(**data.model_dump(), workspace_id=actor.workspace_id, created_by=actor.id)
    db.add(item)
    db.flush()
    audit(db, actor, "feedback.created", item.id)
    return feedback_data(db, item, handle_feedback(db, actor, item))


@router.get("/feedback")
def feedback(db: DB, actor: Current):
    rows = db.scalars(
        select(Feedback)
        .where(Feedback.workspace_id == actor.workspace_id)
        .order_by(Feedback.created_at.desc())
    ).all()
    result = []
    for row in rows:
        handle = handle_feedback(db, actor, row)
        if row.created_by == actor.id or handle:
            result.append(feedback_data(db, row, handle))
    return result[:200]


class Resolution(Versioned):
    status: Literal["accepted", "rejected", "withdrawn"]
    resolution: str = Field(default="", max_length=1000)
    resource: ResourceInput | None = None


@router.post("/feedback/{item_id}/resolve")
def resolve(item_id: str, data: Resolution, db: DB, actor: Current):
    item = db.get(Feedback, item_id)
    if not item or item.workspace_id != actor.workspace_id:
        raise HTTPException(404, "反馈不存在。")
    can_handle = handle_feedback(db, actor, item)
    if (data.status == "withdrawn" and item.created_by != actor.id) or (
        data.status != "withdrawn" and not can_handle
    ):
        raise HTTPException(403, "没有此反馈的处理权限。")
    result = db.execute(
        update(Feedback)
        .where(Feedback.id == item.id, Feedback.status == "open", Feedback.version == data.version)
        .values(
            status=data.status, resolution=data.resolution, resolved_by=actor.id, version=Feedback.version + 1
        )
    )
    if result.rowcount != 1:
        raise HTTPException(409, "反馈已被处理，请刷新。")
    if item.kind == "add" and data.status == "accepted":
        if not data.resource or data.resource.scope != "team":
            raise HTTPException(422, "采用建议时请确认要发布到团队的链接信息。")
        resource = create_resource_record(db, actor, data.resource)
        item.resource_id = resource.id
    audit(db, actor, "feedback.resolved", item.id, detail={"status": data.status})
    db.refresh(item)
    return feedback_data(db, item, can_handle)


@router.get("/exports")
def export(
    db: DB,
    actor: Current,
    scope: Literal["team", "personal"] = "personal",
    format: Literal["json", "csv"] = "json",
):
    rows = db.scalars(
        select(Resource)
        .where(
            read_clause(actor),
            Resource.scope == scope,
            Resource.owner_user_id == actor.id
            if scope == "personal"
            else Resource.workspace_id == actor.workspace_id,
            Resource.deleted_at.is_(None),
        )
        .order_by(Resource.name)
    ).all()
    payload = []
    for row in rows:
        resource = serialize_resource(db, actor, row)
        payload.append(
            {
                key: resource[key]
                for key in ("name", "type", "description", "aliases", "tags", "category_name")
            }
            | {
                "endpoints": [
                    {key: endpoint[key] for key in ("env_key", "env_label", "url")}
                    for endpoint in resource["endpoints"]
                ]
            }
        )
    if format == "json":
        return Response(
            json.dumps({"format": "team-nav-links-v1", "resources": payload}, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="qidian-nav-links.json"'},
        )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["name", "category", "environment", "url", "description"])

    def cell(value):
        text = str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text

    for resource in payload:
        for endpoint in resource["endpoints"]:
            writer.writerow(
                [
                    cell(resource["name"]),
                    cell(resource["category_name"]),
                    cell(endpoint["env_label"]),
                    cell(endpoint["url"]),
                    cell(resource["description"]),
                ]
            )
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="qidian-nav-links.csv"'},
    )
