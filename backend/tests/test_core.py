from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from conftest import draft_from
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.cli import database_backup
from app.db import now
from app.main import create_app
from app.models import Credential, Resource, Session


def test_persistence_and_session_security(h):
    category = h.category()
    resource = h.resource(category=category)
    with h.app.state.sessions() as db:
        assert db.get(Resource, resource["id"]).name == "订单文档"
        sessions = db.scalars(select(Session)).all()
        assert h.admin.cookies["team_nav_session"] not in [row.token_hash for row in sessions]
    fresh = TestClient(h.app, headers={"Origin": "http://testserver"})
    response = fresh.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin-private-pass-2026"}
    )
    assert response.status_code == 200
    assert "HttpOnly" in response.headers["set-cookie"]
    assert fresh.get(f"/api/v1/resources/{resource['id']}").json()["name"] == "订单文档"
    assert fresh.get("/api/v1/me").headers["cache-control"] == "no-store"


def test_setup_is_one_time_and_login_exact_password(h):
    assert h.admin.get("/api/v1/setup/status").json() == {"needs_setup": False, "registration_enabled": True}
    response = h.admin.post(
        "/api/v1/setup",
        json={
            "username": "attacker",
            "display_name": "x",
            "password": "some-other-password",
            "workspace_name": "y",
            "token": h.settings.setup_token_file.read_text(),
        },
    )
    assert response.status_code == 409
    token = h.admin.post("/api/v1/invitations", json={}).json()["token"]
    client = TestClient(h.app, headers={"Origin": "http://testserver"})
    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "username": "spaces",
                "display_name": "空格",
                "password": " a long password ",
                "token": token,
            },
        ).status_code
        == 201
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "spaces", "password": "a long password"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "spaces", "password": " a long password "}
        ).status_code
        == 200
    )


def test_personal_isolation_including_administrator(h):
    alice, _ = h.member()
    bob, _ = h.member()
    category = h.category("personal", alice)
    resource = h.resource("personal", alice, category, name="私人资料", description="PRIVATE-METADATA")
    alice.put(f"/api/v1/me/favorites/{resource['id']}")
    alice.post("/api/v1/me/visits", json={"endpoint_id": resource["endpoints"][0]["id"]})
    for outsider in (bob, h.admin):
        assert outsider.get(f"/api/v1/resources/{resource['id']}").status_code == 404
        assert (
            outsider.patch(
                f"/api/v1/resources/{resource['id']}", json=draft_from(resource, name="盗改")
            ).status_code
            == 404
        )
        assert resource["id"] not in outsider.get("/api/v1/resources?view=personal").text
        assert resource["id"] not in outsider.get("/api/v1/resources?view=favorites").text
        assert resource["id"] not in outsider.get("/api/v1/resources?view=recent").text
        assert category["id"] not in outsider.get("/api/v1/catalog").text
        assert "PRIVATE-METADATA" not in outsider.get("/api/v1/exports?scope=personal").text
        assert resource["id"] not in outsider.get("/api/v1/audit-events").text
    assert (
        h.admin.put(
            f"/api/v1/resources/{resource['id']}/grants/{h.admin_user['id']}", json={"can_read": True}
        ).status_code
        == 404
    )


def test_category_and_role_permissions(h):
    member, _ = h.member()
    maintainer, _ = h.member("maintainer")
    category = h.category()
    for client in (member, maintainer):
        assert (
            client.post("/api/v1/categories", json={"scope": "team", "name": "未获设置权限"}).status_code
            == 403
        )
    resource = h.resource(client=maintainer, category=category)
    assert member.get(f"/api/v1/resources/{resource['id']}").status_code == 200
    assert (
        member.patch(
            f"/api/v1/resources/{resource['id']}", json=draft_from(resource, name="未授权更新")
        ).status_code
        == 403
    )
    assert (
        maintainer.patch(
            f"/api/v1/resources/{resource['id']}", json=draft_from(resource, name="维护人更新")
        ).status_code
        == 200
    )
    h.resource("personal", member, name="自己的书签")


def test_space_boundaries_filter_search_and_exports(h):
    member, _ = h.member()
    original = h.resource(name="原空间资料")
    created = h.admin.post("/api/v1/workspace", json={"name": "另一个空间"})
    assert created.status_code == 201, created.text
    hidden = h.resource(name="OTHER-SPACE-RESOURCE", description="hidden-space-metadata")
    assert member.get(f"/api/v1/resources/{hidden['id']}").status_code == 404
    assert member.get("/api/v1/resources?q=OTHER").json()["total"] == 0
    assert "hidden-space-metadata" not in member.get("/api/v1/exports?scope=team").text
    assert member.get(f"/api/v1/resources/{original['id']}").status_code == 200


def test_versions_and_concurrent_writers(h):
    resource = h.resource()

    def save(name):
        return h.admin.patch(f"/api/v1/resources/{resource['id']}", json=draft_from(resource, name=name))

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ["第一次修改", "第二次修改"]))
    assert sorted(result.status_code for result in results) == [200, 409], [result.text for result in results]
    conflict = next(result for result in results if result.status_code == 409)
    assert conflict.json()["detail"]["current"]["version"] == 2
    assert len(h.admin.get(f"/api/v1/resources/{resource['id']}/revisions").json()) == 2


def grant_manager(h, resource):
    assert h.admin.get(f"/api/v1/resources/{resource['id']}").json()["can_manage_accounts"]


def create_account(h, resource, endpoint=None):
    endpoint = endpoint or resource["endpoints"][0]
    grant_manager(h, resource)
    response = h.admin.post(
        f"/api/v1/endpoints/{endpoint['id']}/credentials",
        json={
            "name": "联调账号",
            "username": "realistic-test-user",
            "password": "SENSITIVE-test-pass-2026",
            "usage_note": "只读用途",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_credential_encryption_and_workspace_roles(h):
    resource = h.system()
    endpoint = resource["endpoints"][0]
    credential = create_account(h, resource, endpoint)
    access = f"/api/v1/credentials/{credential['id']}/access"
    response = h.admin.post(access, json={"field": "password", "purpose": "copy"})
    assert response.json()["value"] == "SENSITIVE-test-pass-2026"
    assert response.headers["cache-control"] == "no-store"
    with h.app.state.sessions() as db:
        stored = db.get(Credential, credential["id"])
        assert "SENSITIVE" not in stored.password_ciphertext and "realistic" not in stored.username_ciphertext
        assert stored.password_nonce != stored.username_nonce
    for path in ("/api/v1/resources", "/api/v1/audit-events", "/api/v1/exports?scope=team"):
        body = h.admin.get(path).text
        assert "SENSITIVE-test-pass-2026" not in body and "realistic-test-user" not in body
    member, _ = h.member()
    accounts = member.get(f"/api/v1/endpoints/{endpoint['id']}/credentials").json()
    assert accounts[0]["username"] is None
    assert accounts[0]["can_read"] and not accounts[0]["can_manage"]
    assert "password" not in accounts[0]
    assert member.post(access, json={"field": "password", "purpose": "copy"}).status_code == 200
    assert (
        member.patch(
            f"/api/v1/credentials/{credential['id']}", json={"version": 1, "name": "盗改"}
        ).status_code
        == 403
    )
    maintainer, _ = h.member("maintainer")
    assert (
        maintainer.patch(
            f"/api/v1/credentials/{credential['id']}", json={"version": 1, "name": "维护人更新账号"}
        ).status_code
        == 200
    )
    assert (
        h.admin.put(
            f"/api/v1/credentials/{credential['id']}/grants/{h.admin_user['id']}", json={"can_read": True}
        ).status_code
        == 410
    )


def test_binding_changes_trash_and_expiration_block_secrets(h):
    resource = h.system()
    credential = create_account(h, resource)
    access = f"/api/v1/credentials/{credential['id']}/access"
    draft = draft_from(resource)
    draft["endpoints"][0]["url"] = "https://new-host.example/"
    resource = h.admin.patch(f"/api/v1/resources/{resource['id']}", json=draft).json()
    assert h.admin.post(access, json={"field": "password", "purpose": "copy"}).status_code == 403
    updated = h.admin.get(f"/api/v1/endpoints/{credential['endpoint_id']}/credentials").json()[0]
    assert updated["status"] == "pending"
    assert (
        h.admin.patch(
            f"/api/v1/credentials/{credential['id']}",
            json={"version": updated["version"], "name": updated["name"], "status": "active"},
        ).status_code
        == 200
    )
    assert h.admin.post(access, json={"field": "password", "purpose": "copy"}).status_code == 200
    assert (
        h.admin.delete(f"/api/v1/resources/{resource['id']}?version={resource['version']}").status_code == 204
    )
    assert h.admin.post(access, json={"field": "password", "purpose": "copy"}).status_code == 404
    trashed = h.admin.get("/api/v1/trash").json()[0]
    assert (
        h.admin.post(
            f"/api/v1/trash/{resource['id']}/restore", json={"version": trashed["version"]}
        ).status_code
        == 200
    )
    assert h.admin.post(access, json={"field": "password", "purpose": "copy"}).status_code == 403
    with h.app.state.sessions.begin() as db:
        row = db.get(Credential, credential["id"])
        row.status, row.expires_at = "active", now() - timedelta(seconds=1)
    assert h.admin.post(access, json={"field": "password", "purpose": "copy"}).status_code == 403


def test_invitation_replay_revocation_and_last_admin(h):
    token = h.admin.post("/api/v1/invitations", json={}).json()["token"]
    client = TestClient(h.app, headers={"Origin": "http://testserver"})
    payload = {
        "username": "invited",
        "display_name": "受邀成员",
        "password": "some-long-password",
        "token": token,
    }
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json={**payload, "username": "replay"}).status_code == 400
    member, user = h.member()
    assert (
        h.admin.patch(
            f"/api/v1/members/{h.admin_user['id']}", json={"version": 1, "role": "member", "active": True}
        ).status_code
        == 409
    )
    assert (
        h.admin.patch(
            f"/api/v1/members/{user['id']}", json={"version": 1, "role": "member", "active": False}
        ).status_code
        == 200
    )
    assert member.get("/api/v1/me").status_code == 200
    assert member.get("/api/v1/me").json()["role"] == "personal"


def test_csrf_urls_and_error_redaction(h):
    payload = h.draft()
    assert (
        h.admin.post(
            "/api/v1/resources", json=payload, headers={"Origin": "https://attacker.example"}
        ).status_code
        == 403
    )
    assert (
        h.admin.post("/api/v1/resources", json=payload, headers={"X-CSRF-Token": "invalid"}).status_code
        == 403
    )
    for url in (
        "javascript:alert(1)",
        "data:text/html,hello",
        "https://user:secret@example.com/",
        "https://example.com:bad/",
    ):
        assert h.admin.post("/api/v1/resources", json=h.draft(endpoints=[{"url": url}])).status_code == 422
    response = h.admin.post(
        "/api/v1/auth/register",
        json={"username": "short", "display_name": "short", "password": "SECRET", "token": "short"},
    )
    assert response.status_code == 422 and "SECRET" not in response.text
    missing = h.admin.post("/api/v1/auth/register", json={"unknown": "PRIVATE-INPUT"})
    assert missing.status_code == 422
    assert "Field required" not in missing.text and "Extra inputs" not in missing.text
    assert "PRIVATE-INPUT" not in missing.text
    assert "请填写用户名" in missing.text


def test_directory_migration_and_depth(h):
    first, second = h.category(), h.category(name="新业务线")
    resource = h.resource(category=first)
    assert h.admin.delete(f"/api/v1/categories/{first['id']}?version=1").status_code == 409
    assert (
        h.admin.delete(f"/api/v1/categories/{first['id']}?version=1&target_id={second['id']}").status_code
        == 204
    )
    assert h.admin.get(f"/api/v1/resources/{resource['id']}").json()["category_id"] == second["id"]
    root = h.category("personal")
    parent = root
    for depth in range(2, 9):
        parent = h.category("personal", name=f"第{depth}层", parent_id=parent["id"])
    assert (
        h.admin.post(
            "/api/v1/categories", json={"scope": "personal", "name": "第九层", "parent_id": parent["id"]}
        ).status_code
        == 422
    )
    nested = h.resource("personal", category=parent, name="深层书签")
    assert (
        h.admin.get("/api/v1/resources", params={"view": "personal", "category_id": root["id"]}).json()[
            "items"
        ][0]["id"]
        == nested["id"]
    )


def test_search_environment_and_favorite_reference(h):
    resource = h.system()
    member, _ = h.member()
    for query in ("订单", "dingdan", "ddzx", "订单 测试"):
        assert member.get("/api/v1/resources", params={"q": query}).json()["total"] == 1
    member.put(f"/api/v1/me/favorites/{resource['id']}")
    h.admin.patch(f"/api/v1/resources/{resource['id']}", json=draft_from(resource, name="订单新名称"))
    assert member.get("/api/v1/resources?view=favorites").json()["items"][0]["name"] == "订单新名称"


def test_suggestion_requires_maintainer_publish(h):
    member, _ = h.member()
    response = member.post(
        "/api/v1/feedback", json={"kind": "add", "title": "新文档", "url": "https://new.example/"}
    )
    assert response.status_code == 201
    item = response.json()
    assert h.admin.get("/api/v1/resources").json()["total"] == 0
    assert (
        member.post(
            f"/api/v1/feedback/{item['id']}/resolve",
            json={"version": 1, "status": "accepted", "resource": h.draft()},
        ).status_code
        == 403
    )
    assert (
        h.admin.post(
            f"/api/v1/feedback/{item['id']}/resolve",
            json={"version": 1, "status": "accepted", "resource": h.draft(name="新文档")},
        ).status_code
        == 200
    )
    assert member.get("/api/v1/resources").json()["items"][0]["name"] == "新文档"


def test_sqlite_backup_is_restorable(h, tmp_path):
    if not h.settings.database_url.startswith("sqlite"):
        return
    resource = h.resource()
    credential = create_account(h, resource)
    backup = tmp_path / "restored.db"
    database_backup(h.settings, backup)
    restored = create_app(h.settings.model_copy(update={"database_url": f"sqlite:///{backup.as_posix()}"}))
    with TestClient(restored, headers={"Origin": "http://testserver"}) as client:
        response = client.post(
            "/api/v1/auth/login", json={"username": "admin", "password": "admin-private-pass-2026"}
        )
        assert response.status_code == 200
        assert client.get(f"/api/v1/resources/{resource['id']}").status_code == 200
        with restored.state.sessions() as db:
            row = db.get(Credential, credential["id"])
            assert restored.state.vault.decrypt(row, "password") == "SENSITIVE-test-pass-2026"
