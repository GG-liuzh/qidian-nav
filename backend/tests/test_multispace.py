from datetime import timedelta

from conftest import draft_from
from fastapi.testclient import TestClient
from sqlalchemy import select
from test_core import create_account
from test_independent_navigation import personal_account, register, set_workspace

from app.db import now
from app.models import AccountReset, Category, Resource

BOOKMARKS = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<DL><p><DT><H3 PERSONAL_TOOLBAR_FOLDER="true">书签栏</H3><DL><p>
<DT><H3>工作</H3><DL><p>
<DT><A HREF="https://docs.example/?a=1&amp;b=2">A &amp; B</A>[cite: 1]
<DT><H3>学习</H3><DL><p><DT><H3>Python</H3><DL><p><DT><H3>进阶</H3><DL><p>
<DT><A HREF="https://python.example/advanced">高级文档</A>
</DL><p></DL><p></DL><p>
<DT><A HREF="javascript:alert('bad')">不支持的脚本书签</A>
</DL><p><DT><A HREF="https://docs.example/?a=1&amp;b=2">重复链接</A>
</DL><p></DL><p>"""


def test_multi_space_roles_and_explicit_context_do_not_follow_other_tabs(h):
    first_space = h.admin_user["workspace"]["id"]
    member, user = h.member()
    first = h.resource(name="仅第一个空间")
    response = h.admin.post("/api/v1/workspace", json={"name": "第二个空间"})
    assert response.status_code == 201, response.text
    second_space = response.json()["workspace"]["id"]
    assert second_space != first_space
    added = h.admin.post(
        "/api/v1/workspace/members", json={"username": user["username"], "role": "maintainer"}
    )
    assert added.status_code == 201, added.text
    second = h.resource(name="第二个空间链接")
    member.headers["X-Workspace-ID"] = first_space
    switched = member.post(f"/api/v1/workspaces/{second_space}/select")
    assert switched.status_code == 200 and switched.json()["role"] == "maintainer"
    assert {space["id"]: space["role"] for space in switched.json()["workspaces"]} == {
        first_space: "member",
        second_space: "maintainer",
    }
    # A tab retaining the first-space header must never edit using the other tab's role.
    assert member.patch(f"/api/v1/resources/{first['id']}", json=draft_from(first)).status_code == 403
    assert member.get(f"/api/v1/resources/{second['id']}").status_code == 404
    assert member.get("/api/v1/resources?view=team").json()["items"][0]["id"] == first["id"]
    exported = member.get("/api/v1/exports", params={"scope": "team", "workspace_id": first_space})
    assert "仅第一个空间" in exported.text and "第二个空间链接" not in exported.text
    member.headers["X-Workspace-ID"] = second_space
    assert (
        member.patch(
            f"/api/v1/resources/{second['id']}", json=draft_from(second, name="维护人编辑成功")
        ).status_code
        == 200
    )
    assert (
        member.post("/api/v1/categories", json={"scope": "team", "name": "维护人不能改目录"}).status_code
        == 403
    )
    other, _ = register(h)
    assert other.post(f"/api/v1/workspaces/{second_space}/select").status_code == 403
    assert other.post("/api/v1/workspace/members", json={"username": user["username"]}).status_code == 403
    own = h.resource("personal", member, name="跨空间的个人导航")
    member.headers["X-Workspace-ID"] = first_space
    assert member.get(f"/api/v1/resources/{own['id']}").status_code == 200


def test_existing_users_can_preview_invites_and_join_multiple_spaces(h):
    client, user = register(h)
    first_token = h.admin.post("/api/v1/invitations", json={"role": "member"}).json()["token"]
    preview = client.post("/api/v1/auth/invitation-info", json={"token": first_token})
    assert preview.status_code == 200 and preview.json()["role"] == "member"
    assert client.post("/api/v1/auth/join", json={"token": first_token}).status_code == 200
    assert client.post("/api/v1/auth/invitation-info", json={"token": first_token}).status_code == 400
    created = h.admin.post("/api/v1/workspace", json={"name": "第三方协作空间"}).json()
    second_id = created["workspace"]["id"]
    token = h.admin.post("/api/v1/invitations", json={"role": "admin"}).json()["token"]
    joined = client.post("/api/v1/auth/join", json={"token": token})
    assert joined.status_code == 200 and joined.json()["id"] == user["id"]
    assert joined.json()["workspace"]["id"] == second_id
    assert len(joined.json()["workspaces"]) == 2
    assert not joined.json()["is_superadmin"]
    assert client.get("/api/v1/admin/users").status_code == 403


def test_platform_admin_controls_spaces_users_and_recovery_but_not_private_navigation(h):
    member, user = h.member("admin")
    personal = h.resource("personal", member, name="PRIVATE-USER-NAVIGATION")
    personal_account(member, personal)
    assert h.admin.get(f"/api/v1/resources/{personal['id']}").status_code == 404
    assert member.get("/api/v1/admin/users").status_code == 403
    assert member.get("/api/v1/admin/workspaces").status_code == 403
    assert member.post(f"/api/v1/admin/users/{user['id']}/recovery").status_code == 403
    users = h.admin.get("/api/v1/admin/users")
    assert users.status_code == 200 and users.json()["total"] == 2
    assert "PRIVATE-USER-NAVIGATION" not in users.text and "private-secret" not in users.text
    assert h.admin.get("/api/v1/admin/workspaces").status_code == 200
    assert (
        h.admin.patch(
            f"/api/v1/admin/users/{h.admin_user['id']}",
            json={"version": 1, "active": False, "is_superadmin": True},
        ).status_code
        == 409
    )
    # The space role and platform role are independent.
    assert not member.get("/api/v1/me").json()["is_superadmin"]
    issued = h.admin.post(f"/api/v1/admin/users/{user['id']}/recovery")
    assert issued.status_code == 200
    token = issued.json()["token"]
    with h.app.state.sessions() as db:
        reset = db.scalar(select(AccountReset).where(AccountReset.user_id == user["id"]))
        assert reset.token_hash != token
    reset_client = TestClient(h.app, headers={"Origin": "http://testserver"})
    payload = {"token": token, "password": "new-password-from-admin-link"}
    reset = reset_client.post("/api/v1/auth/reset-token", json=payload)
    assert reset.status_code == 200 and reset.json()["recovery_code"]
    assert member.get("/api/v1/me").status_code == 401
    assert reset_client.post("/api/v1/auth/reset-token", json=payload).status_code == 400
    logged = reset_client.post(
        "/api/v1/auth/login", json={"username": user["username"], "password": payload["password"]}
    )
    assert logged.status_code == 200
    assert reset_client.get(f"/api/v1/resources/{personal['id']}").status_code == 200
    assert "site.reset_issued" in h.admin.get("/api/v1/admin/events").text
    assert token not in h.admin.get("/api/v1/admin/events").text


def test_expired_reset_links_and_replaced_links_do_not_reset_accounts(h):
    _, user = register(h)
    first = h.admin.post(f"/api/v1/admin/users/{user['id']}/recovery").json()["token"]
    second = h.admin.post(f"/api/v1/admin/users/{user['id']}/recovery").json()["token"]
    guest = TestClient(h.app, headers={"Origin": "http://testserver"})
    assert (
        guest.post(
            "/api/v1/auth/reset-token", json={"token": first, "password": "another-long-password"}
        ).status_code
        == 400
    )
    with h.app.state.sessions.begin() as db:
        for row in db.scalars(select(AccountReset).where(AccountReset.user_id == user["id"])):
            row.expires_at = now() - timedelta(seconds=1)
    assert (
        guest.post(
            "/api/v1/auth/reset-token", json={"token": second, "password": "another-long-password"}
        ).status_code
        == 400
    )


def test_disabled_space_hides_public_content_but_keeps_personal_access(h):
    member, user = h.member()
    set_workspace(h, public_enabled=True)
    team = h.resource(is_public=True)
    secret = create_account(h, team)
    own = h.resource("personal", member)
    own_secret = personal_account(member, own)
    space_id = h.admin_user["workspace"]["id"]
    member.headers["X-Workspace-ID"] = space_id
    version = h.admin.get("/api/v1/admin/workspaces").json()[0]["version"]
    assert (
        h.admin.patch(
            f"/api/v1/admin/workspaces/{space_id}", json={"version": version, "active": False}
        ).status_code
        == 200
    )
    guest = TestClient(h.app)
    assert guest.get("/api/v1/public/navigation", params={"workspace_id": space_id}).status_code == 404
    assert guest.get("/api/v1/public/navigation").json()["total"] == 0
    assert member.get("/api/v1/resources?view=team").json()["total"] == 0
    assert member.get(f"/api/v1/resources/{own['id']}").status_code == 200
    access = {"field": "password", "purpose": "copy"}
    assert member.post(f"/api/v1/credentials/{own_secret['id']}/access", json=access).status_code == 200
    assert member.post(f"/api/v1/credentials/{secret['id']}/access", json=access).status_code == 404
    assert member.get("/api/v1/me").json()["workspace"] is None
    site_user = next(
        item for item in h.admin.get("/api/v1/admin/users").json()["items"] if item["id"] == user["id"]
    )
    assert (
        h.admin.patch(
            f"/api/v1/admin/users/{user['id']}",
            json={"version": site_user["version"], "active": False, "is_superadmin": False},
        ).status_code
        == 200
    )
    assert member.get("/api/v1/me").status_code == 401


def test_public_pages_separate_multiple_spaces_and_never_return_credentials(h):
    set_workspace(h, public_enabled=True)
    first = h.resource(name="FIRST-PUBLIC", is_public=True)
    first_id = h.admin_user["workspace"]["id"]
    created = h.admin.post("/api/v1/workspace", json={"name": "第二公开空间", "public_enabled": True}).json()
    second_id = created["workspace"]["id"]
    second = h.resource(name="SECOND-PUBLIC", is_public=True)
    account = create_account(h, second)
    guest = TestClient(h.app)
    a = guest.get("/api/v1/public/navigation", params={"workspace_id": first_id}).json()
    b = guest.get("/api/v1/public/navigation", params={"workspace_id": second_id}).json()
    assert a["items"][0]["id"] == first["id"] and b["items"][0]["id"] == second["id"]
    assert len(a["spaces"]) == 2
    assert account["id"] not in str(b) and "realistic-test-user" not in str(b)
    assert guest.get("/api/v1/public/navigation").json()["workspace_id"] == first_id
    assert h.admin.put(f"/api/v1/admin/home/{second_id}").status_code == 200
    assert guest.get("/api/v1/public/navigation").json()["workspace_id"] == second_id


def test_chrome_bookmark_import_preserves_folders_entities_privacy_and_preferences(h):
    client, user = register(h)
    client.patch("/api/v1/me/preferences", json={"theme": "dark", "layout": "list"})
    payload = {"html": "\ufeff" + BOOKMARKS}
    preview = client.post("/api/v1/me/bookmarks/preview", json=payload)
    assert preview.status_code == 200, preview.text
    data = preview.json()
    assert data["read"] == 4 and data["resources"] == 2
    assert data["duplicates_in_file"] == 1 and data["skipped_invalid"] == 1
    assert data["categories"] == 4
    assert data["examples"][0]["name"] == "A & B"
    assert data["examples"][0]["url"] == "https://docs.example/?a=1&b=2"
    assert client.get("/api/v1/resources?view=personal").json()["total"] == 0
    imported = client.post("/api/v1/me/bookmarks/import", json=payload)
    assert imported.status_code == 200 and imported.json()["imported"] == 2
    resources = client.get("/api/v1/resources?view=personal").json()["items"]
    assert all(not row["is_public"] and row["scope"] == "personal" for row in resources)
    assert client.get("/api/v1/me").json()["preferences"]["theme"] == "dark"
    assert h.admin.get("/api/v1/resources?view=personal").json()["total"] == 0
    categories = client.get("/api/v1/catalog").json()["categories"]
    assert "书签栏" not in [row["name"] for row in categories]
    root = next(row for row in categories if row["name"] == "工作")
    assert (
        client.get("/api/v1/resources", params={"view": "personal", "category_id": root["id"]}).json()[
            "total"
        ]
        == 2
    )
    with h.app.state.sessions() as db:
        leaf = next(row for row in categories if row["name"] == "进阶")
        level = db.get(Category, leaf["id"])
        assert db.get(Category, level.parent_id).name == "Python"
        assert all(row.owner_user_id == user["id"] for row in db.scalars(select(Resource)))
    client.patch("/api/v1/me/preferences", json={"theme": "light"})
    again = client.post("/api/v1/me/bookmarks/import", json=payload)
    assert again.json()["already_imported"]
    assert client.get("/api/v1/me").json()["preferences"]["theme"] == "light"
    migration = client.post("/api/v1/me/transfer/export", json={})
    assert migration.status_code == 200
    target, _ = register(h, "second-import-user")
    assert (
        target.post("/api/v1/me/transfer/import", json={"package": migration.json()}).json()["imported"] == 2
    )


def test_bookmark_import_flat_and_copy_options_and_invalid_files(h):
    client, _ = register(h)
    payload = {"html": BOOKMARKS, "folders": "flat", "duplicates": "copy"}
    assert client.post("/api/v1/me/bookmarks/preview", json=payload).json()["resources"] == 3
    imported = client.post("/api/v1/me/bookmarks/import", json=payload)
    assert imported.status_code == 200 and imported.json()["imported"] == 3
    assert client.get("/api/v1/catalog").json()["categories"] == []
    assert (
        client.post("/api/v1/me/bookmarks/import", json={"html": "<script>bad()</script>"}).status_code == 422
    )
    assert (
        TestClient(h.app, headers={"Origin": "http://testserver"})
        .post("/api/v1/me/bookmarks/import", json=payload)
        .status_code
        == 401
    )
    assert client.get("/api/v1/resources?view=personal").json()["total"] == 3
