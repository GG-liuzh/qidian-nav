from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text
from test_independent_navigation import register

from app.config import ROOT
from app.db import Base, now
from app.models import AccountReset, Invitation, Membership, Resource, Session, User


def guest(h):
    return TestClient(h.app, headers={"Origin": "http://testserver"})


def invitation(h, **values):
    response = h.admin.post("/api/v1/invitations", json=values)
    assert response.status_code == 201, response.text
    return response.json()


def signup(client, token, username):
    return client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "display_name": username,
            "password": "invited-test-password",
            "token": token,
        },
    )


def test_invitation_capacity_shared_by_new_and_existing_accounts(h):
    existing, _ = register(h)
    invite = invitation(h, max_uses=2)
    payload = {"token": invite["token"]}
    for _ in range(2):
        assert existing.post("/api/v1/auth/invitation-info", json=payload).json()["remaining_uses"] == 2
    assert existing.post("/api/v1/auth/join", json=payload).status_code == 200
    assert existing.post("/api/v1/auth/join", json=payload).status_code == 409
    assert signup(guest(h), invite["token"], "admin").status_code == 409
    listed = next(row for row in h.admin.get("/api/v1/invitations").json() if row["id"] == invite["id"])
    assert listed["used_count"] == 1 and listed["remaining_uses"] == 1
    assert signup(guest(h), invite["token"], "last-invite-user").status_code == 201
    assert signup(guest(h), invite["token"], "one-too-many").status_code == 400
    assert existing.post("/api/v1/auth/invitation-info", json=payload).status_code == 400
    assert invite["id"] not in {row["id"] for row in h.admin.get("/api/v1/invitations").json()}
    with h.app.state.sessions() as db:
        row = db.get(Invitation, invite["id"])
        assert row.used_count == 2 and row.used_at is not None


def test_unlimited_invites_still_expire_and_can_be_revoked(h):
    invite = invitation(h, max_uses=None)
    assert invite["max_uses"] is None and invite["remaining_uses"] is None
    for i in range(3):
        assert signup(guest(h), invite["token"], f"unlimited-{i}").status_code == 201
    info = guest(h).post("/api/v1/auth/invitation-info", json={"token": invite["token"]}).json()
    assert info["used_count"] == 3 and info["remaining_uses"] is None
    with h.app.state.sessions.begin() as db:
        row = db.get(Invitation, invite["id"])
        assert row.used_at is None
        row.expires_at = now() - timedelta(seconds=1)
    assert signup(guest(h), invite["token"], "expired-user").status_code == 400
    second = invitation(h, max_uses=None)
    assert signup(guest(h), second["token"], "before-revoke").status_code == 201
    assert h.admin.delete(f"/api/v1/invitations/{second['id']}").status_code == 204
    assert signup(guest(h), second["token"], "after-revoke").status_code == 400


def test_invitation_limits_validate_and_non_admin_cannot_issue(h):
    for invalid in (0, -1, 10001, 1.5, True, "5"):
        assert h.admin.post("/api/v1/invitations", json={"max_uses": invalid}).status_code == 422
    member, _ = h.member()
    assert member.post("/api/v1/invitations", json={"max_uses": None}).status_code == 403
    assert invitation(h)["max_uses"] == 1


def test_concurrent_invitation_acceptance_cannot_exceed_capacity(h):
    clients = [register(h, f"concurrent-{i}")[0] for i in range(3)]
    invite = invitation(h, max_uses=2)
    barrier = Barrier(3)

    def join(client):
        barrier.wait(timeout=10)
        return client.post("/api/v1/auth/join", json={"token": invite["token"]}).status_code

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(join, clients))
    assert sorted(results) == [200, 200, 400]
    with h.app.state.sessions() as db:
        assert db.get(Invitation, invite["id"]).used_count == 2


def test_disabling_user_revokes_access_and_can_be_reenabled(h):
    member, user = h.member("admin")
    personal = h.resource("personal", member, is_public=True)
    team = h.resource("team", member)
    invite = member.post("/api/v1/invitations", json={"max_uses": None}).json()
    assert signup(guest(h), invite["token"], "already-invited").status_code == 201
    reset_token = h.admin.post(f"/api/v1/admin/users/{user['id']}/recovery").json()["token"]
    visitor = guest(h)
    url = f"/api/v1/admin/users/{user['id']}"
    assert h.admin.delete(url + "?version=1").status_code == 405
    assert member.get("/api/v1/me").status_code == 200
    response = h.admin.patch(url, json={"version": 1, "active": False, "is_superadmin": False})
    assert response.status_code == 200, response.text
    assert member.get("/api/v1/me").status_code == 401
    login = {"username": user["username"], "password": "test-member-password-2026"}
    assert visitor.post("/api/v1/auth/login", json=login).status_code == 401
    assert (
        visitor.post(
            "/api/v1/auth/reset",
            json={
                "username": user["username"],
                "recovery_code": user["recovery_code"],
                "password": "new-account-password",
            },
        ).status_code
        == 400
    )
    reset_payload = {"token": reset_token, "password": "new-account-password"}
    assert visitor.post("/api/v1/auth/reset-token", json=reset_payload).status_code == 400
    assert signup(visitor, invite["token"], "after-disable").status_code == 400
    assert visitor.get("/api/v1/public/navigation", params={"owner": user["id"]}).status_code == 404
    assert h.admin.get(f"/api/v1/resources/{personal['id']}").status_code == 404
    assert h.admin.get(f"/api/v1/resources/{team['id']}").status_code == 200
    listed = h.admin.get("/api/v1/admin/users", params={"q": user["username"]}).json()
    assert listed["total"] == 1 and not listed["items"][0]["active"]
    with h.app.state.sessions() as db:
        assert db.get(User, user["id"]).deleted_at is None
        assert db.get(Resource, personal["id"]) is not None
        assert not db.scalar(select(Session).where(Session.user_id == user["id"]))
        assert db.scalar(select(Membership).where(Membership.user_id == user["id"])).active
        assert db.scalar(select(AccountReset).where(AccountReset.user_id == user["id"])).expires_at <= now()
    assert signup(visitor, invitation(h)["token"], user["username"]).status_code == 409
    assert h.admin.patch(url, json={"version": 2, "active": True, "is_superadmin": False}).status_code == 200
    assert visitor.post("/api/v1/auth/login", json=login).status_code == 200
    assert visitor.get(f"/api/v1/resources/{personal['id']}").status_code == 200
    assert member.get("/api/v1/me").status_code == 401
    assert visitor.post("/api/v1/auth/reset-token", json=reset_payload).status_code == 400
    assert signup(guest(h), invite["token"], "after-reenable").status_code == 400


def test_disable_user_permission_version_and_last_space_admin_guards(h):
    member, user = h.member("admin")
    url = f"/api/v1/admin/users/{user['id']}"
    payload = {"version": 1, "active": False, "is_superadmin": False}
    assert guest(h).patch(url, json=payload).status_code == 401
    assert member.patch(url, json=payload).status_code == 403
    assert h.admin.patch(url, json={**payload, "version": 99}).status_code == 409
    assert h.admin.patch(f"/api/v1/admin/users/{h.admin_user['id']}", json=payload).status_code == 409
    assert h.admin.post("/api/v1/workspace/leave").status_code == 200
    assert h.admin.patch(url, json=payload).status_code == 409
    space = h.admin_user["workspace"]["id"]
    assert h.admin.post(f"/api/v1/workspaces/{space}/select").status_code == 200
    assert (
        h.admin.post(
            "/api/v1/workspace/members",
            json={
                "username": h.admin_user["username"],
                "role": "admin",
            },
        ).status_code
        == 201
    )
    assert h.admin.patch(url, json=payload).status_code == 200


def test_all_database_tables_and_columns_have_chinese_comments(h):
    inspector = inspect(h.app.state.engine)
    for table in Base.metadata.tables.values():
        assert table.comment and any("\u4e00" <= c <= "\u9fff" for c in table.comment)
        assert all(column.comment for column in table.columns), table.name
        if inspector.bind.dialect.name == "postgresql":
            assert inspector.get_table_comment(table.name)["text"] == table.comment
            actual = {row["name"]: row["comment"] for row in inspector.get_columns(table.name)}
            assert actual == {column.name: column.comment for column in table.columns}
    if inspector.bind.dialect.name == "postgresql":
        assert inspector.get_table_comment("alembic_version")["text"]
        assert inspector.get_columns("alembic_version")[0]["comment"]


def test_upgrade_preserves_old_invites_and_downgrade_does_not_reopen_used_links(h):
    unused = invitation(h)
    consumed = invitation(h)
    assert signup(guest(h), consumed["token"], "legacy-member").status_code == 201
    config = Config(str(ROOT / "backend/alembic.ini"))
    config.attributes["database_url"] = h.settings.resolved_database_url
    command.downgrade(config, "b9410d2ad582")
    command.upgrade(config, "head")
    with h.app.state.sessions() as db:
        assert db.get(Invitation, unused["id"]).used_count == 0
        old = db.get(Invitation, consumed["id"])
        assert old.max_uses == 1 and old.used_count == 1 and old.used_at is not None
    assert signup(guest(h), consumed["token"], "legacy-replay").status_code == 400
    assert signup(guest(h), unused["token"], "legacy-unused").status_code == 201
    multi = invitation(h, max_uses=5)
    assert signup(guest(h), multi["token"], "used-multi").status_code == 201
    command.downgrade(config, "b9410d2ad582")
    with h.app.state.engine.connect() as connection:
        assert connection.scalar(text("SELECT used_at FROM invitations WHERE id = :id"), {"id": multi["id"]})
    command.upgrade(config, "head")
    assert signup(guest(h), multi["token"], "downgrade-replay").status_code == 400


def test_installed_c3_revision_upgrades_without_resetting_usage_or_deleted_users(h):
    invite = invitation(h, max_uses=5)
    unlimited = invitation(h, max_uses=None)
    _, user = register(h, "legacy-deleted-user")
    # Represent a historical tombstone without exposing a new deletion operation.
    with h.app.state.sessions.begin() as db:
        record = db.get(User, user["id"])
        record.deleted_at, record.active = now(), False
    config = Config(str(ROOT / "backend/alembic.ini"))
    config.attributes["database_url"] = h.settings.resolved_database_url
    command.downgrade(config, "c3d8f7a9b641")
    with h.app.state.engine.begin() as connection:
        connection.execute(
            text("UPDATE invitations SET used_count = 2, used_at = NULL WHERE id = :id"), {"id": invite["id"]}
        )
        connection.execute(
            text("UPDATE invitations SET used_count = 3, max_uses = 0, used_at = NULL WHERE id = :id"),
            {"id": unlimited["id"]},
        )
    command.upgrade(config, "head")
    with h.app.state.sessions() as db:
        assert db.get(User, user["id"]).deleted_at is not None
        assert db.get(Invitation, invite["id"]).used_count == 2
        assert db.get(Invitation, unlimited["id"]).used_count == 3
        assert db.get(Invitation, unlimited["id"]).max_uses is None
    preview = guest(h).post("/api/v1/auth/invitation-info", json={"token": invite["token"]})
    assert preview.json()["remaining_uses"] == 3
